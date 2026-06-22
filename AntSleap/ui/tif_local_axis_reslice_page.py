import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.core.tif_local_axis_reslice import (
        build_reslice_preview,
        compute_local_frame,
        create_editable_axis_from_source,
        export_part_reslice,
        source_z_axis_for_part,
        validate_roll_reference_pair,
    )
    from AntSleap.core.tif_local_axis_signal import analyze_source_z_signal, compute_source_z_signal
    from AntSleap.core.tif_volume_io import load_volume_sidecar, volume_sidecar_exists
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_local_axis_reslice import (
        build_reslice_preview,
        compute_local_frame,
        create_editable_axis_from_source,
        export_part_reslice,
        source_z_axis_for_part,
        validate_roll_reference_pair,
    )
    from core.tif_local_axis_signal import analyze_source_z_signal, compute_source_z_signal
    from core.tif_volume_io import load_volume_sidecar, volume_sidecar_exists


LOCAL_AXIS_TRANSLATIONS = {
    "zh": {
        "Local Axis Reslice": "局部轴重切片",
        "Current part": "当前部位",
        "Source reference": "原始方向参考",
        "Editable output axis": "可编辑输出轴",
        "Roll reference": "Roll 参照",
        "AI proposal": "AI 建议",
        "Preview": "预览",
        "Export": "导出",
        "Training quality": "训练质量",
        "Specimen": "标本",
        "Part": "部位",
        "Shape": "尺寸",
        "Spacing": "体素间距",
        "Parent bbox": "父体 bbox",
        "Mask": "Mask",
        "available": "可用",
        "missing": "缺失",
        "Source Z axis is locked and used only as a direction reference.": "原始 Z 轴已锁定，只作为原始切片方向参考。",
        "Copy source Z axis": "复制原始 Z 轴",
        "Reslice ID": "重切片编号",
        "Template": "模板",
        "Origin z,y,x": "中心点 z,y,x",
        "Output axis start z,y,x": "输出轴起点 z,y,x",
        "Output axis end z,y,x": "输出轴终点 z,y,x",
        "Roll point A role": "Roll 点 A 角色",
        "Roll point A z,y,x": "Roll 点 A z,y,x",
        "Roll point B role": "Roll 点 B 角色",
        "Roll point B z,y,x": "Roll 点 B z,y,x",
        "Output shape z,y,x": "输出尺寸 z,y,x",
        "Proposal": "建议项",
        "No proposal": "无建议项",
        "Accept proposal": "接受建议",
        "Needs review": "需要复核",
        "Reject proposal": "拒绝建议",
        "Generate preview": "生成预览",
        "Export reslice": "导出重切片",
        "Usable for training": "可用于训练",
        "Hard case": "困难样本",
        "Reviewer notes": "复核备注",
        "MPR point picking": "MPR 点选",
        "Plane": "平面",
        "Target": "目标点",
        "Slice": "切片",
        "Origin": "中心点",
        "Output axis start": "输出轴起点",
        "Output axis end": "输出轴终点",
        "Roll point A": "Roll 点 A",
        "Roll point B": "Roll 点 B",
        "Part image unavailable": "部位图像不可用",
        "Click the part slice to fill the selected point. Source Z is shown as a locked reference; the editable output axis and roll points are drawn from the fields above.": "在部位切片上点击，可填写当前选择的点。原始 Z 轴作为锁定参考显示；可编辑输出轴和 roll 点来自上方字段。",
        "Open large MPR view": "大图点选",
        "Large MPR point picking": "MPR 大图点选",
        "Full screen": "全屏",
        "Exit full screen": "退出全屏",
        "Close": "关闭",
        "Source Z signal diagnostic": "原始 Z 信号诊断",
        "Show source Z signal diagnostic": "展开原始 Z 信号诊断",
        "Hide source Z signal diagnostic": "折叠原始 Z 信号诊断",
        "Auxiliary navigation only. This signal reflects the locked source Z slice stack and is not used to decide anatomical direction or local frame orientation.": "仅用于辅助导航。这个信号来自锁定的原始 Z 切片序列，不用于判断解剖方向或局部坐标系方向。",
        "Compute source Z signal": "计算原始 Z 信号",
        "Press Compute source Z signal when you need this optional diagnostic.": "需要这个可选诊断时，再点击“计算原始 Z 信号”。",
        "Copied source Z axis as editable output axis.": "已从原始 Z 轴复制可编辑输出轴。",
        "Loaded local axis draft from 3D preview.": "已载入三维预览中的局部轴草稿。",
        "Local frame is valid.": "局部坐标系有效。",
        "Preview generated: {0}": "已生成预览：{0}",
        "Exported local axis reslice {0}.": "已导出局部轴重切片 {0}。",
        "Select or accept the proposal before exporting.": "请先接受建议项，再用它导出正式重切片。",
        "Proposal status updated to {0}.": "建议项状态已更新为 {0}。",
        "No proposal selected.": "未选择建议项。",
        "Roll reference point pair is required before final export.": "正式导出前必须设置 roll 参照点对。",
        "ID": "编号",
        "Status": "状态",
        "Confidence": "置信度",
        "Model": "模型",
        "Missing": "缺失",
        "proposed": "待复核",
        "needs_review": "需要复核",
        "accepted": "已接受",
        "exported": "已导出",
        "rejected": "已拒绝",
        "source Z": "原始 Z",
        "output Z": "输出 Z",
        "origin": "中心点",
        "source Z signal, diagnostic only": "原始 Z 信号，仅作诊断",
        "Peak source-Z slice": "原始 Z 峰值切片",
        "Active range": "有效范围",
        "Active fraction": "有效比例",
        "Gaps": "断裂数",
        "Warnings": "提示",
        "Auxiliary navigation only.": "仅用于辅助导航。",
        "This source Z signal can help navigation and quality checks, but it is not an anatomical direction decision.": "原始 Z 信号可辅助导航和质量检查，但不能作为解剖方向判断。",
        "source_z_signal_is_auxiliary_navigation_only": "原始 Z 信号仅作辅助导航",
        "empty_signal": "信号为空",
        "low_dynamic_range": "动态范围偏低",
        "no_active_source_z_region": "未检测到明显有效区域",
        "fragmented_source_z_signal": "原始 Z 信号存在分段",
        "very_short_source_z_signal": "有效信号范围很短",
        "peak_near_stack_edge": "峰值靠近切片边缘",
        "signal_spans_most_slices_container_or_support_possible": "信号覆盖多数切片，可能受容器或支撑物影响",
    }
}


def tt(text, lang="en"):
    return LOCAL_AXIS_TRANSLATIONS.get(lang, {}).get(text, text)


