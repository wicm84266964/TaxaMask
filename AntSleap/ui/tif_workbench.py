import os

import numpy as np
from PySide6.QtCore import QObject, QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.core.amira_import import import_amira_directory
    from AntSleap.core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, TifBackendRunner, sanitize_tif_backend_config
    from AntSleap.core.tif_export import export_tif_training_dataset
    from AntSleap.core.tif_materials import next_material_id, read_material_map, remove_material, upsert_material, write_material_map
    from AntSleap.core.tif_prediction_import import default_prediction_id_for_tif, import_external_prediction_tif
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_stack_import import import_tif_stack
    from AntSleap.core.tif_volume_io import create_empty_label_sidecar_like, flush_volume_array, load_volume_sidecar, volume_sidecar_exists
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.amira_import import import_amira_directory
    from core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, TifBackendRunner, sanitize_tif_backend_config
    from core.tif_export import export_tif_training_dataset
    from core.tif_materials import next_material_id, read_material_map, remove_material, upsert_material, write_material_map
    from core.tif_prediction_import import default_prediction_id_for_tif, import_external_prediction_tif
    from core.tif_project import TifProjectManager
    from core.tif_stack_import import import_tif_stack
    from core.tif_volume_io import create_empty_label_sidecar_like, flush_volume_array, load_volume_sidecar, volume_sidecar_exists


TIF_TRANSLATIONS = {
    "zh": {
        "Material": "Material",
        "ID": "ID",
        "Name": "名称",
        "Display name": "显示名称",
        "Color": "颜色",
        "Trainable": "可训练",
        "Choose color": "选择颜色",
        "No TIF volume loaded": "未加载 TIF 体数据",
        "Specimens": "Specimen",
        "Volume slices": "体数据切片",
        "Volume controls": "体数据控制",
        "Annotation tools": "标注工具",
        "Model training": "模型训练",
        "Model configuration": "模型配置",
        "Workbench log": "工作台日志",
        "Slice": "切片",
        "Label layer": "标签层",
        "Manual truth is a read-only reference. Switch to Current edit before changing labels.": "人工真值是只读基准层。要修改标注，请先切换到“当前编辑”。",
        "Current edit is the editable working copy. Brush changes are saved here first.": "当前编辑是可写的工作副本。画笔修改会先保存到这一层。",
        "Model draft is a read-only prediction candidate. Copy it to Current edit before manual correction.": "模型草稿是只读的预测候选。需要人工修正时，请先复制到“当前编辑”。",
        "Cannot paint on this label layer. Switch to Current edit first.": "当前标签层不能直接绘制。请先切换到“当前编辑”。",
        "Cannot paint on model draft. Copy model draft to Current edit first.": "不能直接在模型草稿上绘制。请先复制模型草稿到“当前编辑”。",
        "manual_truth": "人工真值",
        "working_edit": "当前编辑",
        "model_draft": "模型草稿",
        "Overlay": "叠加透明度",
        "Brightness": "亮度",
        "Contrast": "对比度",
        "Brush size": "画笔大小",
        "Undo": "撤销",
        "Redo": "重做",
        "Save working edit": "保存当前编辑层",
        "Auto-save edit": "自动保存编辑层",
        "Working edit saved.": "当前编辑层已保存。",
        "Auto-saved working edit.": "已自动保存当前编辑层。",
        "Unsaved working edit": "未保存的当前编辑层",
        "Save changes to the current working_edit before continuing?": "继续前是否保存当前 working_edit 的修改？",
        "Auto-save is on. Brush changes are saved shortly after editing.": "自动保存已开启。修改后会短延迟保存。",
        "Auto-save is off. Remember to save the current edit layer.": "自动保存已关闭。请记得手动保存当前编辑层。",
        "Accept as manual truth": "确认为人工真值",
        "Copy model draft to working edit": "复制模型草稿到当前编辑层",
        "Material map": "材料表",
        "Add material": "新增 material",
        "Edit material": "编辑 material",
        "Delete material": "删除 material",
        "Data import": "数据导入",
        "Import TIF stack": "导入 TIF stack",
        "Import AMIRA directory": "导入 AMIRA 目录",
        "Start Center": "启动中心",
        "Ask Agent": "询问 Agent",
        "Training handoff": "训练交接",
        "Export train-ready volumes": "导出可训练体数据",
        "Backend parameters": "后端参数",
        "Dataset exchange": "训练数据交换",
        "Backend ID": "后端 ID",
        "Display name": "显示名称",
        "Python": "Python",
        "Export formats": "导出格式",
        "Prepare command": "Prepare 命令",
        "Train command": "训练命令",
        "Predict command": "预测命令",
        "Model manifest": "模型 manifest",
        "Save backend settings": "保存后端设置",
        "Prepare dataset": "准备训练数据",
        "Train backend": "训练后端",
        "Import prediction": "运行预测并导入草稿",
        "Import external label TIF to draft": "导入外部标签 TIF 到草稿",
        "Import External Label TIF": "导入外部标签 TIF",
        "Prediction ID:": "预测编号：",
        "Source model:": "来源模型：",
        "Imported external label TIF as model draft for specimen {0}. Report: {1}": "已为 specimen {0} 将外部标签 TIF 导入模型草稿。报告：{1}",
        "Please select a specimen with a working volume first.": "请先选择一个已有 working volume 的 specimen。",
        "Specimen status": "Specimen 状态",
        "Volume metadata": "体数据元数据",
        "No specimens in this TIF project": "当前 TIF 项目还没有 specimen",
        "Working volume missing": "缺少 working volume",
        "yes": "是",
        "no": "否",
        "Train": "训练",
        "train-ready": "可训练",
        "not train-ready": "不可训练",
        "Status": "状态",
        "Train-ready": "可训练",
        "Reasons": "原因",
        "Shape Z/Y/X": "Shape Z/Y/X",
        "dtype": "dtype",
        "spacing Z/Y/X": "spacing Z/Y/X",
        "modality": "成像类型",
        "TIF data import": "TIF 数据导入",
        "Please create or open a TIF project first.": "请先新建或打开一个 TIF 项目。",
        "Please create or open a TIF volume project first.": "请先新建或打开一个 TIF 体数据项目。",
        "Import TIF Stack": "导入 TIF stack",
        "Import AMIRA Directory": "导入 AMIRA 目录",
        "Specimen ID:": "Specimen 编号：",
        "Imported TIF stack for specimen {0}. Report: {1}": "已为 specimen {0} 导入 TIF stack。报告：{1}",
        "Importing TIF stack...": "正在导入 TIF stack...",
        "Reading TIF slices": "正在读取 TIF 切片",
        "Reading TIF volume": "正在读取 TIF 体数据",
        "Writing TIF sidecar": "正在写入 TIF sidecar",
        "Creating editable label layer": "正在创建可编辑标签层",
        "Saving TIF project": "正在保存 TIF 项目",
        "TIF import is already running.": "已有 TIF 导入正在运行。",
        "Imported AMIRA directory for specimen {0}. Report: {1}": "已为 specimen {0} 导入 AMIRA 目录。报告：{1}",
        "TIF training handoff": "TIF 训练交接",
        "Export train-ready TIF volumes": "导出可训练 TIF 体数据",
        "Exported {0} train-ready specimen(s).\nManifest: {1}": "已导出 {0} 个可训练 specimen。\nManifest：{1}",
        "Export failed: {0}": "导出失败：{0}",
        "TIF backend": "TIF 后端",
        "Backend settings saved.": "后端设置已保存。",
        "Running {0}...": "正在运行：{0}...",
        "Action finished: {0}\nRun: {1}": "动作完成：{0}\n运行目录：{1}",
        "Action failed: {0}": "动作失败：{0}",
        "No command configured for this backend action.": "这个后端动作还没有配置命令。",
        "No train-ready specimens are available.": "当前没有可训练 specimen。",
        "No specimen is available for prediction.": "当前没有可用于预测的 specimen。",
        "Copied latest model draft into working_edit.": "已将最新模型草稿复制到当前编辑层。",
        "No model draft is available for this specimen.": "当前 specimen 还没有模型草稿。",
        "Background material cannot be deleted.": "不能删除 background material。",
        "Material {0} is still used by a label volume.": "Material {0} 仍被 label volume 使用，不能删除。",
        "Delete material {0} ({1})?": "删除 material {0}（{1}）？",
        "Accept working edit": "确认当前编辑层",
        "Promote the current working_edit layer to manual_truth for training?": "将当前 working_edit 提升为可训练的 manual_truth？",
    }
}


def tt(text, lang):
    return TIF_TRANSLATIONS.get(lang, {}).get(text, text)


def _now_log_time():
    from datetime import datetime

    return datetime.now().strftime("%H:%M:%S")


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
        self.trainable_check = QCheckBox(tt("Trainable", self.lang))
        self.trainable_check.setChecked(bool(material.get("trainable", self.id_spin.value() != 0)))
        self.color_button = QPushButton(tt("Choose color", self.lang))
        self.color_button.clicked.connect(self.choose_color)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow(tt("ID", self.lang), self.id_spin)
        form.addRow(tt("Name", self.lang), self.name_edit)
        form.addRow(tt("Display name", self.lang), self.display_edit)
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_edit, 1)
        color_row.addWidget(self.color_button)
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


class WheelSafeComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class WheelSafeSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()


class WheelSafeSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class TifSliceCanvas(QLabel):
    ZOOM_STEPS = (1.0, 1.25, 1.5, 2.0, 3.0, 4.0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tifSliceCanvas")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(360, 280)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFrameShape(QFrame.NoFrame)
        self.setText("No TIF volume loaded")
        self._pixmap = None
        self._draw_rect = QRectF()
        self._zoom_index = 0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._panning = False
        self._last_pan_pos = None
        self.workbench = None

    def set_slice_pixmap(self, pixmap, reset_view=False):
        self._pixmap = pixmap
        if reset_view:
            self.reset_view(refresh=False)
        self._refresh_scaled_pixmap()

    def reset_view(self, refresh=True):
        self._zoom_index = 0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._panning = False
        self._last_pan_pos = None
        if refresh:
            self._refresh_scaled_pixmap()

    def zoom_factor(self):
        return float(self.ZOOM_STEPS[max(0, min(self._zoom_index, len(self.ZOOM_STEPS) - 1))])

    def zoom_in(self):
        if self._pixmap is None or self._pixmap.isNull():
            return
        if self._zoom_index < len(self.ZOOM_STEPS) - 1:
            self._zoom_index += 1
            self._refresh_scaled_pixmap()

    def zoom_out(self):
        if self._pixmap is None or self._pixmap.isNull():
            return
        if self._zoom_index > 0:
            self._zoom_index -= 1
            if self._zoom_index == 0:
                self._pan_x = 0.0
                self._pan_y = 0.0
            self._refresh_scaled_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_scaled_pixmap()

    def _refresh_scaled_pixmap(self):
        if self._pixmap is None or self._pixmap.isNull():
            return
        view_w = max(1, int(self.width()))
        view_h = max(1, int(self.height()))
        base = self._pixmap.scaled(view_w, view_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        zoom = self.zoom_factor()
        target_w = max(1, int(round(base.width() * zoom)))
        target_h = max(1, int(round(base.height() * zoom)))
        zoomed = self._pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target_w = max(1, int(zoomed.width()))
        target_h = max(1, int(zoomed.height()))
        max_pan_x = max(0.0, (target_w - view_w) / 2.0)
        max_pan_y = max(0.0, (target_h - view_h) / 2.0)
        self._pan_x = max(-max_pan_x, min(max_pan_x, self._pan_x)) if max_pan_x else 0.0
        self._pan_y = max(-max_pan_y, min(max_pan_y, self._pan_y)) if max_pan_y else 0.0
        x = (view_w - target_w) / 2.0 + self._pan_x
        y = (view_h - target_h) / 2.0 + self._pan_y
        self._draw_rect = QRectF(x, y, target_w, target_h)

        composed = QPixmap(view_w, view_h)
        composed.fill(QColor("#07090A"))
        painter = QPainter(composed)
        painter.drawPixmap(int(round(x)), int(round(y)), zoomed)
        self._draw_status_overlay(painter)
        painter.end()
        self.setPixmap(composed)

    def _draw_status_overlay(self, painter):
        if self.workbench is None:
            return
        text = self.workbench.canvas_status_text(self.zoom_factor())
        if not text:
            return
        painter.save()
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        rect = QRectF(10, 10, text_w + 16, metrics.height() + 8)
        painter.fillRect(rect, QColor(7, 9, 10, 190))
        painter.setPen(QColor("#DCE4E8"))
        painter.drawText(rect.adjusted(8, 4, -8, -4), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()

    def widget_to_image_pixel(self, x, y):
        if self._pixmap is None or self._pixmap.isNull() or self._draw_rect.isNull():
            return None
        if not self._draw_rect.contains(float(x), float(y)):
            return None
        rel_x = (float(x) - self._draw_rect.x()) / max(1.0, self._draw_rect.width())
        rel_y = (float(y) - self._draw_rect.y()) / max(1.0, self._draw_rect.height())
        px = int(rel_x * self._pixmap.width())
        py = int(rel_y * self._pixmap.height())
        return (
            max(0, min(int(self._pixmap.width()) - 1, px)),
            max(0, min(int(self._pixmap.height()) - 1, py)),
        )

    def wheelEvent(self, event):
        if self.workbench is None:
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        self.setFocus(Qt.MouseFocusReason)
        self.workbench.move_slice(-1 if delta > 0 else 1)
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Left:
            if self.workbench is not None:
                self.workbench.move_slice(-1)
            event.accept()
            return
        if key == Qt.Key_Right:
            if self.workbench is not None:
                self.workbench.move_slice(1)
            event.accept()
            return
        if key == Qt.Key_Up:
            self.zoom_in()
            event.accept()
            return
        if key == Qt.Key_Down:
            self.zoom_out()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self.setFocus(Qt.MouseFocusReason)
        if event.button() == Qt.RightButton and self.zoom_factor() > 1.0:
            self._panning = True
            self._last_pan_pos = event.position()
            event.accept()
            return
        if self.workbench is not None and event.button() == Qt.LeftButton:
            self.workbench.paint_at_widget_position(event.position().x(), event.position().y(), erase=bool(event.modifiers() & Qt.ControlModifier))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and event.buttons() & Qt.RightButton and self._last_pan_pos is not None:
            current = event.position()
            self._pan_x += current.x() - self._last_pan_pos.x()
            self._pan_y += current.y() - self._last_pan_pos.y()
            self._last_pan_pos = current
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if self.workbench is not None and event.buttons() & Qt.LeftButton:
            self.workbench.paint_at_widget_position(event.position().x(), event.position().y(), erase=bool(event.modifiers() & Qt.ControlModifier))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton and self._panning:
            self._panning = False
            self._last_pan_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class TifImportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, project_manager, tif_path, specimen_id):
        super().__init__()
        self.project_manager = project_manager
        self.tif_path = tif_path
        self.specimen_id = specimen_id

    def run(self):
        try:
            result = import_tif_stack(
                self.project_manager,
                self.tif_path,
                self.specimen_id,
                copy_source=False,
                create_working_edit=False,
                progress_callback=self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class TifWorkbenchWidget(QWidget):
    start_center_requested = Signal()
    agent_requested = Signal(dict)

    def __init__(self, project_manager=None, lang="zh", parent=None, config_manager=None):
        super().__init__(parent)
        self.setObjectName("tifWorkbenchRoot")
        self.project = project_manager or TifProjectManager()
        self.lang = lang
        self.config_manager = config_manager
        config = self.config_manager.get("tif_backend", DEFAULT_TIF_BACKEND_CONFIG) if self.config_manager is not None else DEFAULT_TIF_BACKEND_CONFIG
        self.backend_config = sanitize_tif_backend_config(config)
        self.current_specimen_id = ""
        self.image_volume = None
        self.label_volume = None
        self.material_map = {}
        self.material_colors = {}
        self.current_material_id = 0
        self.edit_volume = None
        self.working_edit_dirty = False
        self._dirty_edit_slices = set()
        self._loading_specimen = False
        self._saving_working_edit = False
        self._tif_import_thread = None
        self._tif_import_worker = None
        self._tif_import_progress = None
        self._tif_import_specimen_id = ""
        self.undo_stack = []
        self.redo_stack = []

        self.specimen_list = QListWidget()
        self.specimen_list.setObjectName("tifSpecimenList")
        self.specimen_list.currentItemChanged.connect(self._on_specimen_selected)

        self.canvas = TifSliceCanvas()
        self.canvas.workbench = self
        self._reset_canvas_view_on_next_render = False
        self.slice_slider = WheelSafeSlider(Qt.Horizontal)
        self.slice_slider.setRange(0, 0)
        self.slice_slider.valueChanged.connect(self.on_slice_slider_changed)
        self.slice_prefix_label = QLabel("Slice")
        self.slice_label = QLabel("0 / 0")

        self.label_role_combo = WheelSafeComboBox()
        self._populate_label_role_combo()
        self.label_role_combo.currentIndexChanged.connect(self._reload_label_volume)
        self.label_role_help_label = QLabel("")
        self.label_role_help_label.setObjectName("tifLayerHelpText")
        self.label_role_help_label.setWordWrap(True)

        self.opacity_slider = WheelSafeSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(45)
        self.opacity_slider.valueChanged.connect(self.render_current_slice)
        self.brightness_slider = WheelSafeSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.render_current_slice)
        self.contrast_slider = WheelSafeSlider(Qt.Horizontal)
        self.contrast_slider.setRange(1, 30)
        self.contrast_slider.setValue(10)
        self.contrast_slider.valueChanged.connect(self.render_current_slice)

        self.status_label = QLabel("")
        self.status_label.setObjectName("tifStatusText")
        self.status_label.setWordWrap(True)
        self.metadata_label = QLabel("")
        self.metadata_label.setObjectName("tifMetadataText")
        self.metadata_label.setWordWrap(True)
        self.material_table = QTableWidget(0, 4)
        self.material_table.setObjectName("tifMaterialTable")
        self.material_table.setMinimumHeight(150)
        self.material_table.setMaximumHeight(240)
        self.material_table.setHorizontalHeaderLabels(["ID", "Name", "Train", "Color"])
        self.material_table.verticalHeader().setVisible(False)
        self.material_table.setShowGrid(False)
        self.material_table.setAlternatingRowColors(True)
        self.material_table.horizontalHeader().setStretchLastSection(True)
        self.material_table.itemSelectionChanged.connect(self._on_material_selected)
        self.btn_add_material = QPushButton("Add material")
        self.btn_add_material.clicked.connect(self.add_material)
        self.btn_edit_material = QPushButton("Edit material")
        self.btn_edit_material.clicked.connect(self.edit_selected_material)
        self.btn_delete_material = QPushButton("Delete material")
        self.btn_delete_material.clicked.connect(self.delete_selected_material)

        self.brush_size_slider = WheelSafeSlider(Qt.Horizontal)
        self.brush_size_slider.setRange(1, 80)
        self.brush_size_slider.setValue(8)
        self.btn_undo = QPushButton("Undo")
        self.btn_undo.clicked.connect(self.undo)
        self.btn_redo = QPushButton("Redo")
        self.btn_redo.clicked.connect(self.redo)
        self.btn_save_edit = QPushButton("Save working edit")
        self.btn_save_edit.clicked.connect(lambda: self.save_working_edit())
        self.auto_save_check = QCheckBox("Auto-save edit")
        self.auto_save_check.setObjectName("tifAutoSaveEditCheck")
        self.auto_save_check.setChecked(True)
        self.auto_save_check.toggled.connect(self._on_auto_save_toggled)
        self.btn_promote = QPushButton("Accept as manual truth")
        self.btn_promote.clicked.connect(self.promote_working_edit)
        self.btn_copy_draft = QPushButton("Copy model draft to working edit")
        self.btn_copy_draft.clicked.connect(self.copy_latest_model_draft_to_working_edit)
        self.btn_import_tif = QPushButton("Import TIF stack")
        self.btn_import_tif.setObjectName("tifImportStackButton")
        self.btn_import_tif.clicked.connect(self.import_tif_stack_dialog)
        self.btn_import_amira = QPushButton("Import AMIRA directory")
        self.btn_import_amira.setObjectName("tifImportAmiraButton")
        self.btn_import_amira.clicked.connect(self.import_amira_directory_dialog)
        self.btn_export_training = QPushButton("Export train-ready volumes")
        self.btn_export_training.setObjectName("tifExportTrainingButton")
        self.btn_export_training.clicked.connect(self.export_training_dataset)
        self.backend_id_edit = QLineEdit()
        self.backend_id_edit.setObjectName("tifBackendIdEdit")
        self.backend_display_edit = QLineEdit()
        self.backend_python_edit = QLineEdit()
        self.backend_formats_edit = QLineEdit()
        self.backend_prepare_edit = QLineEdit()
        self.backend_train_edit = QLineEdit()
        self.backend_predict_edit = QLineEdit()
        self.backend_manifest_edit = QLineEdit()
        self.btn_save_backend = QPushButton("Save backend settings")
        self.btn_save_backend.setObjectName("tifSaveBackendButton")
        self.btn_save_backend.clicked.connect(self.save_backend_settings)
        self.btn_prepare_dataset = QPushButton("Prepare dataset")
        self.btn_prepare_dataset.setObjectName("tifPrepareDatasetButton")
        self.btn_prepare_dataset.clicked.connect(lambda: self.run_backend_action("prepare_dataset"))
        self.btn_train_backend = QPushButton("Train backend")
        self.btn_train_backend.setObjectName("tifTrainBackendButton")
        self.btn_train_backend.clicked.connect(lambda: self.run_backend_action("train"))
        self.btn_import_prediction = QPushButton("Import prediction")
        self.btn_import_prediction.setObjectName("tifImportPredictionButton")
        self.btn_import_prediction.clicked.connect(lambda: self.run_backend_action("predict"))
        self.btn_import_external_prediction_tif = QPushButton("Import external label TIF to draft")
        self.btn_import_external_prediction_tif.setObjectName("tifImportExternalPredictionTifButton")
        self.btn_import_external_prediction_tif.clicked.connect(self.import_external_prediction_tif_dialog)
        self.btn_start_center = QPushButton("Start Center")
        self.btn_start_center.setObjectName("tifStartCenterButton")
        self.btn_start_center.clicked.connect(self.start_center_requested.emit)
        self.btn_ask_agent = QPushButton("Ask Agent")
        self.btn_ask_agent.setObjectName("tifAskAgentButton")
        self.btn_ask_agent.clicked.connect(lambda: self.agent_requested.emit(self.get_agent_context()))
        self.training_status_label = QLabel("")
        self.training_status_label.setObjectName("tifTrainingStatusText")
        self.training_status_label.setWordWrap(True)
        self.log_console = QTextEdit()
        self.log_console.setObjectName("tifLogConsole")
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(120)
        self.log_console.setMaximumHeight(180)
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo)
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.redo)
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.setSingleShot(True)
        self.auto_save_timer.setInterval(1200)
        self.auto_save_timer.timeout.connect(lambda: self.save_working_edit(show_message=True, reason="auto_save"))

        self._apply_button_roles()
        self._build_layout()
        self._apply_soft_style()
        self._load_backend_config_into_ui()
        self._update_texts()
        self.refresh_project()

    def _style_button(self, button, role="secondary", full_width=False):
        button.setProperty("tifRole", role)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumHeight(34)
        if full_width:
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _apply_button_roles(self):
        primary_buttons = [
            self.btn_import_tif,
            self.btn_import_amira,
            self.btn_export_training,
            self.btn_prepare_dataset,
            self.btn_train_backend,
            self.btn_import_prediction,
            self.btn_import_external_prediction_tif,
            self.btn_promote,
        ]
        secondary_buttons = [
            self.btn_start_center,
            self.btn_ask_agent,
            self.btn_undo,
            self.btn_redo,
            self.btn_save_edit,
            self.btn_copy_draft,
            self.btn_add_material,
            self.btn_edit_material,
            self.btn_save_backend,
        ]
        for button in primary_buttons:
            self._style_button(button, "primary", full_width=True)
        for button in secondary_buttons:
            self._style_button(button, "secondary", full_width=True)
        self._style_button(self.btn_delete_material, "danger", full_width=True)

    def _populate_label_role_combo(self):
        current = self.label_role_combo.currentData() if self.label_role_combo.count() else "manual_truth"
        self.label_role_combo.blockSignals(True)
        self.label_role_combo.clear()
        for role in ("manual_truth", "working_edit", "model_draft"):
            self.label_role_combo.addItem(tt(role, self.lang), role)
        index = self.label_role_combo.findData(current)
        self.label_role_combo.setCurrentIndex(index if index >= 0 else 0)
        self.label_role_combo.blockSignals(False)

    def change_language(self, lang):
        self.lang = lang
        self._update_texts()
        self.refresh_project()
        self.render_current_slice()

    def _update_texts(self):
        for title, label in getattr(self, "_panel_title_labels", {}).values():
            label.setText(tt(title, self.lang))
        for title, label in getattr(self, "_section_title_labels", {}).values():
            label.setText(tt(title, self.lang))
        self._populate_label_role_combo()
        if self.image_volume is None:
            if self.specimen_list.count():
                self.canvas.setText(tt("Working volume missing", self.lang))
            else:
                self.canvas.setText(tt("No specimens in this TIF project", self.lang))
        self.slice_prefix_label.setText(tt("Slice", self.lang))
        self.label_layer_label.setText(tt("Label layer", self.lang))
        self._update_label_role_help()
        self.overlay_label.setText(tt("Overlay", self.lang))
        self.brightness_label.setText(tt("Brightness", self.lang))
        self.contrast_label.setText(tt("Contrast", self.lang))
        self.brush_size_label.setText(tt("Brush size", self.lang))
        self.btn_import_tif.setText(tt("Import TIF stack", self.lang))
        self.btn_import_amira.setText(tt("Import AMIRA directory", self.lang))
        self.btn_undo.setText(tt("Undo", self.lang))
        self.btn_redo.setText(tt("Redo", self.lang))
        self.btn_save_edit.setText(tt("Save working edit", self.lang))
        self.auto_save_check.setText(tt("Auto-save edit", self.lang))
        self.btn_promote.setText(tt("Accept as manual truth", self.lang))
        self.btn_copy_draft.setText(tt("Copy model draft to working edit", self.lang))
        self.btn_add_material.setText(tt("Add material", self.lang))
        self.btn_edit_material.setText(tt("Edit material", self.lang))
        self.btn_delete_material.setText(tt("Delete material", self.lang))
        self.btn_export_training.setText(tt("Export train-ready volumes", self.lang))
        self.backend_id_label.setText(tt("Backend ID", self.lang))
        self.backend_display_label.setText(tt("Display name", self.lang))
        self.backend_python_label.setText(tt("Python", self.lang))
        self.backend_formats_label.setText(tt("Export formats", self.lang))
        self.backend_prepare_label.setText(tt("Prepare command", self.lang))
        self.backend_train_label.setText(tt("Train command", self.lang))
        self.backend_predict_label.setText(tt("Predict command", self.lang))
        self.backend_manifest_label.setText(tt("Model manifest", self.lang))
        self.btn_save_backend.setText(tt("Save backend settings", self.lang))
        self.btn_prepare_dataset.setText(tt("Prepare dataset", self.lang))
        self.btn_train_backend.setText(tt("Train backend", self.lang))
        self.btn_import_prediction.setText(tt("Import prediction", self.lang))
        self.btn_import_external_prediction_tif.setText(tt("Import external label TIF to draft", self.lang))
        self.btn_start_center.setText(tt("Start Center", self.lang))
        self.btn_ask_agent.setText(tt("Ask Agent", self.lang))
        self.material_table.setHorizontalHeaderLabels(
            [tt("ID", self.lang), tt("Name", self.lang), tt("Train", self.lang), tt("Color", self.lang)]
        )

    def get_agent_context(self):
        selected_material = self._selected_material()
        material_id = ""
        if isinstance(selected_material, dict):
            material_id = selected_material.get("id", "")
        recent_log = ""
        if hasattr(self, "log_console"):
            recent_log = "\n".join(self.log_console.toPlainText().splitlines()[-6:])
        return {
            "source_workbench": "tif_volume",
            "project_type": "tif_volume",
            "project_path": getattr(self.project, "current_project_path", "") or "",
            "active_specimen_id": self.current_specimen_id,
            "active_label_role": self.label_role_combo.currentData() or "",
            "selected_material_id": material_id,
            "recent_log_excerpt": recent_log,
        }

    def _backend_config_from_ui(self):
        return sanitize_tif_backend_config(
            {
                "backend_id": self.backend_id_edit.text(),
                "display_name": self.backend_display_edit.text(),
                "python_executable": self.backend_python_edit.text(),
                "export_formats": self.backend_formats_edit.text(),
                "prepare_dataset_command": self.backend_prepare_edit.text(),
                "train_command": self.backend_train_edit.text(),
                "predict_command": self.backend_predict_edit.text(),
                "model_manifest": self.backend_manifest_edit.text(),
            }
        )

    def _load_backend_config_into_ui(self):
        config = sanitize_tif_backend_config(self.backend_config)
        self.backend_id_edit.setText(config.get("backend_id", ""))
        self.backend_display_edit.setText(config.get("display_name", ""))
        self.backend_python_edit.setText(config.get("python_executable", "python"))
        self.backend_formats_edit.setText(config.get("export_formats", "ome_tiff,nrrd,mha,nifti"))
        self.backend_prepare_edit.setText(config.get("prepare_dataset_command", ""))
        self.backend_train_edit.setText(config.get("train_command", ""))
        self.backend_predict_edit.setText(config.get("predict_command", ""))
        self.backend_manifest_edit.setText(config.get("model_manifest", ""))

    def log(self, message):
        if not hasattr(self, "log_console"):
            return
        self.log_console.append(f"[{_now_log_time()}] {message}")

    def canvas_status_text(self, zoom_factor):
        if self.image_volume is None:
            return ""
        z_index = int(self.slice_slider.value()) + 1
        z_total = int(self.image_volume.shape[0])
        return f"Z {z_index}/{z_total} · {int(round(float(zoom_factor) * 100))}%"

    def move_slice(self, delta):
        if self.image_volume is None:
            return
        current = int(self.slice_slider.value())
        target = max(self.slice_slider.minimum(), min(self.slice_slider.maximum(), current + int(delta)))
        if target == current:
            return
        self._reset_canvas_view_on_next_render = True
        self.slice_slider.setValue(target)

    def on_slice_slider_changed(self):
        self._reset_canvas_view_on_next_render = True
        self.render_current_slice()

    def _label_role_help_text(self, role=None):
        role = role or self.label_role_combo.currentData()
        if role == "working_edit":
            return tt("Current edit is the editable working copy. Brush changes are saved here first.", self.lang)
        if role == "model_draft":
            return tt("Model draft is a read-only prediction candidate. Copy it to Current edit before manual correction.", self.lang)
        return tt("Manual truth is a read-only reference. Switch to Current edit before changing labels.", self.lang)

    def _update_label_role_help(self):
        if hasattr(self, "label_role_help_label"):
            self.label_role_help_label.setText(self._label_role_help_text())

    def _on_auto_save_toggled(self, checked):
        message = tt("Auto-save is on. Brush changes are saved shortly after editing.", self.lang) if checked else tt("Auto-save is off. Remember to save the current edit layer.", self.lang)
        self.training_status_label.setText(message)
        self.log(message)
        if checked and self.working_edit_dirty:
            self.auto_save_timer.start()
        elif not checked:
            self.auto_save_timer.stop()

    def _mark_working_edit_dirty(self):
        self.working_edit_dirty = True
        if self.auto_save_check.isChecked():
            self.auto_save_timer.start()

    def _confirm_discard_or_save_working_edit(self):
        self.auto_save_timer.stop()
        if not self.working_edit_dirty:
            return True
        reply = QMessageBox.question(
            self,
            tt("Unsaved working edit", self.lang),
            tt("Save changes to the current working_edit before continuing?", self.lang),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Save:
            return self.save_working_edit(show_message=True)
        self.working_edit_dirty = False
        self._dirty_edit_slices = set()
        if self.current_specimen_id:
            self._load_edit_volume()
        return True

    def save_backend_settings(self):
        self.backend_config = self._backend_config_from_ui()
        if self.config_manager is not None:
            self.config_manager.set("tif_backend", dict(self.backend_config))
            self.config_manager.save()
        self.training_status_label.setText(tt("Backend settings saved.", self.lang))
        self.log(tt("Backend settings saved.", self.lang))
        QMessageBox.information(self, tt("TIF backend", self.lang), tt("Backend settings saved.", self.lang))

    def _ensure_tif_project_open(self):
        if not self.project.current_project_path:
            QMessageBox.warning(
                self,
                tt("TIF data import", self.lang),
                tt("Please create or open a TIF project first.", self.lang),
            )
            return False
        return True

    def _select_specimen_after_import(self, specimen_id):
        for row in range(self.specimen_list.count()):
            item = self.specimen_list.item(row)
            if item and item.data(Qt.UserRole) == specimen_id:
                self.specimen_list.setCurrentRow(row)
                break

    def _set_tif_import_controls_enabled(self, enabled):
        for button in (self.btn_import_tif, self.btn_import_amira):
            button.setEnabled(bool(enabled))

    def _cleanup_tif_import_thread(self):
        self._set_tif_import_controls_enabled(True)
        if self._tif_import_progress is not None:
            self._tif_import_progress.close()
            self._tif_import_progress.deleteLater()
        self._tif_import_progress = None
        self._tif_import_worker = None
        self._tif_import_thread = None
        self._tif_import_specimen_id = ""

    def _on_tif_import_progress(self, current, total, message):
        if self._tif_import_progress is None:
            return
        maximum = max(1, int(total or 100))
        value = max(0, min(maximum, int(current or 0)))
        self._tif_import_progress.setMaximum(maximum)
        self._tif_import_progress.setValue(value)
        self._tif_import_progress.setLabelText(tt(message, self.lang))

    def _on_tif_import_finished(self, result):
        specimen_id = self._tif_import_specimen_id
        self.refresh_project()
        self._select_specimen_after_import(specimen_id)
        report_path = result.get("report_path", "") if isinstance(result, dict) else ""
        message = tt("Imported TIF stack for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        self.training_status_label.setText(message)
        self.log(message)
        thread = self._tif_import_thread
        self._cleanup_tif_import_thread()
        if thread is not None:
            thread.quit()

    def _on_tif_import_failed(self, message):
        thread = self._tif_import_thread
        self._cleanup_tif_import_thread()
        if thread is not None:
            thread.quit()
        QMessageBox.critical(self, tt("Import TIF Stack", self.lang), message)

    def import_tif_stack_dialog(self):
        if not self._ensure_tif_project_open():
            return
        if self._tif_import_thread is not None:
            QMessageBox.information(
                self,
                tt("Import TIF Stack", self.lang),
                tt("TIF import is already running.", self.lang),
            )
            return
        tif_path, _ = QFileDialog.getOpenFileName(
            self,
            tt("Import TIF Stack", self.lang),
            "",
            "TIF/TIFF (*.tif *.tiff)",
        )
        if not tif_path:
            return
        default_id = os.path.splitext(os.path.basename(tif_path))[0]
        specimen_id, ok = QInputDialog.getText(
            self,
            tt("Import TIF Stack", self.lang),
            tt("Specimen ID:", self.lang),
            text=default_id,
        )
        if not ok or not specimen_id:
            return
        self._set_tif_import_controls_enabled(False)
        self._tif_import_specimen_id = specimen_id
        self._tif_import_progress = QProgressDialog(
            tt("Importing TIF stack...", self.lang),
            "",
            0,
            100,
            self,
        )
        self._tif_import_progress.setWindowTitle(tt("Import TIF Stack", self.lang))
        self._tif_import_progress.setCancelButton(None)
        self._tif_import_progress.setAutoClose(False)
        self._tif_import_progress.setAutoReset(False)
        self._tif_import_progress.setWindowModality(Qt.WindowModal)
        self._tif_import_progress.show()

        self._tif_import_thread = QThread(self)
        self._tif_import_worker = TifImportWorker(self.project, tif_path, specimen_id)
        self._tif_import_worker.moveToThread(self._tif_import_thread)
        self._tif_import_thread.started.connect(self._tif_import_worker.run)
        self._tif_import_worker.progress.connect(self._on_tif_import_progress)
        self._tif_import_worker.finished.connect(self._on_tif_import_finished)
        self._tif_import_worker.failed.connect(self._on_tif_import_failed)
        self._tif_import_worker.finished.connect(self._tif_import_thread.quit)
        self._tif_import_worker.failed.connect(self._tif_import_thread.quit)
        self._tif_import_thread.finished.connect(self._tif_import_worker.deleteLater)
        self._tif_import_thread.finished.connect(self._tif_import_thread.deleteLater)
        self._tif_import_thread.start()

    def import_amira_directory_dialog(self):
        if not self._ensure_tif_project_open():
            return
        source_dir = QFileDialog.getExistingDirectory(self, tt("Import AMIRA Directory", self.lang))
        if not source_dir:
            return
        default_id = os.path.basename(os.path.normpath(source_dir))
        specimen_id, ok = QInputDialog.getText(
            self,
            tt("Import AMIRA Directory", self.lang),
            tt("Specimen ID:", self.lang),
            text=default_id,
        )
        if not ok or not specimen_id:
            return
        try:
            result = import_amira_directory(self.project, source_dir, specimen_id)
        except Exception as exc:
            QMessageBox.critical(self, tt("Import AMIRA Directory", self.lang), str(exc))
            return
        self.refresh_project()
        self._select_specimen_after_import(specimen_id)
        report_path = result.get("report_path", "")
        message = tt("Imported AMIRA directory for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        self.training_status_label.setText(message)
        self.log(message)

    def import_external_prediction_tif_dialog(self):
        if not self._ensure_tif_project_open():
            return
        if not self.current_specimen_id:
            QMessageBox.warning(
                self,
                tt("Import External Label TIF", self.lang),
                tt("Please select a specimen with a working volume first.", self.lang),
            )
            return
        specimen_id = self.current_specimen_id
        specimen = self.project.get_specimen(specimen_id, default=None)
        working = (specimen or {}).get("working_volume") or {}
        if not working.get("path") or not volume_sidecar_exists(self.project.to_absolute(working.get("path", ""))):
            QMessageBox.warning(
                self,
                tt("Import External Label TIF", self.lang),
                tt("Please select a specimen with a working volume first.", self.lang),
            )
            return
        tif_path, _ = QFileDialog.getOpenFileName(
            self,
            tt("Import External Label TIF", self.lang),
            "",
            "TIF/TIFF (*.tif *.tiff)",
        )
        if not tif_path:
            return
        prediction_id, ok = QInputDialog.getText(
            self,
            tt("Import External Label TIF", self.lang),
            tt("Prediction ID:", self.lang),
            text=default_prediction_id_for_tif(tif_path),
        )
        if not ok or not prediction_id:
            return
        source_model, ok = QInputDialog.getText(
            self,
            tt("Import External Label TIF", self.lang),
            tt("Source model:", self.lang),
            text="nnUNet",
        )
        if not ok:
            return
        try:
            result = import_external_prediction_tif(
                self.project,
                specimen_id,
                tif_path,
                prediction_id=prediction_id,
                source_model=source_model or "external_tif",
            )
        except Exception as exc:
            QMessageBox.critical(self, tt("Import External Label TIF", self.lang), str(exc))
            return
        self.refresh_project()
        self._select_specimen_after_import(specimen_id)
        index = self.label_role_combo.findData("model_draft")
        if index >= 0:
            self.label_role_combo.setCurrentIndex(index)
        self.load_specimen(specimen_id)
        report_path = result.get("report_path", "")
        message = tt("Imported external label TIF as model draft for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        self.training_status_label.setText(message)
        self.log(message)

    def _selected_specimen_ids_for_action(self, action):
        if action in {"prepare_dataset", "train"}:
            ready = [item.get("specimen_id") for item in self.project.list_train_ready_specimens()]
            if not ready:
                raise ValueError("No train-ready specimens are available.")
            return ready
        ids = [self.current_specimen_id] if self.current_specimen_id else []
        if not ids:
            ids = [item.get("specimen_id") for item in self.project.project_data.get("specimens", [])]
        if not ids:
            raise ValueError("No specimen is available for prediction.")
        return ids

    def run_backend_action(self, action):
        if not self._ensure_tif_project_open():
            return
        self.backend_config = self._backend_config_from_ui()
        if self.config_manager is not None:
            self.config_manager.set("tif_backend", dict(self.backend_config))
            self.config_manager.save()
        command_key = {
            "prepare_dataset": "prepare_dataset_command",
            "train": "train_command",
            "predict": "predict_command",
        }.get(action, "")
        if command_key and not self.backend_config.get(command_key, "").strip():
            QMessageBox.warning(self, tt("TIF backend", self.lang), tt("No command configured for this backend action.", self.lang))
            return
        try:
            specimen_ids = self._selected_specimen_ids_for_action(action)
            running_message = tt("Running {0}...", self.lang).format(action)
            self.training_status_label.setText(running_message)
            self.log(running_message)
            runner = TifBackendRunner(self.project, self.backend_config)
            result = runner.run_action(
                action,
                specimen_ids=specimen_ids,
                model_manifest=self.backend_config.get("model_manifest", ""),
            )
        except Exception as exc:
            message = tt("Action failed: {0}", self.lang).format(str(exc))
            self.training_status_label.setText(message)
            self.log(message)
            QMessageBox.warning(self, tt("TIF backend", self.lang), str(exc))
            return
        imported_id = self.current_specimen_id
        self.refresh_project()
        if action == "predict" and imported_id:
            self._select_specimen_after_import(imported_id)
            index = self.label_role_combo.findData("model_draft")
            if index >= 0:
                self.label_role_combo.setCurrentIndex(index)
        message = tt("Action finished: {0}\nRun: {1}", self.lang).format(action, result.get("run_dir", ""))
        self.training_status_label.setText(message)
        self.log(message)
        QMessageBox.information(
            self,
            tt("TIF backend", self.lang),
            message,
        )

    def _make_panel(self, title, object_name):
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setFrameShape(QFrame.NoFrame)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("tifPanelTitle")
        layout.addWidget(title_label)
        if not hasattr(self, "_panel_title_labels"):
            self._panel_title_labels = {}
        self._panel_title_labels[object_name] = (title, title_label)
        return panel, layout

    def _make_section(self, title, object_name):
        section = QFrame()
        section.setObjectName(object_name)
        section.setFrameShape(QFrame.NoFrame)
        section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("tifSectionTitle")
        layout.addWidget(title_label)
        if not hasattr(self, "_section_title_labels"):
            self._section_title_labels = {}
        self._section_title_labels[object_name] = (title, title_label)
        return section, layout

    def _build_layout(self):
        self._field_labels = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        top_bar = QFrame()
        top_bar.setObjectName("tifWorkbenchTopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(8)
        self.tif_top_context_label = QLabel("TIF Volume Workbench")
        self.tif_top_context_label.setObjectName("tifTopContextLabel")
        top_layout.addWidget(self.tif_top_context_label, 1)
        top_layout.addWidget(self.btn_start_center)
        top_layout.addWidget(self.btn_ask_agent)
        root.addWidget(top_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("tifWorkbenchSplitter")
        root.addWidget(splitter, 1)

        left, left_layout = self._make_panel("Specimens", "tifSpecimenPanel")
        left_layout.addWidget(self.specimen_list, 1)
        splitter.addWidget(left)

        center, center_layout = self._make_panel("Volume slices", "tifVolumePanel")
        canvas_shell = QFrame()
        canvas_shell.setObjectName("tifCanvasShell")
        canvas_layout = QVBoxLayout(canvas_shell)
        canvas_layout.setContentsMargins(6, 6, 6, 6)
        canvas_layout.addWidget(self.canvas, 1)
        center_layout.addWidget(canvas_shell, 1)
        slice_bar = QFrame()
        slice_bar.setObjectName("tifSliceBar")
        slice_row = QHBoxLayout()
        slice_row.setContentsMargins(10, 6, 10, 6)
        slice_row.addWidget(self.slice_prefix_label)
        slice_row.addWidget(self.slice_slider, 1)
        slice_row.addWidget(self.slice_label)
        slice_bar.setLayout(slice_row)
        center_layout.addWidget(slice_bar)
        splitter.addWidget(center)

        right, right_layout = self._make_panel("Volume controls", "tifControlPanel")
        right.setMinimumWidth(360)
        right.setMaximumWidth(520)

        right_scroll = QScrollArea()
        right_scroll.setObjectName("tifInspectorScroll")
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        inspector_body = QWidget()
        inspector_body.setObjectName("tifInspectorBody")
        inspector_layout = QVBoxLayout(inspector_body)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.setSpacing(10)
        right_layout.addWidget(right_scroll, 1)
        right_scroll.setWidget(inspector_body)

        import_section, import_layout = self._make_section("Data import", "tifImportSection")
        import_button_row = QHBoxLayout()
        import_button_row.addWidget(self.btn_import_tif)
        import_button_row.addWidget(self.btn_import_amira)
        import_layout.addLayout(import_button_row)
        inspector_layout.addWidget(import_section)

        annotation_section, annotation_layout = self._make_section("Annotation tools", "tifAnnotationSection")
        controls = QGridLayout()
        controls.setHorizontalSpacing(10)
        controls.setVerticalSpacing(8)
        self.label_layer_label = QLabel("Label layer")
        self.overlay_label = QLabel("Overlay")
        self.brightness_label = QLabel("Brightness")
        self.contrast_label = QLabel("Contrast")
        self.brush_size_label = QLabel("Brush size")
        controls.addWidget(self.label_layer_label, 0, 0)
        controls.addWidget(self.label_role_combo, 0, 1)
        controls.addWidget(self.overlay_label, 1, 0)
        controls.addWidget(self.opacity_slider, 1, 1)
        controls.addWidget(self.brightness_label, 2, 0)
        controls.addWidget(self.brightness_slider, 2, 1)
        controls.addWidget(self.contrast_label, 3, 0)
        controls.addWidget(self.contrast_slider, 3, 1)
        controls.addWidget(self.brush_size_label, 4, 0)
        controls.addWidget(self.brush_size_slider, 4, 1)
        annotation_layout.addLayout(controls)
        annotation_layout.addWidget(self.label_role_help_label)
        button_row = QHBoxLayout()
        button_row.addWidget(self.btn_undo)
        button_row.addWidget(self.btn_redo)
        annotation_layout.addLayout(button_row)
        annotation_layout.addWidget(self.auto_save_check)
        annotation_layout.addWidget(self.btn_save_edit)
        annotation_layout.addWidget(self.btn_promote)
        annotation_layout.addWidget(self.btn_copy_draft)
        inspector_layout.addWidget(annotation_section)

        material_section, material_layout = self._make_section("Material map", "tifMaterialSection")
        material_button_row = QHBoxLayout()
        material_button_row.addWidget(self.btn_add_material)
        material_button_row.addWidget(self.btn_edit_material)
        material_button_row.addWidget(self.btn_delete_material)
        material_layout.addLayout(material_button_row)
        material_layout.addWidget(self.material_table)
        inspector_layout.addWidget(material_section)

        training_section, training_layout = self._make_section("Model training", "tifTrainingSection")
        training_layout.addWidget(self.btn_export_training)
        backend_button_row = QHBoxLayout()
        backend_button_row.addWidget(self.btn_prepare_dataset)
        backend_button_row.addWidget(self.btn_train_backend)
        backend_button_row.addWidget(self.btn_import_prediction)
        training_layout.addLayout(backend_button_row)
        training_layout.addWidget(self.btn_import_external_prediction_tif)
        training_layout.addWidget(self.training_status_label)
        inspector_layout.addWidget(training_section)

        backend_section, backend_layout = self._make_section("Model configuration", "tifBackendSection")
        backend_form = QFormLayout()
        backend_form.setHorizontalSpacing(8)
        backend_form.setVerticalSpacing(6)
        self.backend_id_label = QLabel("Backend ID")
        self.backend_display_label = QLabel("Display name")
        self.backend_python_label = QLabel("Python")
        self.backend_formats_label = QLabel("Export formats")
        self.backend_prepare_label = QLabel("Prepare command")
        self.backend_train_label = QLabel("Train command")
        self.backend_predict_label = QLabel("Predict command")
        self.backend_manifest_label = QLabel("Model manifest")
        backend_form.addRow(self.backend_id_label, self.backend_id_edit)
        backend_form.addRow(self.backend_display_label, self.backend_display_edit)
        backend_form.addRow(self.backend_python_label, self.backend_python_edit)
        backend_form.addRow(self.backend_formats_label, self.backend_formats_edit)
        backend_form.addRow(self.backend_prepare_label, self.backend_prepare_edit)
        backend_form.addRow(self.backend_train_label, self.backend_train_edit)
        backend_form.addRow(self.backend_predict_label, self.backend_predict_edit)
        backend_form.addRow(self.backend_manifest_label, self.backend_manifest_edit)
        backend_layout.addLayout(backend_form)
        backend_layout.addWidget(self.btn_save_backend)
        inspector_layout.addWidget(backend_section)

        status_section, status_layout = self._make_section("Specimen status", "tifStatusSection")
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.metadata_label)
        inspector_layout.addWidget(status_section)
        inspector_layout.addStretch(1)

        log_section, log_layout = self._make_section("Workbench log", "tifLogSection")
        log_layout.addWidget(self.log_console)
        right_layout.addWidget(log_section)
        splitter.addWidget(right)

        splitter.setSizes([230, 900, 420])

    def _apply_soft_style(self):
        self.setStyleSheet(
            """
            QWidget#tifWorkbenchRoot {
                background: #15191D;
            }
            QFrame#tifSpecimenPanel,
            QFrame#tifVolumePanel,
            QFrame#tifControlPanel,
            QFrame#tifWorkbenchTopBar {
                background: #1B2024;
                border: 1px solid #2F3A40;
                border-radius: 12px;
            }
            QLabel#tifTopContextLabel {
                color: #DCE4E8;
                font-weight: 700;
                border: none;
            }
            QFrame#tifImportSection,
            QFrame#tifAnnotationSection,
            QFrame#tifMaterialSection,
            QFrame#tifTrainingSection,
            QFrame#tifBackendSection,
            QFrame#tifStatusSection,
            QFrame#tifLogSection {
                background: #20262B;
                border: 1px solid #334047;
                border-radius: 12px;
            }
            QWidget#tifInspectorBody {
                background: transparent;
            }
            QScrollArea#tifInspectorScroll {
                background: transparent;
                border: none;
            }
            QLabel#tifPanelTitle {
                color: #DCE4E8;
                font-weight: 700;
                padding-bottom: 4px;
                border: none;
            }
            QLabel#tifSectionTitle {
                color: #B9C5CA;
                font-weight: 700;
                margin-top: 8px;
                border: none;
            }
            QFrame#tifCanvasShell {
                background: #0A0D0F;
                border: 1px solid #2F3A40;
                border-radius: 12px;
            }
            QLabel#tifSliceCanvas {
                background: #07090A;
                color: #859098;
                border: none;
                border-radius: 10px;
            }
            QFrame#tifSliceBar {
                background: #182023;
                border: 1px solid #2B363B;
                border-radius: 12px;
            }
            QListWidget#tifSpecimenList,
            QTableWidget#tifMaterialTable {
                background: #111619;
                alternate-background-color: #171D20;
                border: 1px solid #2D373D;
                border-radius: 10px;
                padding: 2px;
                selection-background-color: #31525D;
                selection-color: #F4FAFC;
            }
            QTableWidget#tifMaterialTable::item,
            QListWidget#tifSpecimenList::item {
                min-height: 24px;
                padding: 4px;
                border: none;
            }
            QTableWidget#tifMaterialTable QHeaderView::section {
                background: #222A2F;
                color: #D7E0E4;
                border: none;
                border-right: 1px solid #303B42;
                padding: 5px 6px;
                font-weight: 700;
            }
            QLineEdit {
                background: #111619;
                color: #DCE4E8;
                border: 1px solid #2D373D;
                border-radius: 8px;
                padding: 4px 6px;
                selection-background-color: #31525D;
            }
            QPushButton {
                background: #26323A;
                color: #EEF6F8;
                border: 1px solid #4A5A63;
                border-radius: 10px;
                padding: 8px 12px;
                font-weight: 700;
                min-height: 18px;
            }
            QPushButton:hover {
                background: #31414B;
                border-color: #6C828E;
            }
            QPushButton:pressed {
                background: #1C252B;
                border-color: #8CA4AF;
                padding-top: 9px;
                padding-bottom: 7px;
            }
            QPushButton:disabled {
                background: #1A2024;
                color: #6C777D;
                border-color: #2B3338;
            }
            QPushButton[tifRole="primary"] {
                background: #2D6472;
                border: 1px solid #67A8B8;
                color: #F5FCFF;
            }
            QPushButton[tifRole="primary"]:hover {
                background: #37788A;
                border-color: #91C7D3;
            }
            QPushButton[tifRole="primary"]:pressed {
                background: #245563;
                border-color: #B2DCE4;
            }
            QPushButton[tifRole="secondary"] {
                background: #253038;
                border: 1px solid #4C5B64;
                color: #DCE7EB;
            }
            QPushButton[tifRole="secondary"]:hover {
                background: #303D46;
                border-color: #71848F;
            }
            QPushButton[tifRole="danger"] {
                background: #3B2528;
                border: 1px solid #8D4B55;
                color: #FFE9EC;
            }
            QPushButton[tifRole="danger"]:hover {
                background: #512D33;
                border-color: #B66974;
            }
            QPushButton[tifRole="danger"]:pressed {
                background: #2D1C20;
                border-color: #D98A94;
            }
            QTextEdit#tifLogConsole {
                background: #101518;
                color: #B8C4CA;
                border: 1px solid #2A353B;
                border-radius: 10px;
                padding: 6px;
            }
            QLabel#tifLayerHelpText {
                color: #B8C4CA;
                background: #12191D;
                border: 1px solid #2C3840;
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel#tifStatusText,
            QLabel#tifMetadataText,
            QLabel#tifTrainingStatusText {
                color: #AEBAC0;
                border: none;
            }
            QPushButton#tifExportTrainingButton,
            QPushButton#tifPrepareDatasetButton,
            QPushButton#tifTrainBackendButton,
            QPushButton#tifImportPredictionButton,
            QPushButton#tifImportStackButton,
            QPushButton#tifImportAmiraButton {
                font-weight: 700;
            }
            """
        )

    def set_project_manager(self, project_manager):
        if not self._confirm_discard_or_save_working_edit():
            return
        self.close_project(prompt_unsaved=False)
        self.project = project_manager
        self.refresh_project()

    def set_config_manager(self, config_manager):
        self.config_manager = config_manager
        config = self.config_manager.get("tif_backend", DEFAULT_TIF_BACKEND_CONFIG) if self.config_manager is not None else DEFAULT_TIF_BACKEND_CONFIG
        self.backend_config = sanitize_tif_backend_config(config)
        self._load_backend_config_into_ui()

    def close_project(self, prompt_unsaved=True):
        if prompt_unsaved and not self._confirm_discard_or_save_working_edit():
            return False
        self.image_volume = None
        self.label_volume = None
        self.material_map = {}
        self.material_colors = {}
        self.current_specimen_id = ""
        self.edit_volume = None
        self._dirty_edit_slices = set()
        self.auto_save_timer.stop()
        self.working_edit_dirty = False
        self.undo_stack = []
        self.redo_stack = []
        self.canvas.clear()
        self.canvas.setText(tt("No TIF volume loaded", self.lang))
        return True

    def closeEvent(self, event):
        if not self.close_project(prompt_unsaved=True):
            event.ignore()
            return
        super().closeEvent(event)

    def refresh_project(self):
        previous_id = self.current_specimen_id
        self.specimen_list.clear()
        for specimen in self.project.project_data.get("specimens", []):
            item = QListWidgetItem(self._format_specimen_label(specimen))
            item.setData(Qt.UserRole, specimen.get("specimen_id", ""))
            self.specimen_list.addItem(item)
        if self.specimen_list.count():
            target_row = 0
            if previous_id:
                for row in range(self.specimen_list.count()):
                    item = self.specimen_list.item(row)
                    if item and item.data(Qt.UserRole) == previous_id:
                        target_row = row
                        break
            self.specimen_list.setCurrentRow(target_row)
        else:
            self.current_specimen_id = ""
            self.canvas.setText(tt("No specimens in this TIF project", self.lang))
            self.status_label.setText("")
            self.metadata_label.setText("")

    def _format_specimen_label(self, specimen):
        status = specimen.get("review_status", "not_started")
        train = tt("train-ready", self.lang) if specimen.get("train_ready") else tt("not train-ready", self.lang)
        return f"{specimen.get('display_name') or specimen.get('specimen_id')} ({status}, {train})"

    def _on_specimen_selected(self, current, previous=None):
        if current is None:
            return
        if self._loading_specimen:
            return
        if previous is not None and self.working_edit_dirty:
            if not self._confirm_discard_or_save_working_edit():
                self._loading_specimen = True
                try:
                    self.specimen_list.setCurrentItem(previous)
                finally:
                    self._loading_specimen = False
                return
        specimen_id = current.data(Qt.UserRole)
        self.load_specimen(specimen_id)

    def load_specimen(self, specimen_id):
        if specimen_id != self.current_specimen_id and self.working_edit_dirty:
            if not self._confirm_discard_or_save_working_edit():
                return
        specimen = self.project.get_specimen(specimen_id, default=None)
        if specimen is None:
            return
        self._loading_specimen = True
        try:
            self.auto_save_timer.stop()
            self.current_specimen_id = specimen_id
            self.image_volume = None
            self.label_volume = None
            self.edit_volume = None
            self.working_edit_dirty = False
            self._dirty_edit_slices = set()
            self.material_map = {}
            self.material_colors = {}
            self.undo_stack = []
            self.redo_stack = []

            image_path = self.project.to_absolute((specimen.get("working_volume") or {}).get("path", ""))
            if image_path and volume_sidecar_exists(image_path):
                self.image_volume = load_volume_sidecar(image_path, mmap_mode="r")
                z_count = int(self.image_volume.shape[0])
                self.slice_slider.setRange(0, max(0, z_count - 1))
                self.slice_slider.setValue(min(self.slice_slider.value(), max(0, z_count - 1)))
                self._reset_canvas_view_on_next_render = True
            else:
                self.slice_slider.setRange(0, 0)
                self.canvas.reset_view()

            material_path = self.project.to_absolute(specimen.get("material_map", ""))
            if material_path and os.path.exists(material_path):
                self.material_map = read_material_map(material_path)
                self.material_colors = {
                    int(item["id"]): QColor(str(item.get("color", "#000000")))
                    for item in self.material_map.get("materials", [])
                }
            self._populate_material_table()
            self._reload_label_volume()
            self._load_edit_volume()
            self._update_status_labels(specimen)
            self.render_current_slice()
        finally:
            self._loading_specimen = False

    def _populate_material_table(self):
        materials = self.material_map.get("materials", []) if isinstance(self.material_map, dict) else []
        self.material_table.setRowCount(len(materials))
        for row, material in enumerate(materials):
            self.material_table.setItem(row, 0, QTableWidgetItem(str(material.get("id", ""))))
            self.material_table.setItem(row, 1, QTableWidgetItem(str(material.get("display_name") or material.get("name") or "")))
            self.material_table.setItem(row, 2, QTableWidgetItem(tt("yes", self.lang) if material.get("trainable") else tt("no", self.lang)))
            color_item = QTableWidgetItem(str(material.get("color", "")))
            try:
                color_item.setBackground(QColor(str(material.get("color", "#000000"))))
            except Exception:
                pass
            self.material_table.setItem(row, 3, color_item)
        self.material_table.resizeColumnsToContents()
        if self.material_table.rowCount() > 1:
            self.material_table.selectRow(1)
        elif self.material_table.rowCount() == 1:
            self.material_table.selectRow(0)

    def _selected_material(self):
        items = self.material_table.selectedItems()
        if not items:
            return None
        row = items[0].row()
        try:
            material_id = int(self.material_table.item(row, 0).text())
        except Exception:
            return None
        for material in self.material_map.get("materials", []):
            if int(material.get("id", -1)) == material_id:
                return dict(material)
        return None

    def _material_map_path(self):
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return ""
        return self.project.to_absolute(specimen.get("material_map", ""))

    def _save_material_map(self):
        path = self._material_map_path()
        if not path:
            return
        self.material_map = write_material_map(path, self.material_map, source=self.material_map.get("source", "manual"))
        self.material_colors = {
            int(item["id"]): QColor(str(item.get("color", "#000000")))
            for item in self.material_map.get("materials", [])
        }
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is not None:
            self._update_status_labels(specimen)
        self._populate_material_table()
        self.render_current_slice()

    def add_material(self):
        if not self.current_specimen_id:
            return
        dialog = MaterialEditorDialog(next_id=next_material_id(self.material_map), parent=self, lang=self.lang)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.material_map = upsert_material(self.material_map, dialog.get_material())
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(self, tt("Material map", self.lang), str(exc))

    def edit_selected_material(self):
        material = self._selected_material()
        if material is None:
            return
        dialog = MaterialEditorDialog(material=material, parent=self, lang=self.lang)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.material_map = upsert_material(self.material_map, dialog.get_material())
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(self, tt("Material map", self.lang), str(exc))

    def delete_selected_material(self):
        material = self._selected_material()
        if material is None:
            return
        material_id = int(material.get("id", -1))
        if material_id == 0:
            QMessageBox.warning(self, tt("Material map", self.lang), tt("Background material cannot be deleted.", self.lang))
            return
        if self._material_id_is_used(material_id):
            QMessageBox.warning(self, tt("Material map", self.lang), tt("Material {0} is still used by a label volume.", self.lang).format(material_id))
            return
        reply = QMessageBox.question(
            self,
            tt("Material map", self.lang),
            tt("Delete material {0} ({1})?", self.lang).format(material_id, material.get("display_name", material.get("name", ""))),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.material_map = remove_material(self.material_map, material_id)
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(self, tt("Material map", self.lang), str(exc))

    def _material_id_is_used(self, material_id):
        arrays = []
        if self.edit_volume is not None:
            arrays.append(self.edit_volume)
        if self.label_volume is not None:
            arrays.append(self.label_volume)
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is not None:
            label_records = []
            labels = specimen.get("labels") or {}
            label_records.extend([labels.get("manual_truth") or {}, labels.get("working_edit") or {}])
            label_records.extend(labels.get("model_drafts") or [])
            for record in label_records:
                path = self.project.to_absolute((record or {}).get("path", ""))
                if path and volume_sidecar_exists(path):
                    try:
                        arrays.append(load_volume_sidecar(path, mmap_mode="r"))
                    except Exception:
                        pass
        for array in arrays:
            try:
                z_count = int(array.shape[0]) if getattr(array, "ndim", 0) == 3 else 0
                for z_index in range(z_count):
                    if np.any(np.asarray(array[z_index]) == int(material_id)):
                        return True
            except Exception:
                continue
        return False

    def _on_material_selected(self):
        items = self.material_table.selectedItems()
        if not items:
            return
        row = items[0].row()
        try:
            self.current_material_id = int(self.material_table.item(row, 0).text())
        except Exception:
            self.current_material_id = 0

    def _reload_label_volume(self):
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        self.label_volume = None
        self._update_label_role_help()
        if specimen is None:
            return
        role = self.label_role_combo.currentData()
        label_record = None
        labels = specimen.get("labels") or {}
        if role in {"manual_truth", "working_edit"}:
            label_record = labels.get(role) or {}
        elif role == "model_draft":
            drafts = labels.get("model_drafts") or []
            label_record = drafts[-1] if drafts else {}
        label_path = self.project.to_absolute((label_record or {}).get("path", ""))
        if label_path and volume_sidecar_exists(label_path):
            self.label_volume = load_volume_sidecar(label_path, mmap_mode="r")
        self.render_current_slice()

    def _load_edit_volume(self):
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        self.edit_volume = None
        if specimen is None:
            return
        edit_path = self.project.to_absolute(((specimen.get("labels") or {}).get("working_edit") or {}).get("path", ""))
        if edit_path and volume_sidecar_exists(edit_path):
            self.edit_volume = load_volume_sidecar(edit_path, mmap_mode="c")

    def _ensure_working_edit_volume(self):
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return False
        labels = specimen.setdefault("labels", {})
        edit_record = labels.get("working_edit") or {}
        edit_path = self.project.to_absolute(edit_record.get("path", ""))
        if edit_path and volume_sidecar_exists(edit_path):
            if self.edit_volume is None:
                self.edit_volume = load_volume_sidecar(edit_path, mmap_mode="c")
            return self.edit_volume is not None
        image_path = self.project.to_absolute((specimen.get("working_volume") or {}).get("path", ""))
        if not image_path or not volume_sidecar_exists(image_path):
            return False
        edit_rel = os.path.join(self.project.specimen_dir(self.current_specimen_id), "labels", "working_edit.ome.zarr").replace("\\", "/")
        edit_abs = self.project.to_absolute(edit_rel)
        metadata = create_empty_label_sidecar_like(image_path, edit_abs, role="working_edit", write_ome_zarr=False)
        self.project.register_label_volume(
            self.current_specimen_id,
            "working_edit",
            edit_rel,
            metadata["shape_zyx"],
            metadata["dtype"],
            status="empty_edit",
            spacing_zyx=metadata.get("spacing_zyx"),
            spacing_unit=metadata.get("spacing_unit", "micrometer"),
            orientation=metadata.get("orientation", "unknown"),
            fmt=metadata.get("format", ""),
            save=False,
        )
        self.project.save_project()
        self.edit_volume = load_volume_sidecar(edit_abs, mmap_mode="c")
        return self.edit_volume is not None

    def _update_status_labels(self, specimen):
        readiness = self.project.evaluate_train_ready(specimen.get("specimen_id"))
        self.status_label.setText(
            f"{tt('Status', self.lang)}: {specimen.get('review_status', 'not_started')}\n"
            f"{tt('Train-ready', self.lang)}: {tt('yes', self.lang) if readiness['train_ready'] else tt('no', self.lang)}\n"
            f"{tt('Reasons', self.lang)}: {', '.join(readiness['reasons']) if readiness['reasons'] else '-'}"
        )
        working = specimen.get("working_volume") or {}
        self.metadata_label.setText(
            f"{tt('Shape Z/Y/X', self.lang)}: {working.get('shape_zyx', [])}\n"
            f"{tt('dtype', self.lang)}: {working.get('dtype', '')}\n"
            f"{tt('spacing Z/Y/X', self.lang)}: {working.get('spacing_zyx', [])} {working.get('spacing_unit', '')}\n"
            f"{tt('modality', self.lang)}: {specimen.get('modality', 'unknown')}"
        )

    def render_current_slice(self):
        if self.image_volume is None:
            if not self.current_specimen_id and not self.specimen_list.count():
                self.canvas.setText(tt("No specimens in this TIF project", self.lang))
            else:
                self.canvas.setText(tt("Working volume missing", self.lang))
            return
        z_index = int(self.slice_slider.value())
        z_index = max(0, min(z_index, int(self.image_volume.shape[0]) - 1))
        self.slice_label.setText(f"{z_index + 1} / {int(self.image_volume.shape[0])}")
        image_slice = np.asarray(self.image_volume[z_index])
        label_slice = None
        if self.label_volume is not None and self.label_volume.shape == self.image_volume.shape:
            label_slice = np.asarray(self.label_volume[z_index])
        if self.label_role_combo.currentData() == "working_edit" and self.edit_volume is not None and self.edit_volume.shape == self.image_volume.shape:
            label_slice = np.asarray(self.edit_volume[z_index])
        pixmap = self._render_slice_pixmap(image_slice, label_slice)
        reset_view = bool(getattr(self, "_reset_canvas_view_on_next_render", False))
        self._reset_canvas_view_on_next_render = False
        self.canvas.set_slice_pixmap(pixmap, reset_view=reset_view)

    def paint_at_widget_position(self, x, y, erase=False):
        if self.image_volume is None:
            return
        if self.edit_volume is None and not self._ensure_working_edit_volume():
            return
        role = self.label_role_combo.currentData()
        if role != "working_edit":
            if role == "model_draft":
                message = tt("Cannot paint on model draft. Copy model draft to Current edit first.", self.lang)
            else:
                message = tt("Cannot paint on this label layer. Switch to Current edit first.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
            return
        z_index = int(self.slice_slider.value())
        height, width = self.image_volume.shape[1], self.image_volume.shape[2]
        pixel = self._widget_to_image_pixel(x, y, width, height)
        if pixel is None:
            return
        px, py = pixel
        radius = max(1, int(self.brush_size_slider.value()))
        self._push_undo()
        yy, xx = np.ogrid[:height, :width]
        mask = (xx - px) ** 2 + (yy - py) ** 2 <= radius ** 2
        self.edit_volume[z_index][mask] = 0 if erase else int(self.current_material_id)
        self._dirty_edit_slices.add(z_index)
        self._mark_working_edit_dirty()
        self.render_current_slice()

    def _widget_to_image_pixel(self, x, y, image_width, image_height):
        pixel = self.canvas.widget_to_image_pixel(x, y)
        if pixel is None:
            return None
        px, py = pixel
        return max(0, min(image_width - 1, px)), max(0, min(image_height - 1, py))

    def _push_undo(self):
        if self.edit_volume is None:
            return
        z_index = int(self.slice_slider.value())
        self.undo_stack.append((z_index, self.edit_volume[z_index].copy()))
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack or self.edit_volume is None:
            return
        z_index, old_slice = self.undo_stack.pop()
        self.redo_stack.append((z_index, self.edit_volume[z_index].copy()))
        self.edit_volume[z_index] = old_slice
        self._dirty_edit_slices.add(z_index)
        self.slice_slider.setValue(z_index)
        self._mark_working_edit_dirty()
        self.render_current_slice()

    def redo(self):
        if not self.redo_stack or self.edit_volume is None:
            return
        z_index, redo_slice = self.redo_stack.pop()
        self.undo_stack.append((z_index, self.edit_volume[z_index].copy()))
        self.edit_volume[z_index] = redo_slice
        self._dirty_edit_slices.add(z_index)
        self.slice_slider.setValue(z_index)
        self._mark_working_edit_dirty()
        self.render_current_slice()

    def save_working_edit(self, show_message=True, reason="manual"):
        if self._saving_working_edit:
            return True
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None or self.edit_volume is None:
            return False
        edit_path = self.project.to_absolute(((specimen.get("labels") or {}).get("working_edit") or {}).get("path", ""))
        if not edit_path:
            return False
        self._saving_working_edit = True
        self.auto_save_timer.stop()
        try:
            self.label_volume = None
            target = load_volume_sidecar(edit_path, mmap_mode="r+")
            if self._dirty_edit_slices:
                for z_index in sorted(self._dirty_edit_slices):
                    if 0 <= int(z_index) < int(target.shape[0]):
                        target[int(z_index)] = self.edit_volume[int(z_index)]
            metadata = flush_volume_array(edit_path, target)
            specimen["labels"]["working_edit"]["dtype"] = metadata["dtype"]
            specimen["labels"]["working_edit"]["status"] = "in_progress"
            specimen["review_status"] = "in_progress"
            specimen["train_ready"] = False
            self.project.save_project()
            self.working_edit_dirty = False
            self._dirty_edit_slices = set()
            self.edit_volume = load_volume_sidecar(edit_path, mmap_mode="c")
            if self.label_role_combo.currentData() == "working_edit":
                self.label_volume = load_volume_sidecar(edit_path, mmap_mode="r")
            else:
                self._reload_label_volume()
            self._update_status_labels(specimen)
        except Exception as exc:
            self.working_edit_dirty = True
            QMessageBox.warning(self, tt("Unsaved working edit", self.lang), str(exc))
            return False
        finally:
            self._saving_working_edit = False
        if show_message:
            message = tt("Auto-saved working edit.", self.lang) if reason == "auto_save" else tt("Working edit saved.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
        return True

    def promote_working_edit(self):
        if not self.current_specimen_id:
            return
        if not self.save_working_edit(show_message=False):
            return
        reply = QMessageBox.question(
            self,
            tt("Accept working edit", self.lang),
            tt("Promote the current working_edit layer to manual_truth for training?", self.lang),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.project.promote_working_edit_to_manual_truth(self.current_specimen_id)
        self._reload_label_volume()
        specimen = self.project.get_specimen(self.current_specimen_id)
        self._update_status_labels(specimen)
        self.refresh_project()

    def copy_latest_model_draft_to_working_edit(self):
        if not self.current_specimen_id:
            return
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        drafts = ((specimen or {}).get("labels") or {}).get("model_drafts") or []
        if not drafts:
            QMessageBox.warning(
                self,
                tt("TIF backend", self.lang),
                tt("No model draft is available for this specimen.", self.lang),
            )
            return
        try:
            self.project.copy_label_layer_to_working_edit(self.current_specimen_id, source_role="model_draft")
        except Exception as exc:
            QMessageBox.warning(self, tt("TIF backend", self.lang), str(exc))
            return
        index = self.label_role_combo.findData("working_edit")
        if index >= 0:
            self.label_role_combo.setCurrentIndex(index)
        self.load_specimen(self.current_specimen_id)
        message = tt("Copied latest model draft into working_edit.", self.lang)
        self.training_status_label.setText(message)
        self.log(message)

    def export_training_dataset(self):
        if not self.project.current_project_path:
            QMessageBox.warning(self, tt("TIF training handoff", self.lang), tt("Please create or open a TIF project first.", self.lang))
            return
        output_dir = QFileDialog.getExistingDirectory(self, tt("Export train-ready TIF volumes", self.lang))
        if not output_dir:
            return
        formats = [
            item.strip()
            for item in self.backend_formats_edit.text().split(",")
            if item.strip()
        ]
        try:
            result = export_tif_training_dataset(
                self.project,
                output_dir,
                formats=formats or ["ome_tiff", "nrrd", "mha", "nifti"],
                require_train_ready=True,
            )
        except Exception as exc:
            QMessageBox.warning(self, tt("TIF training handoff", self.lang), str(exc))
            message = tt("Export failed: {0}", self.lang).format(str(exc))
            self.training_status_label.setText(message)
            self.log(message)
            return
        manifest_path = result.get("manifest_path", "")
        exported_count = result.get("exported_count", 0)
        message = tt("Exported {0} train-ready specimen(s).\nManifest: {1}", self.lang).format(exported_count, manifest_path)
        self.training_status_label.setText(message)
        self.log(message)
        QMessageBox.information(
            self,
            tt("TIF training handoff", self.lang),
            message,
        )

    def _render_slice_pixmap(self, image_slice, label_slice=None):
        gray = self._normalize_image(image_slice)
        rgb = np.stack([gray, gray, gray], axis=-1)
        if label_slice is not None and self.opacity_slider.value() > 0:
            alpha = self.opacity_slider.value() / 100.0
            mask = label_slice > 0
            if np.any(mask):
                overlay = np.zeros_like(rgb)
                for material_id in np.unique(label_slice[mask]):
                    color = self.material_colors.get(int(material_id), QColor("#ff4b4b"))
                    overlay[label_slice == material_id] = [color.red(), color.green(), color.blue()]
                rgb[mask] = ((1.0 - alpha) * rgb[mask].astype(np.float32) + alpha * overlay[mask].astype(np.float32)).astype(np.uint8)
        height, width = rgb.shape[:2]
        rgb = np.ascontiguousarray(rgb)
        image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format_RGB888).copy()
        return QPixmap.fromImage(image)

    def _normalize_image(self, image_slice):
        data = np.asarray(image_slice, dtype=np.float32)
        finite = data[np.isfinite(data)]
        if finite.size == 0:
            return np.zeros(data.shape, dtype=np.uint8)
        low = float(np.percentile(finite, 1))
        high = float(np.percentile(finite, 99))
        if high <= low:
            low = float(np.min(finite))
            high = float(np.max(finite))
        if high <= low:
            return np.zeros(data.shape, dtype=np.uint8)
        normalized = (data - low) / (high - low)
        contrast = self.contrast_slider.value() / 10.0
        brightness = self.brightness_slider.value() / 100.0
        normalized = (normalized - 0.5) * contrast + 0.5 + brightness
        return np.clip(normalized * 255.0, 0, 255).astype(np.uint8)