class LocalAxisSliceLabel(QLabel):
    point_clicked = Signal(float, float)
    slice_wheel_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._display_rect = (0.0, 0.0, 1.0, 1.0)
        self._image_shape_yx = (1, 1)
        self.setMinimumHeight(160)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.setStyleSheet("QLabel { background: #101417; color: #DCE4E8; }")

    def set_display_mapping(self, image_shape_yx, rect_xywh):
        self._image_shape_yx = tuple(int(value) for value in image_shape_yx)
        self._display_rect = tuple(float(value) for value in rect_xywh)

    def mousePressEvent(self, event):
        x0, y0, width, height = self._display_rect
        if width <= 0 or height <= 0:
            return super().mousePressEvent(event)
        pos = event.position() if hasattr(event, "position") else event.pos()
        px = float(pos.x())
        py = float(pos.y())
        if px < x0 or py < y0 or px > x0 + width or py > y0 + height:
            return super().mousePressEvent(event)
        image_h, image_w = self._image_shape_yx
        ix = (px - x0) / width * max(1, image_w)
        iy = (py - y0) / height * max(1, image_h)
        self.point_clicked.emit(
            max(0.0, min(float(image_w - 1), ix)),
            max(0.0, min(float(image_h - 1), iy)),
        )
        event.accept()

    def wheelEvent(self, event):
        delta = event.angleDelta().y() if hasattr(event, "angleDelta") else 0
        if delta:
            self.slice_wheel_requested.emit(-1 if delta > 0 else 1)
            event.accept()
            return
        return super().wheelEvent(event)


class TifLocalAxisSlicePickerDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.lang = owner.lang
        self.setWindowTitle(tt("Large MPR point picking", self.lang))
        self.resize(1180, 820)
        self.setMinimumSize(760, 520)

        root = QVBoxLayout(self)
        top_controls = QHBoxLayout()
        self.axis_combo = QComboBox()
        self.axis_combo.addItem("Z", "z")
        self.axis_combo.addItem("Y", "y")
        self.axis_combo.addItem("X", "x")
        self.target_combo = QComboBox()
        self.target_combo.setMinimumContentsLength(10)
        self.target_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.target_combo.addItem(tt("Origin", self.lang), "origin")
        self.target_combo.addItem(tt("Output axis start", self.lang), "axis_start")
        self.target_combo.addItem(tt("Output axis end", self.lang), "axis_end")
        self.target_combo.addItem(tt("Roll point A", self.lang), "roll_a")
        self.target_combo.addItem(tt("Roll point B", self.lang), "roll_b")
        self.btn_fullscreen = QPushButton(tt("Full screen", self.lang))
        self.btn_fullscreen.clicked.connect(self.toggle_full_screen)
        top_controls.addWidget(QLabel(tt("Plane", self.lang)))
        top_controls.addWidget(self.axis_combo)
        top_controls.addWidget(QLabel(tt("Target", self.lang)))
        top_controls.addWidget(self.target_combo, 1)
        top_controls.addWidget(self.btn_fullscreen)
        root.addLayout(top_controls)

        slice_controls = QHBoxLayout()
        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_label = QLabel("")
        slice_controls.addWidget(QLabel(tt("Slice", self.lang)))
        slice_controls.addWidget(self.slice_slider, 1)
        slice_controls.addWidget(self.slice_label)
        root.addLayout(slice_controls)

        self.slice_canvas = LocalAxisSliceLabel()
        self.slice_canvas.setMinimumHeight(520)
        self.slice_canvas.setText(tt("Part image unavailable", self.lang))
        root.addWidget(self.slice_canvas, 1)

        help_label = QLabel(
            tt(
                "Click the part slice to fill the selected point. Source Z is shown as a locked reference; the editable output axis and roll points are drawn from the fields above.",
                self.lang,
            )
        )
        help_label.setWordWrap(True)
        root.addWidget(help_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        close_button = buttons.button(QDialogButtonBox.Close)
        if close_button is not None:
            close_button.setText(tt("Close", self.lang))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.axis_combo.currentIndexChanged.connect(self._configure_slice_range)
        self.target_combo.currentIndexChanged.connect(self._render)
        self.slice_slider.valueChanged.connect(self._render)
        self.slice_canvas.point_clicked.connect(self._set_point)
        self.slice_canvas.slice_wheel_requested.connect(self._move_slice)

        self._load_owner_state()
        self._configure_slice_range()

    def _load_owner_state(self):
        owner_axis = self.owner.picker_axis_combo.currentData() if hasattr(self.owner, "picker_axis_combo") else "z"
        owner_target = self.owner.picker_target_combo.currentData() if hasattr(self.owner, "picker_target_combo") else "origin"
        axis_index = self.axis_combo.findData(owner_axis)
        target_index = self.target_combo.findData(owner_target)
        self.axis_combo.setCurrentIndex(axis_index if axis_index >= 0 else 0)
        self.target_combo.setCurrentIndex(target_index if target_index >= 0 else 0)

    def _configure_slice_range(self, *_args):
        axis = self.axis_combo.currentData() or "z"
        count = self.owner._slice_count_for_picker_axis(axis)
        owner_index = int(self.owner.picker_slice_slider.value()) if hasattr(self.owner, "picker_slice_slider") else 0
        current = min(max(0, int(self.slice_slider.value() or owner_index)), count - 1)
        self.slice_slider.blockSignals(True)
        self.slice_slider.setRange(0, count - 1)
        self.slice_slider.setValue(current)
        self.slice_slider.blockSignals(False)
        self._render()

    def _move_slice(self, steps):
        value = max(self.slice_slider.minimum(), min(self.slice_slider.maximum(), self.slice_slider.value() + int(steps)))
        self.slice_slider.setValue(value)

    def _set_point(self, click_x, click_y):
        self.owner._set_picker_point_from_values(
            self.axis_combo.currentData() or "z",
            int(self.slice_slider.value()),
            self.target_combo.currentData() or "origin",
            click_x,
            click_y,
            sync_controls=True,
        )
        self._render()

    def toggle_full_screen(self):
        if self.isFullScreen():
            self.showNormal()
            self.btn_fullscreen.setText(tt("Full screen", self.lang))
        else:
            self.showFullScreen()
            self.btn_fullscreen.setText(tt("Exit full screen", self.lang))
        QTimer.singleShot(0, self._render)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
            self.btn_fullscreen.setText(tt("Full screen", self.lang))
            QTimer.singleShot(0, self._render)
            event.accept()
            return
        return super().keyPressEvent(event)

    def _render(self, *_args):
        axis = self.axis_combo.currentData() or "z"
        index = int(self.slice_slider.value())
        rendered = self.owner._render_slice_picker_to_label(self.slice_canvas, axis, index)
        if rendered:
            self.slice_label.setText(f"{index + 1} / {self.slice_slider.maximum() + 1}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._render)


class TifLocalAxisResliceDialog(QDialog):
    def __init__(self, project_manager, specimen_id, part_id, proposal_id="", parent=None, lang="en", initial_draft=None):
        super().__init__(parent)
        self.project = project_manager
        self.specimen_id = str(specimen_id or "")
        self.part_id = str(part_id or "")
        self.lang = lang
        self.export_result = None
        self.preview_volume = None
        self.part = self.project.get_part(self.specimen_id, self.part_id, default=None)
        if self.part is None:
            raise KeyError(f"unknown_part_id:{self.specimen_id}:{self.part_id}")

        self._part_volume_cache = None
        self._picker_render_enabled = False
        self._picker_render_pending = False
        self.part_image = self.part.get("image") or {}
        self.part_shape = [int(value) for value in (self.part_image.get("shape_zyx") or [1, 1, 1])]
        if len(self.part_shape) != 3:
            self.part_shape = [1, 1, 1]
        self.spacing_zyx = [float(value) for value in (self.part_image.get("spacing_zyx") or [1.0, 1.0, 1.0])]
        if len(self.spacing_zyx) != 3:
            self.spacing_zyx = [1.0, 1.0, 1.0]
        self.source_axis = source_z_axis_for_part(self.part_shape)
        self.editable_axis = create_editable_axis_from_source(self.source_axis)
        self.initial_draft = dict(initial_draft or {}) if isinstance(initial_draft, dict) else {}
        self.proposals = self.project.list_local_frame_proposals(self.specimen_id, self.part_id)

        self.setWindowTitle(tt("Local Axis Reslice", self.lang))
        self.resize(920, 760)
        self.setMinimumSize(720, 520)

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        body = QWidget()
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self._build_part_group())
        body_layout.addWidget(self._build_axis_group())
        body_layout.addWidget(self._build_slice_picker_group())
        body_layout.addWidget(self._build_source_signal_group())
        body_layout.addWidget(self._build_training_group())
        body_layout.addWidget(self._build_proposal_group(proposal_id))
        body_layout.addWidget(self._build_preview_group())
        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.btn_export = QPushButton(tt("Export reslice", self.lang))
        buttons.addButton(self.btn_export, QDialogButtonBox.AcceptRole)
        self.btn_export.clicked.connect(self.export_reslice)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._update_validation_status()
        self._configure_slice_picker()
        if proposal_id:
            self._select_proposal(proposal_id)
            self.load_selected_proposal()
        else:
            self._apply_initial_draft()
        QTimer.singleShot(0, self._enable_initial_picker_render)

    def _build_part_group(self):
        group = QGroupBox(tt("Current part", self.lang))
        layout = QFormLayout(group)
        mask_path = (self.part.get("mask") or {}).get("path", "")
        mask_status = tt("available", self.lang) if mask_path else tt("missing", self.lang)
        if mask_path and not volume_sidecar_exists(self.project.to_absolute(mask_path)):
            mask_status = tt("missing", self.lang)
        layout.addRow(tt("Specimen", self.lang), QLabel(self.specimen_id))
        layout.addRow(tt("Part", self.lang), QLabel(self.part_id))
        layout.addRow(tt("Shape", self.lang), QLabel(self._format_point(self.part_shape)))
        layout.addRow(tt("Spacing", self.lang), QLabel(self._format_point(self.spacing_zyx)))
        layout.addRow(tt("Parent bbox", self.lang), QLabel(str(self.part.get("parent_bbox_zyx", []))))
        layout.addRow(tt("Mask", self.lang), QLabel(mask_status))
        return group

    def _build_axis_group(self):
        group = QGroupBox(tt("Editable output axis", self.lang))
        layout = QFormLayout(group)
        center = [(float(value) - 1.0) / 2.0 for value in self.part_shape]

        self.source_label = QLabel(tt("Source Z axis is locked and used only as a direction reference.", self.lang))
        self.source_label.setWordWrap(True)
        self.reslice_id_edit = QLineEdit(self._default_reslice_id())
        self.template_id_edit = QLineEdit(self.part_id)
        self.origin_edit = QLineEdit(self._format_point(center))
        self.axis_start_edit = QLineEdit(self._format_point(self.source_axis.get("start_zyx")))
        self.axis_end_edit = QLineEdit(self._format_point(self.source_axis.get("end_zyx")))
        self.roll_a_role_edit = QLineEdit("roll_point_a")
        self.roll_a_point_edit = QLineEdit("")
        self.roll_b_role_edit = QLineEdit("roll_point_b")
        self.roll_b_point_edit = QLineEdit("")
        self.output_shape_edit = QLineEdit(",".join(str(int(value)) for value in self.part_shape))
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)

        self.btn_copy_source_axis = QPushButton(tt("Copy source Z axis", self.lang))
        self.btn_copy_source_axis.clicked.connect(self.copy_source_axis)

        layout.addRow(tt("Source reference", self.lang), self.source_label)
        layout.addRow("", self.btn_copy_source_axis)
        layout.addRow(tt("Reslice ID", self.lang), self.reslice_id_edit)
        layout.addRow(tt("Template", self.lang), self.template_id_edit)
        layout.addRow(tt("Origin z,y,x", self.lang), self.origin_edit)
        layout.addRow(tt("Output axis start z,y,x", self.lang), self.axis_start_edit)
        layout.addRow(tt("Output axis end z,y,x", self.lang), self.axis_end_edit)
        layout.addRow(tt("Roll point A role", self.lang), self.roll_a_role_edit)
        layout.addRow(tt("Roll point A z,y,x", self.lang), self.roll_a_point_edit)
        layout.addRow(tt("Roll point B role", self.lang), self.roll_b_role_edit)
        layout.addRow(tt("Roll point B z,y,x", self.lang), self.roll_b_point_edit)
        layout.addRow(tt("Output shape z,y,x", self.lang), self.output_shape_edit)
        layout.addRow("", self.validation_label)

        for edit in (
            self.origin_edit,
            self.axis_start_edit,
            self.axis_end_edit,
            self.roll_a_point_edit,
            self.roll_b_point_edit,
            self.output_shape_edit,
        ):
            edit.textChanged.connect(self._update_validation_status)
        return group

    def _build_slice_picker_group(self):
        group = QGroupBox(tt("MPR point picking", self.lang))
        root = QVBoxLayout(group)
        controls = QHBoxLayout()
        self.picker_axis_combo = QComboBox()
        self.picker_axis_combo.addItem("Z", "z")
        self.picker_axis_combo.addItem("Y", "y")
        self.picker_axis_combo.addItem("X", "x")
        self.picker_target_combo = QComboBox()
        self.picker_target_combo.setMinimumContentsLength(9)
        self.picker_target_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.picker_target_combo.addItem(tt("Origin", self.lang), "origin")
        self.picker_target_combo.addItem(tt("Output axis start", self.lang), "axis_start")
        self.picker_target_combo.addItem(tt("Output axis end", self.lang), "axis_end")
        self.picker_target_combo.addItem(tt("Roll point A", self.lang), "roll_a")
        self.picker_target_combo.addItem(tt("Roll point B", self.lang), "roll_b")
        self.picker_slice_slider = QSlider(Qt.Horizontal)
        self.picker_slice_label = QLabel("")
        controls.addWidget(QLabel(tt("Plane", self.lang)))
        controls.addWidget(self.picker_axis_combo)
        controls.addWidget(QLabel(tt("Target", self.lang)))
        controls.addWidget(self.picker_target_combo, 1)
        self.btn_large_mpr = QPushButton(tt("Open large MPR view", self.lang))
        self.btn_large_mpr.clicked.connect(self.open_large_mpr_view)
        controls.addWidget(self.btn_large_mpr)
        root.addLayout(controls)
        slice_controls = QHBoxLayout()
        slice_controls.addWidget(QLabel(tt("Slice", self.lang)))
        slice_controls.addWidget(self.picker_slice_slider, 1)
        slice_controls.addWidget(self.picker_slice_label)
        root.addLayout(slice_controls)
        self.slice_picker_label = LocalAxisSliceLabel()
        self.slice_picker_label.setText(tt("Part image unavailable", self.lang))
        self.slice_picker_label.setMinimumHeight(220)
        self.slice_picker_label.setMaximumHeight(260)
        root.addWidget(self.slice_picker_label)
        help_label = QLabel(
            tt(
                "Click the part slice to fill the selected point. Source Z is shown as a locked reference; the editable output axis and roll points are drawn from the fields above.",
                self.lang,
            )
        )
        help_label.setWordWrap(True)
        root.addWidget(help_label)
        self.picker_axis_combo.currentIndexChanged.connect(self._configure_slice_picker)
        self.picker_slice_slider.valueChanged.connect(self._render_slice_picker)
        self.slice_picker_label.point_clicked.connect(self._set_picker_point)
        self.slice_picker_label.slice_wheel_requested.connect(self._move_main_picker_slice)
        return group

    def _build_source_signal_group(self):
        group = QGroupBox(tt("Source Z signal diagnostic", self.lang))
        root = QVBoxLayout(group)
        self.source_signal_toggle = QToolButton()
        self.source_signal_toggle.setText(tt("Show source Z signal diagnostic", self.lang))
        self.source_signal_toggle.setCheckable(True)
        self.source_signal_toggle.setChecked(False)
        self.source_signal_toggle.setToolButtonStyle(Qt.ToolButtonTextOnly)
        root.addWidget(self.source_signal_toggle)
        self.source_signal_body = QVBoxLayout()
        self.source_signal_note = QLabel(
            tt(
                "Auxiliary navigation only. This signal reflects the locked source Z slice stack and is not used to decide anatomical direction or local frame orientation.",
                self.lang,
            )
        )
        self.source_signal_note.setWordWrap(True)
        self.source_signal_plot = QLabel("")
        self.source_signal_plot.setMinimumHeight(100)
        self.source_signal_plot.setMaximumHeight(140)
        self.source_signal_plot.setAlignment(Qt.AlignCenter)
        self.source_signal_plot.setStyleSheet("QLabel { background: #101417; color: #DCE4E8; }")
        self.source_signal_summary = QLabel("")
        self.source_signal_summary.setWordWrap(True)
        self.btn_compute_source_signal = QPushButton(tt("Compute source Z signal", self.lang))
        self.btn_compute_source_signal.clicked.connect(self.compute_source_signal)
        for widget in (self.source_signal_note, self.btn_compute_source_signal, self.source_signal_plot, self.source_signal_summary):
            self.source_signal_body.addWidget(widget)
        root.addLayout(self.source_signal_body)
        self.source_signal_toggle.toggled.connect(self._toggle_source_signal_body)
        self._toggle_source_signal_body(False)
        return group

    def _toggle_source_signal_body(self, checked):
        if not hasattr(self, "source_signal_body"):
            return
        for index in range(self.source_signal_body.count()):
            item = self.source_signal_body.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setVisible(bool(checked))
        self.source_signal_toggle.setText(
            tt("Hide source Z signal diagnostic" if checked else "Show source Z signal diagnostic", self.lang)
        )
        if checked and not self.source_signal_summary.text():
            self.source_signal_summary.setText(tt("Press Compute source Z signal when you need this optional diagnostic.", self.lang))

    def _build_proposal_group(self, proposal_id):
        group = QGroupBox(tt("AI proposal", self.lang))
        root = QVBoxLayout(group)
        row = QHBoxLayout()
        self.proposal_combo = QComboBox()
        self.proposal_combo.addItem(tt("No proposal", self.lang), "")
        for proposal in self.proposals:
            label = "{0} ({1}, {2:.3f})".format(
                proposal.get("frame_proposal_id", ""),
                tt(proposal.get("status", "proposed"), self.lang),
                float(proposal.get("confidence", 0.0) or 0.0),
            )
            self.proposal_combo.addItem(label, proposal.get("frame_proposal_id", ""))
        row.addWidget(QLabel(tt("Proposal", self.lang)))
        row.addWidget(self.proposal_combo, 1)
        root.addLayout(row)

        self.proposal_info_label = QLabel("")
        self.proposal_info_label.setWordWrap(True)
        root.addWidget(self.proposal_info_label)

        actions = QHBoxLayout()
        self.btn_accept_proposal = QPushButton(tt("Accept proposal", self.lang))
        self.btn_needs_review = QPushButton(tt("Needs review", self.lang))
        self.btn_reject_proposal = QPushButton(tt("Reject proposal", self.lang))
        self.btn_accept_proposal.clicked.connect(lambda: self.update_selected_proposal_status("accepted"))
        self.btn_needs_review.clicked.connect(lambda: self.update_selected_proposal_status("needs_review"))
        self.btn_reject_proposal.clicked.connect(lambda: self.update_selected_proposal_status("rejected"))
        actions.addWidget(self.btn_accept_proposal)
        actions.addWidget(self.btn_needs_review)
        actions.addWidget(self.btn_reject_proposal)
        root.addLayout(actions)
        self.proposal_combo.currentIndexChanged.connect(self.load_selected_proposal)
        self._select_proposal(proposal_id)
        self.load_selected_proposal()
        return group

    def _build_preview_group(self):
        group = QGroupBox(tt("Preview", self.lang))
        root = QVBoxLayout(group)
        self.btn_preview = QPushButton(tt("Generate preview", self.lang))
        self.btn_preview.clicked.connect(self.generate_preview)
        self.preview_status_label = QLabel("")
        self.preview_status_label.setWordWrap(True)
        self.preview_image_label = QLabel("")
        self.preview_image_label.setAlignment(Qt.AlignCenter)
        self.preview_image_label.setMinimumHeight(160)
        self.preview_image_label.setMaximumHeight(220)
        self.preview_image_label.setStyleSheet("QLabel { background: #101417; color: #DCE4E8; }")
        root.addWidget(self.btn_preview)
        root.addWidget(self.preview_status_label)
        root.addWidget(self.preview_image_label)
        return group

    def _build_training_group(self):
        group = QGroupBox(tt("Training quality", self.lang))
        root = QVBoxLayout(group)
        self.usable_training_check = QCheckBox(tt("Usable for training", self.lang))
        self.usable_training_check.setChecked(True)
        self.hard_case_check = QCheckBox(tt("Hard case", self.lang))
        self.reviewer_notes_edit = QTextEdit()
        self.reviewer_notes_edit.setPlaceholderText(tt("Reviewer notes", self.lang))
        self.reviewer_notes_edit.setMaximumHeight(80)
        root.addWidget(self.usable_training_check)
        root.addWidget(self.hard_case_check)
        root.addWidget(self.reviewer_notes_edit)
        return group

    def _proposal_by_id(self, proposal_id):
        wanted = str(proposal_id or "").strip()
        if not wanted:
            return None
        return self.project.get_local_frame_proposal(self.specimen_id, self.part_id, wanted, default=None)

    def _status_label(self, status):
        return tt(str(status or ""), self.lang)

    def _selected_proposal_id(self):
        return str(self.proposal_combo.currentData() or "")

    def _selected_proposal(self):
        return self._proposal_by_id(self._selected_proposal_id())

    def _select_proposal(self, proposal_id):
        wanted = str(proposal_id or "")
        if not wanted or not hasattr(self, "proposal_combo"):
            return
        for index in range(self.proposal_combo.count()):
            if str(self.proposal_combo.itemData(index) or "") == wanted:
                self.proposal_combo.setCurrentIndex(index)
                return

    def _configure_slice_picker(self, *_args):
        if not hasattr(self, "picker_slice_slider"):
            return
        axis = self.picker_axis_combo.currentData() if hasattr(self, "picker_axis_combo") else "z"
        count = self._slice_count_for_picker_axis(axis)
        current = min(max(0, int(self.picker_slice_slider.value())), count - 1)
        self.picker_slice_slider.blockSignals(True)
        self.picker_slice_slider.setRange(0, count - 1)
        self.picker_slice_slider.setValue(current)
        self.picker_slice_slider.blockSignals(False)
        self._schedule_slice_picker_render()

    def _enable_initial_picker_render(self):
        self._picker_render_enabled = True
        self._schedule_slice_picker_render()

    def _schedule_slice_picker_render(self):
        if not getattr(self, "_picker_render_enabled", False):
            return
        if getattr(self, "_picker_render_pending", False):
            return
        self._picker_render_pending = True
        QTimer.singleShot(50, self._render_slice_picker)

    def _default_reslice_id(self):
        existing = self.project.list_part_reslices(self.specimen_id, self.part_id) if self.project is not None else []
        return f"local_axis_{len(existing) + 1}"

    def _format_point(self, values):
        return ",".join(f"{float(value):.3f}".rstrip("0").rstrip(".") for value in (values or []))

    def _parse_point(self, text, field_name, allow_empty=False):
        text = str(text or "").strip()
        if not text and allow_empty:
            return []
        parts = [item.strip() for item in text.split(",") if item.strip()]
        if len(parts) != 3:
            raise ValueError(f"{field_name}_must_be_z_y_x")
        return [float(parts[0]), float(parts[1]), float(parts[2])]

    def _parse_shape(self, text):
        point = self._parse_point(text, "output_shape_zyx")
        return [max(1, int(round(value))) for value in point]

    def _part_image_volume_shape(self):
        if len(self.part_shape) == 3:
            return [max(1, int(value)) for value in self.part_shape]
        return [1, 1, 1]

    def _slice_count_for_picker_axis(self, axis):
        shape = self._part_image_volume_shape()
        axis_index = {"z": 0, "y": 1, "x": 2}.get(axis, 0)
        return max(1, int(shape[axis_index]))

    def copy_source_axis(self):
        self.editable_axis = create_editable_axis_from_source(self.source_axis)
        self.axis_start_edit.setText(self._format_point(self.source_axis.get("start_zyx")))
        self.axis_end_edit.setText(self._format_point(self.source_axis.get("end_zyx")))
        self.preview_status_label.setText(tt("Copied source Z axis as editable output axis.", self.lang))

    def _apply_initial_draft(self):
        draft = self.initial_draft if isinstance(self.initial_draft, dict) else {}
        if not draft:
            return
        if draft.get("specimen_id") and str(draft.get("specimen_id")) != self.specimen_id:
            return
        if draft.get("part_id") and str(draft.get("part_id")) != self.part_id:
            return
        source_axis = draft.get("source_axis")
        editable_axis = draft.get("editable_axis")
        if isinstance(source_axis, dict) and source_axis.get("start_zyx") and source_axis.get("end_zyx"):
            self.source_axis = dict(source_axis)
        if isinstance(editable_axis, dict):
            self.editable_axis = dict(editable_axis)
            if editable_axis.get("start_zyx"):
                self.axis_start_edit.setText(self._format_point(editable_axis.get("start_zyx")))
            if editable_axis.get("end_zyx"):
                self.axis_end_edit.setText(self._format_point(editable_axis.get("end_zyx")))
        if draft.get("template_id"):
            self.template_id_edit.setText(str(draft.get("template_id")))
        if draft.get("origin_zyx"):
            self.origin_edit.setText(self._format_point(draft.get("origin_zyx")))
        roll = draft.get("roll_reference") if isinstance(draft.get("roll_reference"), dict) else {}
        point_a = roll.get("point_a") if isinstance(roll.get("point_a"), dict) else {}
        point_b = roll.get("point_b") if isinstance(roll.get("point_b"), dict) else {}
        if point_a.get("zyx"):
            self.roll_a_role_edit.setText(str(point_a.get("role") or "roll_point_a"))
            self.roll_a_point_edit.setText(self._format_point(point_a.get("zyx")))
        if point_b.get("zyx"):
            self.roll_b_role_edit.setText(str(point_b.get("role") or "roll_point_b"))
            self.roll_b_point_edit.setText(self._format_point(point_b.get("zyx")))
        self.preview_status_label.setText(tt("Loaded local axis draft from 3D preview.", self.lang))
        self._update_validation_status()

    def load_selected_proposal(self):
        proposal = self._selected_proposal()
        if proposal is None:
            self.proposal_info_label.setText(tt("No proposal selected.", self.lang))
            return
        self.template_id_edit.setText(proposal.get("template_id") or self.part_id)
        self.origin_edit.setText(self._format_point(proposal.get("origin_zyx")))
        self.axis_start_edit.setText(self._format_point(proposal.get("output_axis_start_zyx")))
        self.axis_end_edit.setText(self._format_point(proposal.get("output_axis_end_zyx")))
        roll = proposal.get("roll_reference") or {}
        point_a = roll.get("point_a") if isinstance(roll.get("point_a"), dict) else {}
        point_b = roll.get("point_b") if isinstance(roll.get("point_b"), dict) else {}
        if point_a.get("zyx"):
            self.roll_a_role_edit.setText(str(point_a.get("role") or "roll_point_a"))
            self.roll_a_point_edit.setText(self._format_point(point_a.get("zyx")))
        if point_b.get("zyx"):
            self.roll_b_role_edit.setText(str(point_b.get("role") or "roll_point_b"))
            self.roll_b_point_edit.setText(self._format_point(point_b.get("zyx")))
        hard_flags = proposal.get("hard_case_flags") or []
        self.hard_case_check.setChecked(bool(hard_flags))
        self.proposal_info_label.setText(
            "{0}: {1}\n{2}: {3}\n{4}: {5:.3f}\n{6}: {7} {8}\n{9}: {10}".format(
                tt("ID", self.lang),
                proposal.get("frame_proposal_id", ""),
                tt("Status", self.lang),
                self._status_label(proposal.get("status", "proposed")),
                tt("Confidence", self.lang),
                float(proposal.get("confidence", 0.0) or 0.0),
                tt("Model", self.lang),
                proposal.get("model_id", ""),
                proposal.get("model_version", ""),
                tt("Missing", self.lang),
                ", ".join(proposal.get("missing_landmarks", []) or []),
            )
        )
        self._update_validation_status()
        self._schedule_slice_picker_render()

    def update_selected_proposal_status(self, status):
        proposal_id = self._selected_proposal_id()
        if not proposal_id:
            QMessageBox.information(self, tt("Local Axis Reslice", self.lang), tt("No proposal selected.", self.lang))
            return None
        record = self.project.update_local_frame_proposal(
            self.specimen_id,
            self.part_id,
            proposal_id,
            {"status": status, "reviewer_notes": self.reviewer_notes_edit.toPlainText().strip()},
        )
        self.proposals = self.project.list_local_frame_proposals(self.specimen_id, self.part_id)
        self.proposal_info_label.setText(tt("Proposal status updated to {0}.", self.lang).format(status))
        return record

    def _roll_reference_payload(self):
        roll_a = self._parse_point(self.roll_a_point_edit.text(), "roll_point_a", allow_empty=True)
        roll_b = self._parse_point(self.roll_b_point_edit.text(), "roll_point_b", allow_empty=True)
        if not roll_a or not roll_b:
            return {}
        role_a = self.roll_a_role_edit.text().strip() or "roll_point_a"
        role_b = self.roll_b_role_edit.text().strip() or "roll_point_b"
        return {
            "pair_id": f"{role_a}_{role_b}".strip("_"),
            "point_a": {"role": role_a, "zyx": roll_a},
            "point_b": {"role": role_b, "zyx": roll_b},
        }

    def build_reslice_payload(self):
        origin = self._parse_point(self.origin_edit.text(), "origin_zyx")
        axis_start = self._parse_point(self.axis_start_edit.text(), "output_axis_start_zyx")
        axis_end = self._parse_point(self.axis_end_edit.text(), "output_axis_end_zyx")
        roll_reference = self._roll_reference_payload()
        if not roll_reference:
            raise ValueError(tt("Roll reference point pair is required before final export.", self.lang))
        roll_reference = validate_roll_reference_pair(roll_reference)
        local_frame = compute_local_frame(origin, axis_start, axis_end, roll_reference=roll_reference, spacing_zyx=self.spacing_zyx)
        template_id = self.template_id_edit.text().strip()
        editable_axis = dict(self.editable_axis)
        editable_axis["start_zyx"] = axis_start
        editable_axis["end_zyx"] = axis_end
        proposal = self._selected_proposal()
        hard_flags = ["hard_case"] if self.hard_case_check.isChecked() else []
        training_source = "human_manual_local_axis"
        provenance = {"created_by": "TaxaMask Local Axis Reslice"}
        if proposal is not None:
            training_source = "AI proposed + human reviewed"
            provenance.update(
                {
                    "source_proposal_id": proposal.get("frame_proposal_id", ""),
                    "source_model_id": proposal.get("model_id", ""),
                    "source_model_version": proposal.get("model_version", ""),
                }
            )
        return {
            "reslice_id": self.reslice_id_edit.text().strip() or self._default_reslice_id(),
            "display_name": self.reslice_id_edit.text().strip() or self._default_reslice_id(),
            "template_id": template_id,
            "source_axis": self.source_axis,
            "editable_axis": editable_axis,
            "local_frame": local_frame,
            "reslice_params": {
                "output_shape_zyx": self._parse_shape(self.output_shape_edit.text()),
                "output_spacing_zyx": self.spacing_zyx,
                "image_interpolation": "linear",
            },
            "training": {
                "human_confirmed": True,
                "usable_for_training": bool(self.usable_training_check.isChecked()),
                "source": training_source,
                "template_id": template_id,
                "hard_case_flags": hard_flags,
                "reviewer_notes": self.reviewer_notes_edit.toPlainText().strip(),
            },
            "provenance": provenance,
        }

    def _update_validation_status(self, *_args):
        if not hasattr(self, "validation_label"):
            return
        try:
            self.build_reslice_payload()
        except Exception as exc:
            self.validation_label.setText(str(exc))
            self._schedule_slice_picker_render()
            return
        self.validation_label.setText(tt("Local frame is valid.", self.lang))
        self._schedule_slice_picker_render()

    def _part_image_volume(self):
        if self._part_volume_cache is not None:
            return self._part_volume_cache
        image_path = self.project.to_absolute(self.part_image.get("path", ""))
        if not image_path or not volume_sidecar_exists(image_path):
            raise FileNotFoundError(image_path)
        self._part_volume_cache = load_volume_sidecar(image_path, mmap_mode="r")
        return self._part_volume_cache

    def _extract_axis_slice(self, volume, axis, index):
        axis = axis if axis in {"z", "y", "x"} else "z"
        if axis == "y":
            index = max(0, min(int(index), int(volume.shape[1]) - 1))
            return np.asarray(volume[:, index, :])
        if axis == "x":
            index = max(0, min(int(index), int(volume.shape[2]) - 1))
            return np.asarray(volume[:, :, index])
        index = max(0, min(int(index), int(volume.shape[0]) - 1))
        return np.asarray(volume[index])

    def _point_to_plane_xy(self, point_zyx, axis):
        if not point_zyx or len(point_zyx) != 3:
            return None
        z, y, x = [float(value) for value in point_zyx]
        if axis == "y":
            return float(x), float(z), float(y)
        if axis == "x":
            return float(y), float(z), float(x)
        return float(x), float(y), float(z)

    def _current_picker_point(self, click_x, click_y):
        axis = self.picker_axis_combo.currentData() if hasattr(self, "picker_axis_combo") else "z"
        plane_index = float(self.picker_slice_slider.value()) if hasattr(self, "picker_slice_slider") else 0.0
        return self._picker_point_from_values(axis, plane_index, click_x, click_y)

    def _picker_point_from_values(self, axis, plane_index, click_x, click_y):
        if axis == "y":
            return [click_y, plane_index, click_x]
        if axis == "x":
            return [click_y, click_x, plane_index]
        return [plane_index, click_y, click_x]

    def _set_picker_point(self, click_x, click_y):
        axis = self.picker_axis_combo.currentData() if hasattr(self, "picker_axis_combo") else "z"
        plane_index = int(self.picker_slice_slider.value()) if hasattr(self, "picker_slice_slider") else 0
        target = self.picker_target_combo.currentData() if hasattr(self, "picker_target_combo") else "origin"
        self._set_picker_point_from_values(axis, plane_index, target, click_x, click_y)

    def _set_picker_point_from_values(self, axis, plane_index, target, click_x, click_y, sync_controls=False):
        point = self._picker_point_from_values(axis, float(plane_index), click_x, click_y)
        edit_by_target = {
            "origin": self.origin_edit,
            "axis_start": self.axis_start_edit,
            "axis_end": self.axis_end_edit,
            "roll_a": self.roll_a_point_edit,
            "roll_b": self.roll_b_point_edit,
        }
        edit = edit_by_target.get(target)
        if edit is not None:
            edit.setText(self._format_point(point))
        if sync_controls and hasattr(self, "picker_axis_combo") and hasattr(self, "picker_target_combo") and hasattr(self, "picker_slice_slider"):
            axis_index = self.picker_axis_combo.findData(axis)
            target_index = self.picker_target_combo.findData(target)
            if axis_index >= 0:
                self.picker_axis_combo.setCurrentIndex(axis_index)
            if target_index >= 0:
                self.picker_target_combo.setCurrentIndex(target_index)
            self.picker_slice_slider.setValue(int(plane_index))
        self._schedule_slice_picker_render()

    def _move_main_picker_slice(self, steps):
        if not hasattr(self, "picker_slice_slider"):
            return
        value = max(self.picker_slice_slider.minimum(), min(self.picker_slice_slider.maximum(), self.picker_slice_slider.value() + int(steps)))
        self.picker_slice_slider.setValue(value)

    def open_large_mpr_view(self):
        dialog = TifLocalAxisSlicePickerDialog(self)
        dialog.exec()
        self._schedule_slice_picker_render()

    def _draw_axis_overlay(self, painter, axis, slice_index, image_shape_yx, scale, pad_x, pad_y, color, start, end, label):
        start_xy = self._point_to_plane_xy(start, axis)
        end_xy = self._point_to_plane_xy(end, axis)
        if start_xy is None or end_xy is None:
            return
        start_plane = start_xy[2]
        end_plane = end_xy[2]
        if abs(start_plane - float(slice_index)) > 1.5 and abs(end_plane - float(slice_index)) > 1.5:
            return
        pen = QPen(QColor(color), 2)
        painter.setPen(pen)
        x0 = pad_x + start_xy[0] * scale
        y0 = pad_y + start_xy[1] * scale
        x1 = pad_x + end_xy[0] * scale
        y1 = pad_y + end_xy[1] * scale
        painter.drawLine(int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1)))
        painter.drawText(int(round(x1 + 5)), int(round(y1 - 5)), label)

    def _draw_point_overlay(self, painter, axis, slice_index, scale, pad_x, pad_y, color, point, label):
        point_xy = self._point_to_plane_xy(point, axis)
        if point_xy is None or abs(point_xy[2] - float(slice_index)) > 1.5:
            return
        x = pad_x + point_xy[0] * scale
        y = pad_y + point_xy[1] * scale
        painter.setPen(QPen(QColor(color), 2))
        painter.drawEllipse(int(round(x - 4)), int(round(y - 4)), 8, 8)
        painter.drawText(int(round(x + 6)), int(round(y - 6)), label)

    def _render_slice_picker(self, *_args):
        self._picker_render_pending = False
        if not getattr(self, "_picker_render_enabled", False):
            return
        if not hasattr(self, "slice_picker_label"):
            return
        axis = self.picker_axis_combo.currentData() if hasattr(self, "picker_axis_combo") else "z"
        index = int(self.picker_slice_slider.value()) if hasattr(self, "picker_slice_slider") else 0
        if self._render_slice_picker_to_label(self.slice_picker_label, axis, index):
            self.picker_slice_label.setText(f"{index + 1} / {self.picker_slice_slider.maximum() + 1}")

    def _render_slice_picker_to_label(self, label, axis, index):
        total_count = self._slice_count_for_picker_axis(axis)
        index = max(0, min(int(index), total_count - 1))
        try:
            image = self._part_image_volume()
        except Exception:
            label.setText(tt("Part image unavailable", self.lang))
            return False
        image_slice = self._extract_axis_slice(image, axis, index)
        array = np.asarray(image_slice, dtype=np.float32)
        if array.ndim != 2 or array.size == 0:
            label.setText(tt("Part image unavailable", self.lang))
            return False
        lo = float(np.percentile(array, 1))
        hi = float(np.percentile(array, 99))
        if hi <= lo:
            hi = lo + 1.0
        gray = np.clip((array - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
        height, width = gray.shape
        rgb = np.stack([gray, gray, gray], axis=-1)
        qimage = QImage(np.ascontiguousarray(rgb).data, width, height, width * 3, QImage.Format_RGB888).copy()
        parent_width = label.parentWidget().width() if label.parentWidget() is not None else 0
        label_w = max(320, int(label.width() or parent_width or 520))
        label_h = max(160, int(label.height() or 220))
        scale = min(label_w / max(1, width), label_h / max(1, height))
        draw_w = max(1, int(round(width * scale)))
        draw_h = max(1, int(round(height * scale)))
        pad_x = (label_w - draw_w) / 2.0
        pad_y = (label_h - draw_h) / 2.0
        pixmap = QPixmap(label_w, label_h)
        pixmap.fill(QColor("#101417"))
        painter = QPainter(pixmap)
        painter.drawImage(int(round(pad_x)), int(round(pad_y)), qimage.scaled(draw_w, draw_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        try:
            payload = self.build_reslice_payload()
            editable = payload.get("editable_axis") or {}
            roll = payload.get("local_frame", {}).get("roll_reference", {}) or {}
        except Exception:
            editable = {
                "start_zyx": self._safe_parse_point_for_overlay(self.axis_start_edit.text()),
                "end_zyx": self._safe_parse_point_for_overlay(self.axis_end_edit.text()),
            }
            roll = self._roll_reference_payload_safe()
        self._draw_axis_overlay(
            painter,
            axis,
            index,
            (height, width),
            scale,
            pad_x,
            pad_y,
            "#6AA6FF",
            self.source_axis.get("start_zyx"),
            self.source_axis.get("end_zyx"),
            tt("source Z", self.lang),
        )
        self._draw_axis_overlay(
            painter,
            axis,
            index,
            (height, width),
            scale,
            pad_x,
            pad_y,
            "#FFB84D",
            editable.get("start_zyx"),
            editable.get("end_zyx"),
            tt("output Z", self.lang),
        )
        self._draw_point_overlay(
            painter,
            axis,
            index,
            scale,
            pad_x,
            pad_y,
            "#7CFF9B",
            self._safe_parse_point_for_overlay(self.origin_edit.text()),
            tt("origin", self.lang),
        )
        point_a = roll.get("point_a") if isinstance(roll.get("point_a"), dict) else {}
        point_b = roll.get("point_b") if isinstance(roll.get("point_b"), dict) else {}
        self._draw_point_overlay(painter, axis, index, scale, pad_x, pad_y, "#FF7BE5", point_a.get("zyx"), str(point_a.get("role") or "A"))
        self._draw_point_overlay(painter, axis, index, scale, pad_x, pad_y, "#FF7BE5", point_b.get("zyx"), str(point_b.get("role") or "B"))
        painter.setPen(QPen(QColor("#DCE4E8"), 1))
        painter.drawText(8, 18, f"{axis.upper()} {index + 1}/{total_count}")
        painter.end()
        label.setPixmap(pixmap)
        label.set_display_mapping((height, width), (pad_x, pad_y, draw_w, draw_h))
        return True

    def compute_source_signal(self):
        try:
            signal = compute_source_z_signal(self._part_image_volume())
            summary = analyze_source_z_signal(signal)
        except Exception as exc:
            self.source_signal_summary.setText(str(exc))
            return None
        self._show_source_signal_plot(signal, summary)
        warnings = ", ".join(tt(item, self.lang) for item in (summary.get("warnings", []) or [])) or "-"
        active_range = summary.get("active_range_zyx", "-")
        self.source_signal_summary.setText(
            "{0}: {1}\n{2}: {3}\n{4}: {5:.3f}\n{6}: {7}\n{8}: {9}\n{10}".format(
                tt("Peak source-Z slice", self.lang),
                "-" if summary.get("peak_slice") is None else int(summary.get("peak_slice")) + 1,
                tt("Active range", self.lang),
                active_range,
                tt("Active fraction", self.lang),
                float(summary.get("active_fraction", 0.0) or 0.0),
                tt("Gaps", self.lang),
                int(summary.get("gap_count", 0) or 0),
                tt("Warnings", self.lang),
                warnings,
                tt(summary.get("message", "Auxiliary navigation only."), self.lang),
            )
        )
        return {"signal": signal, "summary": summary}

    def _show_source_signal_plot(self, signal, summary):
        values = np.asarray(signal.get("normalized_signal") or [], dtype=np.float64)
        width = max(320, int(self.source_signal_plot.width() or 520))
        height = max(120, int(self.source_signal_plot.height() or 120))
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#101417"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor("#48535A"), 1))
        left, right, top, bottom = 34, width - 12, 14, height - 26
        painter.drawRect(left, top, max(1, right - left), max(1, bottom - top))
        if values.size:
            points = []
            for index, value in enumerate(values):
                x = left + (right - left) * (float(index) / float(max(1, values.size - 1)))
                y = bottom - (bottom - top) * max(0.0, min(1.0, float(value)))
                points.append((x, y))
            painter.setPen(QPen(QColor("#FFB84D"), 2))
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                painter.drawLine(int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1)))
            peak = summary.get("peak_slice")
            if peak is not None and 0 <= int(peak) < len(points):
                x, y = points[int(peak)]
                painter.setPen(QPen(QColor("#7CFF9B"), 2))
                painter.drawEllipse(int(round(x - 4)), int(round(y - 4)), 8, 8)
        painter.setPen(QPen(QColor("#DCE4E8"), 1))
        painter.drawText(8, height - 8, tt("source Z signal, diagnostic only", self.lang))
        painter.end()
        self.source_signal_plot.setPixmap(pixmap)

    def _safe_parse_point_for_overlay(self, text):
        try:
            return self._parse_point(text, "overlay_point", allow_empty=True)
        except Exception:
            return []

    def _roll_reference_payload_safe(self):
        try:
            return self._roll_reference_payload()
        except Exception:
            return {}

    def generate_preview(self):
        try:
            payload = self.build_reslice_payload()
            image = self._part_image_volume()
            self.preview_volume = build_reslice_preview(image, payload["local_frame"], payload.get("reslice_params"), max_shape_zyx=(80, 80, 80))
        except Exception as exc:
            self.preview_status_label.setText(str(exc))
            QMessageBox.warning(self, tt("Local Axis Reslice", self.lang), str(exc))
            return None
        shape_text = "x".join(str(int(value)) for value in self.preview_volume.shape)
        self.preview_status_label.setText(tt("Preview generated: {0}", self.lang).format(shape_text))
        self._show_preview_middle_slice()
        return self.preview_volume

    def _show_preview_middle_slice(self):
        if self.preview_volume is None:
            return
        array = np.asarray(self.preview_volume)
        if array.ndim != 3 or array.size == 0:
            return
        slice_2d = np.asarray(array[array.shape[0] // 2], dtype=np.float32)
        lo = float(np.percentile(slice_2d, 1)) if slice_2d.size else 0.0
        hi = float(np.percentile(slice_2d, 99)) if slice_2d.size else 1.0
        if hi <= lo:
            hi = lo + 1.0
        gray = np.clip((slice_2d - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
        gray = np.ascontiguousarray(gray)
        height, width = gray.shape
        image = QImage(gray.data, width, height, gray.strides[0], QImage.Format_Grayscale8).copy()
        pixmap = QPixmap.fromImage(image).scaled(self.preview_image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_image_label.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._show_preview_middle_slice()
        self._schedule_slice_picker_render()

    def export_reslice(self):
        proposal = self._selected_proposal()
        if proposal is not None and proposal.get("status") != "accepted":
            QMessageBox.warning(self, tt("Local Axis Reslice", self.lang), tt("Select or accept the proposal before exporting.", self.lang))
            return None
        try:
            payload = self.build_reslice_payload()
            self.export_result = export_part_reslice(self.project, self.specimen_id, self.part_id, payload)
            if proposal is not None:
                self.project.update_local_frame_proposal(
                    self.specimen_id,
                    self.part_id,
                    proposal.get("frame_proposal_id", ""),
                    {"status": "exported", "reviewer_notes": self.reviewer_notes_edit.toPlainText().strip()},
                )
        except Exception as exc:
            QMessageBox.warning(self, tt("Local Axis Reslice", self.lang), str(exc))
            return None
        record = self.export_result.get("record", {})
        self.preview_status_label.setText(tt("Exported local axis reslice {0}.", self.lang).format(record.get("reslice_id", "")))
        self.accept()
        return self.export_result
