# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportIncompatibleMethodOverride=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportOptionalCall=false, reportUninitializedInstanceVariable=false

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLabel, QSplitter, QListWidget,
                              QGroupBox, QSlider, QProgressBar, QRadioButton, QButtonGroup, QSpinBox, QTreeWidget, QTreeWidgetItem, QMessageBox, QTextEdit, QCheckBox, QDialog, QDialogButtonBox, QLineEdit, QHeaderView, QSizePolicy, QScrollArea, QFrame, QComboBox, QTabWidget, QInputDialog)
import os
import shutil
import sys
from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QThread
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QPainterPath, QPixmap
try:
    from AntSleap.core.taxonomy_defaults import is_safe_part_name
    from AntSleap.core.cascade_routes import build_expert_id
    from AntSleap.core.expert_notes import format_expert_display_name, load_expert_notes, set_expert_note
except ImportError:
    from core.taxonomy_defaults import is_safe_part_name
    from core.cascade_routes import build_expert_id
    from core.expert_notes import format_expert_display_name, load_expert_notes, set_expert_note
from .canvas import AnnotationCanvas
from .style import (
    BUTTON_ROLE_COMMIT,
    BUTTON_ROLE_DESTRUCTIVE,
    BUTTON_ROLE_NEUTRAL,
    BUTTON_ROLE_RUN,
    BUTTON_ROLE_STOP,
    SURFACE_ROLE_CANVAS,
    SURFACE_ROLE_PANEL,
    SURFACE_ROLE_RAISED,
    SURFACE_ROLE_SUBTLE,
    apply_theme_dialog_button_box_style,
    apply_theme_button_style,
    apply_semantic_button_style,
    apply_surface_role,
    get_theme_config,
    themed_yes_no_question,
)

BLINK_TRANSLATIONS = {
    "zh": {
        "Expert Taxonomy": "专家分类",
        "Sync from Workbench": "从工作台同步",
        "Start Center": "启动中心",
        "Ask Agent": "询问 Agent",
        "Drawing Tools": "绘制工具",
        "Draw Polygon": "绘制多边形",
        "Draw Box (For SAM Draft)": "绘制框（SAM 草稿）",
        "Draw Box (For Shrink)": "绘制框（用于收缩）",
        "Trained Experts": "已训练专家",
        "Model File": "模型文件",
        "Size": "大小",
        "Appoint to Current Route": "指定到当前路由",
        "Edit Note": "编辑备注",
        "Delete": "删除",
        "Refresh": "刷新",
        "Blink Control Room": "Blink 控制区",
        "Mode: STANDBY": "模式：待命",
        "BLINK SWITCH\n(Space)": "BLINK 开关\n（空格）",
        "Shrink Logic:": "收缩逻辑：",
        "AUTO-ANNOTATE DRAFT": "自动标注草稿",
        "EXECUTE AUTO-SHRINK": "执行自动收缩",
        "APPLY TO GLOBAL": "应用到全局",
        "Training Settings": "训练设置",
        "Training Log": "训练日志",
        "Clear Log": "清空日志",
        "Blink training log will appear here during expert training.": "Blink 专家训练时的日志会显示在这里。",
        "Epochs:": "训练轮数 (Epochs):",
        "Batch Size:": "批次大小 (Batch Size):",
        "Learning Rate:": "学习率 (LR):",
        "Weight Decay:": "权重衰减：",
        "Input Size:": "输入尺寸：",
        "Blink Training Report": "Blink 训练报告",
        "Summary": "摘要",
        "Metrics": "指标",
        "Box Validation": "框验证",
        "No report image generated.": "没有生成报告图像。",
        "Close": "关闭",
        "TRAIN EXPERT MODEL": "训练专家模型",
        "STOP TRAINING": "停止训练",
        "Training Progress": "训练进度",
        "Training cancelled.": "训练已取消。",
        "Stopping training after the current batch...": "将在当前批次结束后停止训练...",
        "Discard Blink Edits?": "放弃 Blink 编辑？",
        "The current Blink session has unapplied edits. Discard them and {0}?": "当前 Blink 会话有未应用的修改。要放弃这些修改并{0}吗？",
        "Focus: Full Image": "焦点：整张图像",
        "Manual Box": "手工框",
        "Auto Box": "自动框",
        "Session: {0} via {1} ({2})": "会话：{0}（通过 {1}，{2}）",
        "Error: Invalid Blink session.": "错误：无效的 Blink 会话。",
        "Blink session kept. Apply or discard edits before switching sessions.": "已保留当前 Blink 会话。请先应用或放弃编辑后再切换会话。",
        "Error: Incomplete Blink session.": "错误：Blink 会话信息不完整。",
        "Blink session has unsaved edits. Apply to Global or click Sync to discard before reloading.": "Blink 会话有未保存的修改。请先应用到全局，或点击同步以放弃修改后再重新加载。",
        "Sync cancelled. Blink session edits were kept.": "已取消同步，Blink 会话修改已保留。",
        "Synced from Workbench": "已从工作台同步",
        "Info": "提示",
        "This model is already appointed to the current route.": "该模型已经是当前路由的指定专家。",
        "Appoint this model to {0}?\n(This will only update the current route manifest; it will not copy or overwrite model files.)": "要将该模型指定到当前 Blink 路由 {0} 吗？\n这只会更新当前项目路由，不会复制或覆盖模型文件。",
        "Success": "成功",
        "Route expert updated successfully.": "当前路由专家已更新。",
        "Open a Blink session with a parent ROI before appointing a route expert.": "请先通过父级 ROI 打开 Blink 会话，再为当前路由指定专家。",
        "Expert Note": "专家备注",
        "Set a short note for {0}:": "为 {0} 设置一个简短备注：",
        "Select a trained expert file first.": "请先选择一个专家模型文件。",
        "Edit a display note only. The model file name and route binding stay unchanged.": "只编辑展示备注；模型文件名和路由绑定不会改变。",
        "Note saved.": "备注已保存。",
        "Note cleared.": "备注已清空。",
        "Delete Model": "删除模型",
        "Are you sure you want to delete {0}?": "确定要删除 {0} 吗？",
        "Delete Expert Bucket": "删除专家桶",
        "Delete Current Project Route Branches": "删除当前项目中对应的路由分支",
        "Bucket Delete Review": "专家桶删除风险确认",
        "Type-to-Confirm Bucket Delete": "输入名称以确认删除",
        "Delete Expert Bucket Permanently": "永久删除专家桶",
        "Cancel": "取消",
        "Delete cancelled. The expert bucket was kept.": "已取消删除，专家桶已保留。",
        "Delete cancelled. Current project route branches were kept.": "已取消删除，当前项目中的路由分支已保留。",
        "Select a trained expert file or a child-part bucket first.": "请先选择一个训练好的专家文件，或选择一个子部位专家桶。",
        "Delete the selected expert model file from disk.": "从磁盘删除当前选中的专家模型文件。",
        "Delete the selected child-part expert bucket from disk.": "从磁盘删除当前选中的子部位专家桶。",
        "Delete all expert files for {0}?": "要删除 {0} 的整个专家桶吗？",
        "This is a high-risk action. It deletes the expert bucket from disk and can also remove matching route branches in the currently open project.": "这是高风险操作。它会从磁盘删除该专家桶，并且还可以同时删除当前打开项目里匹配的路由分支。",
        "Target bucket path:": "目标专家桶路径：",
        "Files to delete ({0}):": "将删除的文件（{0} 个）：",
        "No expert files were found in this bucket.": "这个专家桶里没有找到专家模型文件。",
        "Affected routes in the current project ({0}):": "当前项目中受影响的路由（{0} 条）：",
        "No matching current-project routes were found.": "当前打开项目里没有发现匹配的路由。",
        "Default cleanup action:": "默认清理动作：",
        "If checked, TaxaMask will remove the matching route branches from the currently open project only after the bucket files are deleted successfully. Other projects are not scanned or changed.": "如果保持勾选，TaxaMask 只会在该专家桶文件成功删除后，删除当前打开项目中匹配的路由分支。不会扫描或修改其他项目。",
        "If unchecked, the files will still be deleted, but the current project routes will remain and later show missing-expert behavior until you clean them manually.": "如果取消勾选，模型文件仍会被删除，但当前项目里的路由会保留，之后会表现为“专家文件缺失”，直到你手工清理。",
        "Please type the child-part name exactly to confirm bucket deletion:": "请输入子部位名称，并且必须完全一致，才会继续删除专家桶：",
        "Type child-part name here": "在这里输入子部位名称",
        "You must type '{0}' exactly to continue.": "你必须完整输入“{0}”才能继续。",
        "Deleted expert bucket for {0}.": "已删除 {0} 的专家桶。",
        "Deleted {0} current-project route branch(es) for {1}.": "已为 {1} 删除当前项目中的 {0} 条路由分支。",
        "Expert bucket deleted, but current-project route cleanup was skipped.": "专家桶已删除，但当前项目的路由清理已跳过。",
        "Failed to delete expert bucket: {0}": "删除专家桶失败：{0}",
        "Error": "错误",
        "Failed to delete file: {0}": "删除文件失败：{0}",
        "Mode: Draw Polygon": "模式：绘制多边形",
        "Mode: Draw Prompt Box": "模式：绘制草稿框",
        "Mode: Draw Box": "模式：绘制框",
        "Box drawn for {0}. Ready to Shrink.": "已为 {0} 绘制框，可开始收缩。",
        "Generating SAM draft from manual box for {0}...": "正在根据 {0} 的手工框生成 SAM 草稿...",
        "Base SAM returned no polygon for the prompt box of {0}. Adjust the box or refine manually.": "基础 SAM 没有为 {0} 的提示框返回多边形。请调整框或手工精修。",
        "Edited {0} in Blink session. Apply to Global to keep changes.": "已在 Blink 会话中编辑 {0}。请应用到全局以保留修改。",
        "Focus: {0}": "焦点：{0}",
        "Mode: {0}": "模式：{0}",
        "Error: Select a part first!": "错误：请先选择部位！",
        "Error: Open a Blink session first.": "错误：请先打开一个 Blink 会话。",
        "Error: Blink auto-annotate needs a valid session ROI.": "错误：Blink 自动标注需要有效的会话 ROI。",
        "Generating SAM draft for {0}...": "正在为 {0} 生成 SAM 草稿...",
        "Draft polygon generated for {0}. Refine it, then draw a loose box for shrink.": "已为 {0} 生成草稿多边形。请先精修，再绘制松框用于收缩。",
        "Expert found a box for {0}, but base SAM returned no polygon. Refine manually.": "专家已为 {0} 找到框，但基础 SAM 没有返回多边形。请手工精修。",
        "Error: No appointed route expert found for {0}. Train one or appoint a candidate first.": "错误：没有找到 {0} 的路由指定专家。请先训练一个候选专家，或手动指定一个专家。",
        "Replace current polygon for {0}?": "要替换 {0} 的当前多边形吗？",
        "A draft polygon already exists for this target. Replacing it will discard the current local polygon.": "该目标已经有一个草稿多边形。替换后会丢弃当前本地多边形。",
        "Auto-annotate cancelled. Current polygon kept.": "已取消自动标注，当前多边形已保留。",
        "Error generating draft polygon for {0}: {1}": "为 {0} 生成草稿多边形时出错：{1}",
        "Nothing to apply for {0}.": "{0} 没有可应用的内容。",
        "Applied {0} to Global!": "已将 {0} 应用到全局！",
        "Error: Draw a loose BOX for {0} first!": "错误：请先为 {0} 绘制一个松框！",
        "Error: Draw a golden POLYGON for {0} !": "错误：请先为 {0} 绘制黄金标准多边形！",
        "Error: Draw a golden POLYGON for {0}!": "错误：请先为 {0} 绘制黄金标准多边形！",
        "Error: Zoomed image not ready.": "错误：放大图像尚未准备好。",
        "Generating Trajectory for {0}...": "正在为 {0} 生成轨迹...",
        "Error generating trajectory.": "生成轨迹时出错。",
        "Generated {0} trajectory frames.": "已生成 {0} 帧轨迹。",
        "Saved {0} trajectory frames for {1}.": "已为 {1} 保存 {0} 帧轨迹。",
        "Error: Select a part to train!": "错误：请选择要训练的部位！",
        "Training already running...": "训练已在进行中...",
        "Training Expert for {0}...": "正在为 {0} 训练专家模型...",
        "Success! Expert saved.": "成功！专家模型已保存。",
        "Training failed. Need more data.": "训练失败，需要更多数据。",
        "Training finished. Expert was linked to route {0} -> {1} and enabled for workbench auto-annotation.": "训练完成。专家模型已绑定到路由 {0} -> {1}，并已启用，可用于标注工作台自动标注。",
        "Training finished. Route {0} -> {1} already has an appointed expert, so the new model was saved as a candidate and was not appointed automatically.": "训练完成。路由 {0} -> {1} 已有指定专家，因此新模型已作为候选保存，未自动指定。",
        "Training finished. Expert was added as a route candidate for {0} -> {1}. Appoint it manually if the report looks better.": "训练完成。专家模型已作为路由 {0} -> {1} 的候选保存。请根据报告判断更好后再手动指定。",
        "Training finished. Expert saved, but no parent-part route was available to enable.": "训练完成。专家模型已保存，但当前没有可启用的父部位路由。",
        "Training finished. Expert saved, but route auto-link failed: {0}": "训练完成。专家模型已保存，但自动绑定路由失败：{0}",
        "Training Error: {0}": "训练错误：{0}",
        "open a new session": "打开新会话",
        "reload from the workbench": "从工作台重新加载",
        "NORMAL": "普通",
        "INSIDE": "内侧",
        "OUTSIDE": "外侧",
    }
}


def translate_blink_text(text, lang="en"):
    if lang == "zh":
        return BLINK_TRANSLATIONS["zh"].get(text, text)
    return text


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class BlinkCanvas(AnnotationCanvas):
    """
    Subclass of AnnotationCanvas specialized for the BLINK algorithm.
    Adds masking overlays for Inside-View and Outside-View.
    """
    def __init__(self):
        super().__init__()
        self.blink_mode = "NORMAL" # NORMAL, INSIDE, OUTSIDE
        self.blink_alpha = 196 # Strong guidance without near-blackout fatigue
        
    def set_blink_mode(self, mode):
        self.blink_mode = mode
        self.update()

    def paintEvent(self, event):
        # 1. Base Rendering (Image, Polygons)
        super().paintEvent(event)
        
        if self.blink_mode == "NORMAL" or not self.original_pixmap:
            return

        # 2. Blink Overlay Logic
        # We look for a box for the current_tool_part
        target_box = None
        if self.current_tool_part:
            if self.current_tool_part in self.manual_boxes:
                target_box = self.manual_boxes[self.current_tool_part]
            elif self.current_tool_part in self.auto_boxes:
                target_box = self.auto_boxes[self.current_tool_part]

        # 兼容场景：如果没有框，但有该部位多边形，则自动使用多边形外接框做 Blink 示意
        if not target_box and self.current_tool_part and self.current_tool_part in self.polygons:
            pts = self.polygons.get(self.current_tool_part, [])
            if isinstance(pts, list) and len(pts) >= 3:
                xs = [p[0] for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2]
                ys = [p[1] for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2]
                if xs and ys:
                    target_box = [min(xs), min(ys), max(xs), max(ys)]
            
        if not target_box:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Convert logical image coordinates to view coordinates
        x1, y1, x2, y2 = target_box
        # Use the canvas's scale and offset
        p1 = self.offset + QPointF(x1 * self.scale, y1 * self.scale)
        p2 = self.offset + QPointF(x2 * self.scale, y2 * self.scale)
        rect = QRectF(p1, p2)

        overlay_color = QColor(0, 0, 0, self.blink_alpha)
        
        if self.blink_mode == "INSIDE":
            # Odd Blink: Black out everything OUTSIDE the box
            path = QPainterPath()
            path.addRect(QRectF(self.rect())) # Total area
            path.addRect(rect) # The hole to keep
            painter.fillPath(path, QBrush(overlay_color))
            
        elif self.blink_mode == "OUTSIDE":
            # Even Blink: Black out everything INSIDE the box
            painter.fillRect(rect, QBrush(overlay_color))


class BlinkTrainingThread(QThread):
    result_signal = Signal(str)
    report_signal = Signal(dict)
    error_signal = Signal(str)
    log_signal = Signal(str)
    progress_signal = Signal(int)
    cancelled_signal = Signal()

    def __init__(
        self,
        project_path,
        part_name,
        parent_part,
        epochs,
        batch_size,
        learning_rate=1e-3,
        weight_decay=1e-4,
        input_size=224,
        device="auto",
    ):
        super().__init__()
        self.project_path = project_path
        self.part_name = part_name
        self.parent_part = parent_part
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.input_size = input_size
        self.device = device

    def run(self):
        try:
            try:
                from AntSleap.core.blink_trainer import BlinkExpertTrainer
            except ImportError:
                from core.blink_trainer import BlinkExpertTrainer

            trainer = BlinkExpertTrainer(
                project_path=self.project_path,
                part_name=self.part_name,
                parent_part=self.parent_part,
                learning_rate=self.learning_rate,
                weight_decay=self.weight_decay,
                input_size=self.input_size,
                device=self.device,
            )
            save_path = trainer.train(
                epochs=self.epochs,
                batch_size=self.batch_size,
                log_callback=self.log_signal.emit,
                progress_callback=self.progress_signal.emit,
                stop_callback=self.isInterruptionRequested,
            )
            if self.isInterruptionRequested() and not save_path:
                self.cancelled_signal.emit()
            else:
                self.result_signal.emit(save_path or "")
                report = getattr(trainer, "last_report", None)
                if isinstance(report, dict) and report:
                    self.report_signal.emit(report)
        except Exception as exc:
            self.error_signal.emit(str(exc))


class BlinkExpertTrainingReportDialog(QDialog):
    def __init__(self, report_data, lang="en", parent=None):
        super().__init__(parent)
        self.report_data = dict(report_data or {})
        self.lang = lang
        self.setWindowTitle(translate_blink_text("Blink Training Report", lang))
        self.resize(1100, 760)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        summary = self.report_data.get("validation_summary") or {}
        summary_text = [
            f"Part: {summary.get('part_name', '')}",
            f"Parent: {summary.get('parent_part') or 'N/A'}",
            f"Input size: {summary.get('input_size', '')}",
            f"Learning rate: {summary.get('learning_rate', '')}",
            f"Weight decay: {summary.get('weight_decay', '')}",
            f"Validation samples: {summary.get('validation_count', 0)}",
            f"Model: {self.report_data.get('model_path', '')}",
            f"Report folder: {self.report_data.get('dir', '')}",
            "",
            "Green box = trajectory target / golden box",
            "Cyan box = Blink expert prediction",
        ]
        summary_box = QTextEdit()
        summary_box.setReadOnly(True)
        summary_box.setPlainText("\n".join(str(line) for line in summary_text))
        tabs.addTab(summary_box, translate_blink_text("Summary", lang))

        tabs.addTab(
            self._image_tab(self.report_data.get("metrics")),
            translate_blink_text("Metrics", lang),
        )
        tabs.addTab(
            self._image_tab(self.report_data.get("val")),
            translate_blink_text("Box Validation", lang),
        )

        layout.addWidget(tabs, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button:
            close_button.setText(translate_blink_text("Close", lang))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _image_tab(self, image_path):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        layout = QVBoxLayout(holder)
        label = QLabel(translate_blink_text("No report image generated.", self.lang))
        label.setAlignment(Qt.AlignCenter)
        if image_path and os.path.exists(image_path):
            pix = QPixmap(image_path)
            label.setPixmap(pix.scaled(1000, 680, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(label)
        layout.addStretch()
        scroll.setWidget(holder)
        return scroll


class BucketDeletePreviewDialog(QDialog):
    def __init__(self, parent, *, title, body_text, cleanup_label, cleanup_checked=True, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.current_theme = getattr(parent, "current_theme", "dark")
        self.setModal(True)
        self.setWindowTitle(title)
        self.resize(700, 520)

        layout = QVBoxLayout(self)

        self.body_text = QTextEdit()
        self.body_text.setReadOnly(True)
        self.body_text.setPlainText(body_text)
        self.body_text.setObjectName("blinkBucketDeletePreview")
        layout.addWidget(self.body_text, 1)

        self.cleanup_checkbox = QCheckBox(cleanup_label)
        self.cleanup_checkbox.setChecked(bool(cleanup_checked))
        layout.addWidget(self.cleanup_checkbox)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText(translate_blink_text("Delete Expert Bucket Permanently", self.lang))
        if cancel_button is not None:
            cancel_button.setText(translate_blink_text("Cancel", self.lang))
        self.set_theme(self.current_theme)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def cleanup_requested(self):
        return bool(self.cleanup_checkbox.isChecked())

    def set_theme(self, theme):
        self.current_theme = theme
        apply_theme_dialog_button_box_style(
            getattr(self, "buttons", None),
            ok_role=BUTTON_ROLE_DESTRUCTIVE,
            cancel_role=BUTTON_ROLE_STOP,
            theme=theme,
            ok_extras="min-width: 168px;",
        )


class BucketDeleteTypeConfirmDialog(QDialog):
    def __init__(self, parent, *, title, prompt_text, expected_text, placeholder_text="", lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.expected_text = str(expected_text or "")
        self.current_theme = getattr(parent, "current_theme", "dark")
        self.setModal(True)
        self.setWindowTitle(title)
        self.resize(420, 160)

        layout = QVBoxLayout(self)
        self.prompt_label = QLabel(prompt_text)
        self.prompt_label.setWordWrap(True)
        layout.addWidget(self.prompt_label)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(placeholder_text)
        layout.addWidget(self.input_edit)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #d9534f;")
        layout.addWidget(self.error_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText(translate_blink_text("Delete Expert Bucket Permanently", self.lang))
        if cancel_button is not None:
            cancel_button.setText(translate_blink_text("Cancel", self.lang))
        self.set_theme(self.current_theme)
        self.buttons.accepted.connect(self._accept_if_matches)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _accept_if_matches(self):
        if self.input_edit.text() == self.expected_text:
            self.accept()
            return
        self.error_label.setText(
            translate_blink_text("You must type '{0}' exactly to continue.", self.lang).format(self.expected_text)
        )

    def typed_text(self):
        return self.input_edit.text()

    def set_theme(self, theme):
        self.current_theme = theme
        apply_theme_dialog_button_box_style(
            getattr(self, "buttons", None),
            ok_role=BUTTON_ROLE_DESTRUCTIVE,
            cancel_role=BUTTON_ROLE_STOP,
            theme=theme,
            ok_extras="min-width: 168px;",
        )
        c = get_theme_config(theme)
        self.error_label.setStyleSheet(f"color: {c['error']}; font-weight: 600;")

class BlinkLabWidget(QWidget):
    global_labels_updated = Signal() # Signal to notify MainWindow to refresh
    route_registry_refresh_requested = Signal()
    start_center_requested = Signal()
    agent_requested = Signal(dict)

    def __init__(
        self,
        engine,
        project_manager,
        lang="en",
        parent=None,
        blink_epochs=5,
        blink_batch=2,
        blink_lr=1e-3,
        blink_weight_decay=1e-4,
        blink_input_size=224,
        runtime_device="auto",
    ):
        super().__init__(parent)
        self.engine = engine
        self.pm = project_manager
        self.lang = lang
        self.current_theme = "dark"
        self.default_training_epochs = self._clamp_training_value(blink_epochs, 1, 500, 5)
        self.default_training_batch = self._clamp_training_value(blink_batch, 1, 64, 2)
        self.default_learning_rate = self._coerce_float(blink_lr, 1e-3)
        self.default_weight_decay = self._coerce_float(blink_weight_decay, 1e-4)
        self.default_input_size = self._normalize_input_size(blink_input_size)
        self.runtime_device = str(runtime_device or "auto")
        self.training_thread = None
        self.active_session = None
        self.session_target_part = None
        self.session_dirty = False
        self.training_route_context = None
        self.box_tool_role = "shrink"
        self.current_image_path = None
        self.raw_labels = {}
        self.raw_manual_boxes = {}
        self.raw_auto_boxes = {}
        self.init_ui()
        self.retranslate_ui()

    def _clamp_training_value(self, value, low, high, fallback):
        try:
            number = int(value)
        except Exception:
            number = int(fallback)
        return max(int(low), min(int(high), number))

    def _coerce_float(self, value, fallback):
        try:
            number = float(value)
        except Exception:
            number = float(fallback)
        return number if number > 0 else float(fallback)

    def _normalize_input_size(self, value):
        try:
            side = int(value[0] if isinstance(value, (list, tuple)) else value)
        except Exception:
            side = 224
        allowed = [224, 384, 512]
        return min(allowed, key=lambda candidate: abs(candidate - side))

    def set_training_defaults(
        self,
        epochs=None,
        batch_size=None,
        learning_rate=None,
        weight_decay=None,
        input_size=None,
        runtime_device=None,
        apply_to_controls=True,
    ):
        if epochs is not None:
            self.default_training_epochs = self._clamp_training_value(epochs, 1, 500, self.default_training_epochs)
        if batch_size is not None:
            self.default_training_batch = self._clamp_training_value(batch_size, 1, 64, self.default_training_batch)
        if learning_rate is not None:
            self.default_learning_rate = self._coerce_float(learning_rate, self.default_learning_rate)
        if weight_decay is not None:
            self.default_weight_decay = self._coerce_float(weight_decay, self.default_weight_decay)
        if input_size is not None:
            self.default_input_size = self._normalize_input_size(input_size)
        if runtime_device is not None:
            self.runtime_device = str(runtime_device or "auto")
        if apply_to_controls and hasattr(self, "spin_epochs") and hasattr(self, "spin_batch"):
            self.spin_epochs.setValue(self.default_training_epochs)
            self.spin_batch.setValue(self.default_training_batch)
            if hasattr(self, "edit_lr"):
                self.edit_lr.setText(f"{self.default_learning_rate:g}")
            if hasattr(self, "edit_weight_decay"):
                self.edit_weight_decay.setText(f"{self.default_weight_decay:g}")
            if hasattr(self, "combo_input_size"):
                index = self.combo_input_size.findData(self.default_input_size)
                self.combo_input_size.setCurrentIndex(index if index >= 0 else 0)

    def tr(self, text):
        return translate_blink_text(text, self.lang)

    def change_language(self, lang):
        self.lang = lang
        self.retranslate_ui()

    def retranslate_ui(self):
        self.sidebar.setTitle(self.tr("Expert Taxonomy"))
        self.btn_sync.setText(self.tr("Sync from Workbench"))
        self.btn_start_center.setText(self.tr("Start Center"))
        self.btn_ask_agent.setText(self.tr("Ask Agent"))
        self.tool_group_box.setTitle(self.tr("Drawing Tools"))
        self.rb_draw.setText(self.tr("Draw Polygon"))
        self.rb_box_prompt.setText(self.tr("Draw Box (For SAM Draft)"))
        self.rb_box.setText(self.tr("Draw Box (For Shrink)"))
        self.expert_registry.setTitle(self.tr("Trained Experts"))
        self.expert_tree.setHeaderLabels([self.tr("Model File"), self.tr("Size")])
        self.btn_appoint_route_expert.setText(self.tr("Appoint to Current Route"))
        self.btn_edit_expert_note.setText(self.tr("Edit Note"))
        self.btn_edit_expert_note.setToolTip(self.tr("Edit a display note only. The model file name and route binding stay unchanged."))
        self.btn_delete_expert.setText(self.tr("Delete"))
        self.btn_refresh_experts.setText(self.tr("Refresh"))
        self.training_log_box.setTitle(self.tr("Training Log"))
        self.btn_clear_training_log.setText(self.tr("Clear Log"))
        if not self.training_log_console.toPlainText().strip():
            self.training_log_console.setPlaceholderText(self.tr("Blink training log will appear here during expert training."))
        self.controls.setTitle(self.tr("Blink Control Room"))
        self.btn_blink.setText(self.tr("BLINK SWITCH\n(Space)"))
        self.lbl_shrink_logic.setText(self.tr("Shrink Logic:"))
        self.btn_auto_annotate.setText(self.tr("AUTO-ANNOTATE DRAFT"))
        self.btn_auto_shrink.setText(self.tr("EXECUTE AUTO-SHRINK"))
        self.btn_apply_global.setText(self.tr("APPLY TO GLOBAL"))
        self.training_settings_box.setTitle(self.tr("Training Settings"))
        self.lbl_epochs.setText(self.tr("Epochs:"))
        self.lbl_batch_size.setText(self.tr("Batch Size:"))
        self.lbl_learning_rate.setText(self.tr("Learning Rate:"))
        self.lbl_weight_decay.setText(self.tr("Weight Decay:"))
        self.lbl_input_size.setText(self.tr("Input Size:"))
        self.btn_train_expert.setText(self.tr("TRAIN EXPERT MODEL"))
        self.btn_stop_training.setText(self.tr("STOP TRAINING"))
        self.lbl_training_progress.setText(self.tr("Training Progress"))
        if self.has_active_session():
            self.lbl_status.setText(self._session_focus_status())
        elif self.lbl_status.text() in {"Mode: STANDBY", "模式：待命", ""}:
            self.lbl_status.setText(self.tr("Mode: STANDBY"))

    def set_theme(self, theme):
        self.current_theme = theme
        c = get_theme_config(theme)
        self.lbl_status.setStyleSheet(f"color: {c['success']}; font-weight: bold;")
        for label in [self.lbl_epochs, self.lbl_batch_size, self.lbl_learning_rate, self.lbl_weight_decay, self.lbl_input_size]:
            label.setStyleSheet(f"color: {c['text_soft']}; font-weight: 600;")
        self.training_settings_box.setStyleSheet(
            f"QGroupBox {{ background-color: {c['bg_surface_alt']}; border: 1px solid {c['border']}; "
            f"border-radius: 10px; margin-top: 10px; padding-top: 12px; }}"
            f"QGroupBox::title {{ color: {c['accent']}; subcontrol-origin: margin; "
            f"subcontrol-position: top left; left: 10px; padding: 0 4px; }}"
        )
        apply_theme_button_style(self.btn_sync, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_start_center, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_ask_agent, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_appoint_route_expert, BUTTON_ROLE_COMMIT, "", theme)
        apply_theme_button_style(self.btn_edit_expert_note, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_delete_expert, BUTTON_ROLE_DESTRUCTIVE, "", theme)
        apply_theme_button_style(self.btn_refresh_experts, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(
            self.btn_blink,
            BUTTON_ROLE_NEUTRAL,
            "font-size: 14px; font-weight: bold; border-radius: 10px;",
            theme,
        )
        apply_theme_button_style(self.btn_auto_annotate, BUTTON_ROLE_RUN, "", theme)
        apply_theme_button_style(self.btn_auto_shrink, BUTTON_ROLE_RUN, "", theme)
        apply_theme_button_style(self.btn_apply_global, BUTTON_ROLE_COMMIT, "font-weight: bold;", theme)
        apply_theme_button_style(self.btn_train_expert, BUTTON_ROLE_RUN, "font-weight: bold;", theme)
        apply_theme_button_style(self.btn_stop_training, BUTTON_ROLE_STOP, "font-weight: bold;", theme)
        apply_theme_button_style(self.btn_clear_training_log, BUTTON_ROLE_NEUTRAL, "", theme)
        self.training_log_console.setStyleSheet(
            f"background-color: {c['bg_input']}; color: {c['text_main']};"
            f"font-family: Consolas, 'Courier New', monospace; font-size: 9pt;"
            f"border: 1px solid {c['border']}; border-radius: 10px; padding: 8px;"
        )
        if hasattr(self.canvas, "set_theme"):
            self.canvas.set_theme(theme)

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        
        # Sidebar: Parts and Experts
        self.sidebar = QGroupBox("Expert Taxonomy")
        self.sidebar.setMinimumWidth(380)
        apply_surface_role(self.sidebar, SURFACE_ROLE_PANEL, "blinkSidebarPanel")
        s_layout = QVBoxLayout(self.sidebar)
        s_layout.setContentsMargins(12, 12, 12, 12)
        s_layout.setSpacing(10)
        shortcut_row = QHBoxLayout()
        shortcut_row.setSpacing(8)
        self.btn_start_center = QPushButton("Start Center")
        self.btn_start_center.setObjectName("blinkStartCenterButton")
        self.btn_start_center.clicked.connect(self.start_center_requested.emit)
        self.btn_ask_agent = QPushButton("Ask Agent")
        self.btn_ask_agent.setObjectName("blinkAskAgentButton")
        self.btn_ask_agent.clicked.connect(lambda: self.agent_requested.emit(self.get_agent_context()))
        apply_semantic_button_style(self.btn_start_center, BUTTON_ROLE_NEUTRAL)
        apply_semantic_button_style(self.btn_ask_agent, BUTTON_ROLE_NEUTRAL)
        shortcut_row.addWidget(self.btn_start_center)
        shortcut_row.addWidget(self.btn_ask_agent)
        s_layout.addLayout(shortcut_row)
        self.part_list = QListWidget()
        self.part_list.itemClicked.connect(self.on_part_selected)
        s_layout.addWidget(self.part_list)
        
        self.btn_sync = QPushButton("Sync from Workbench")
        self.btn_sync.clicked.connect(lambda: self.sync_data(force=True))
        apply_semantic_button_style(self.btn_sync, BUTTON_ROLE_NEUTRAL)
        s_layout.addWidget(self.btn_sync)
        
        # Tools
        self.tool_group_box = QGroupBox("Drawing Tools")
        apply_surface_role(self.tool_group_box, SURFACE_ROLE_SUBTLE, "blinkToolPanel")
        t_layout = QVBoxLayout(self.tool_group_box)
        self.tool_group = QButtonGroup(self)
        
        self.rb_draw = QRadioButton("Draw Polygon")
        self.rb_box_prompt = QRadioButton("Draw Box (For SAM Draft)")
        self.rb_box = QRadioButton("Draw Box (For Shrink)")
        self.rb_box.setChecked(True) # Default for shrink
        
        self.tool_group.addButton(self.rb_draw, 1)
        self.tool_group.addButton(self.rb_box_prompt, 2)
        self.tool_group.addButton(self.rb_box, 3)
        
        t_layout.addWidget(self.rb_draw)
        t_layout.addWidget(self.rb_box_prompt)
        t_layout.addWidget(self.rb_box)
        s_layout.addWidget(self.tool_group_box)
        self.tool_group.buttonClicked.connect(self.on_tool_changed)
        
        # Central Canvas
        self.canvas = BlinkCanvas()
        self.canvas.setObjectName("blinkCanvas")
        self.canvas.set_mode("BOX_PROMPT") # Default mode
        self.canvas.magic_box_completed.connect(self.on_box_drawn)
        self.canvas.polygon_completed.connect(self.on_local_polygon_changed)
        self.canvas_shell = QWidget()
        apply_surface_role(self.canvas_shell, SURFACE_ROLE_CANVAS, "blinkCanvasShell")
        canvas_layout = QVBoxLayout(self.canvas_shell)
        canvas_layout.setContentsMargins(12, 12, 12, 12)
        canvas_layout.addWidget(self.canvas)
        
        # --- Expert Registry Panel (New) ---
        self.expert_registry = QGroupBox("Trained Experts")
        apply_surface_role(self.expert_registry, SURFACE_ROLE_SUBTLE, "blinkExpertRegistryPanel")
        er_layout = QVBoxLayout(self.expert_registry)
        self.expert_tree = QTreeWidget()
        self.expert_tree.setHeaderLabels(["Model File", "Size"])
        self.expert_tree.setAlternatingRowColors(True)
        self.expert_tree.setMinimumHeight(180)
        self.expert_tree.setTextElideMode(Qt.ElideMiddle)
        self.expert_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.expert_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.expert_tree.setColumnWidth(0, 300)
        self.expert_tree.itemSelectionChanged.connect(self._update_delete_expert_tooltip)
        er_layout.addWidget(self.expert_tree)
        
        btn_layout_er = QHBoxLayout()
        self.btn_appoint_route_expert = QPushButton("Appoint to Current Route")
        self.btn_appoint_route_expert.clicked.connect(self.appoint_selected_expert_to_current_route)
        self.btn_edit_expert_note = QPushButton("Edit Note")
        self.btn_edit_expert_note.clicked.connect(self.edit_selected_expert_note)
        self.btn_edit_expert_note.setToolTip(self.tr("Edit a display note only. The model file name and route binding stay unchanged."))
        self.btn_delete_expert = QPushButton("Delete")
        self.btn_delete_expert.clicked.connect(self.delete_expert_model)
        self.btn_delete_expert.setToolTip(self.tr("Delete the selected expert model file from disk."))
        self.btn_refresh_experts = QPushButton("Refresh")
        self.btn_refresh_experts.clicked.connect(self.refresh_expert_registry)
        apply_semantic_button_style(self.btn_appoint_route_expert, BUTTON_ROLE_COMMIT)
        apply_semantic_button_style(self.btn_edit_expert_note, BUTTON_ROLE_NEUTRAL)
        apply_semantic_button_style(self.btn_delete_expert, BUTTON_ROLE_DESTRUCTIVE)
        apply_semantic_button_style(self.btn_refresh_experts, BUTTON_ROLE_NEUTRAL)
        
        btn_layout_er.addWidget(self.btn_appoint_route_expert)
        btn_layout_er.addWidget(self.btn_edit_expert_note)
        btn_layout_er.addWidget(self.btn_delete_expert)
        btn_layout_er.addWidget(self.btn_refresh_experts)
        er_layout.addLayout(btn_layout_er)
        s_layout.addWidget(self.expert_registry)
        
        # --- Control Panel ---
        self.controls = QGroupBox("Blink Control Room")
        apply_surface_role(self.controls, SURFACE_ROLE_PANEL, "blinkControlsPanel")
        c_layout = QVBoxLayout(self.controls)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setSpacing(10)

        self.session_panel = QWidget()
        apply_surface_role(self.session_panel, SURFACE_ROLE_SUBTLE, "blinkSessionPanel")
        session_layout = QVBoxLayout(self.session_panel)
        session_layout.setContentsMargins(10, 10, 10, 10)
        session_layout.setSpacing(8)
        
        self.lbl_status = QLabel("Mode: STANDBY")
        self.lbl_status.setObjectName("StatusPill")
        self.lbl_status.setWordWrap(True)
        session_layout.addWidget(self.lbl_status)
        
        self.btn_blink = QPushButton("BLINK SWITCH\\n(Space)")
        self.btn_blink.setFixedHeight(78)
        apply_semantic_button_style(self.btn_blink, BUTTON_ROLE_NEUTRAL, "font-size: 14px; font-weight: bold; border-radius: 10px;")
        self.btn_blink.clicked.connect(self.cycle_blink)
        session_layout.addWidget(self.btn_blink)
        c_layout.addWidget(self.session_panel)

        self.action_panel = QWidget()
        apply_surface_role(self.action_panel, SURFACE_ROLE_RAISED, "blinkActionPanel")
        action_layout = QVBoxLayout(self.action_panel)
        action_layout.setContentsMargins(10, 10, 10, 10)
        action_layout.setSpacing(8)

        self.lbl_shrink_logic = QLabel("Shrink Logic:")
        action_layout.addWidget(self.lbl_shrink_logic)
        self.prog_shrink = QProgressBar()
        action_layout.addWidget(self.prog_shrink)

        self.btn_auto_annotate = QPushButton("AUTO-ANNOTATE DRAFT")
        self.btn_auto_annotate.setFixedHeight(44)
        apply_semantic_button_style(self.btn_auto_annotate, BUTTON_ROLE_RUN)
        self.btn_auto_annotate.clicked.connect(self.run_auto_annotate)
        action_layout.addWidget(self.btn_auto_annotate)

        self.btn_auto_shrink = QPushButton("EXECUTE AUTO-SHRINK")
        self.btn_auto_shrink.setFixedHeight(44)
        apply_semantic_button_style(self.btn_auto_shrink, BUTTON_ROLE_RUN)
        self.btn_auto_shrink.clicked.connect(self.run_auto_shrink)
        action_layout.addWidget(self.btn_auto_shrink)
        
        self.btn_apply_global = QPushButton("APPLY TO GLOBAL")
        self.btn_apply_global.setFixedHeight(54)
        apply_semantic_button_style(self.btn_apply_global, BUTTON_ROLE_COMMIT, "font-weight: bold;")
        self.btn_apply_global.clicked.connect(self.apply_to_global)
        action_layout.addWidget(self.btn_apply_global)
        c_layout.addWidget(self.action_panel)
        
        # --- Training Config (New) ---
        self.training_panel = QWidget()
        apply_surface_role(self.training_panel, SURFACE_ROLE_SUBTLE, "blinkTrainingPanel")
        training_panel_layout = QVBoxLayout(self.training_panel)
        training_panel_layout.setContentsMargins(10, 10, 10, 10)
        training_panel_layout.setSpacing(8)

        self.training_settings_box = QGroupBox("Training Settings")
        apply_surface_role(self.training_settings_box, SURFACE_ROLE_SUBTLE, "blinkTrainingSettingsBox")
        tc_layout = QVBoxLayout(self.training_settings_box)
        tc_layout.setContentsMargins(10, 12, 10, 10)
        tc_layout.setSpacing(8)
        
        self.spin_epochs = QSpinBox()
        self.spin_epochs.setRange(1, 500)
        self.spin_epochs.setValue(self.default_training_epochs)
        self.spin_epochs.setMinimumHeight(30)
        
        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(1, 64)
        self.spin_batch.setValue(self.default_training_batch)
        self.spin_batch.setMinimumHeight(30)
        
        self.lbl_epochs = QLabel("Epochs:")
        self.lbl_epochs.setObjectName("BlinkFormLabel")
        self.lbl_batch_size = QLabel("Batch Size:")
        self.lbl_batch_size.setObjectName("BlinkFormLabel")
        self.lbl_learning_rate = QLabel("Learning Rate:")
        self.lbl_learning_rate.setObjectName("BlinkFormLabel")
        self.lbl_weight_decay = QLabel("Weight Decay:")
        self.lbl_weight_decay.setObjectName("BlinkFormLabel")
        self.lbl_input_size = QLabel("Input Size:")
        self.lbl_input_size.setObjectName("BlinkFormLabel")
        tc_layout.addWidget(self.lbl_epochs)
        tc_layout.addWidget(self.spin_epochs)
        tc_layout.addWidget(self.lbl_batch_size)
        tc_layout.addWidget(self.spin_batch)
        self.edit_lr = QLineEdit(f"{self.default_learning_rate:g}")
        self.edit_lr.setMinimumHeight(30)
        self.edit_weight_decay = QLineEdit(f"{self.default_weight_decay:g}")
        self.edit_weight_decay.setMinimumHeight(30)
        self.combo_input_size = NoWheelComboBox()
        for side in [224, 384, 512]:
            self.combo_input_size.addItem(f"{side} x {side}", side)
        input_index = self.combo_input_size.findData(self.default_input_size)
        self.combo_input_size.setCurrentIndex(input_index if input_index >= 0 else 0)
        tc_layout.addWidget(self.lbl_learning_rate)
        tc_layout.addWidget(self.edit_lr)
        tc_layout.addWidget(self.lbl_weight_decay)
        tc_layout.addWidget(self.edit_weight_decay)
        tc_layout.addWidget(self.lbl_input_size)
        tc_layout.addWidget(self.combo_input_size)
        training_panel_layout.addWidget(self.training_settings_box)
        
        self.btn_train_expert = QPushButton("TRAIN EXPERT MODEL")
        self.btn_train_expert.setFixedHeight(54)
        apply_semantic_button_style(self.btn_train_expert, BUTTON_ROLE_RUN, "font-weight: bold;")
        self.btn_train_expert.clicked.connect(self.train_expert_model)
        training_panel_layout.addWidget(self.btn_train_expert)

        self.btn_stop_training = QPushButton("STOP TRAINING")
        self.btn_stop_training.setFixedHeight(40)
        self.btn_stop_training.setEnabled(False)
        apply_semantic_button_style(self.btn_stop_training, BUTTON_ROLE_STOP, "font-weight: bold;")
        self.btn_stop_training.clicked.connect(self.stop_expert_training)
        training_panel_layout.addWidget(self.btn_stop_training)

        self.lbl_training_progress = QLabel("Training Progress")
        self.lbl_training_progress.setObjectName("BlinkFormLabel")
        training_panel_layout.addWidget(self.lbl_training_progress)
        self.prog_training = QProgressBar()
        self.prog_training.setRange(0, 100)
        self.prog_training.setValue(0)
        training_panel_layout.addWidget(self.prog_training)

        self.training_log_box = QGroupBox("Training Log")
        apply_surface_role(self.training_log_box, SURFACE_ROLE_SUBTLE, "blinkTrainingLogBox")
        training_log_layout = QVBoxLayout(self.training_log_box)
        training_log_layout.setContentsMargins(8, 8, 8, 8)
        training_log_layout.setSpacing(8)

        self.training_log_console = QTextEdit()
        self.training_log_console.setReadOnly(True)
        self.training_log_console.setObjectName("blinkTrainingLogConsole")
        self.training_log_console.setMinimumHeight(300)
        self.training_log_console.setSizePolicy(self.training_log_console.sizePolicy().horizontalPolicy(), QSizePolicy.Expanding)
        self.training_log_console.setPlaceholderText("Blink training log will appear here during expert training.")
        training_log_layout.addWidget(self.training_log_console, 1)

        self.btn_clear_training_log = QPushButton("Clear Log")
        self.btn_clear_training_log.clicked.connect(self.training_log_console.clear)
        apply_semantic_button_style(self.btn_clear_training_log, BUTTON_ROLE_NEUTRAL)
        training_log_layout.addWidget(self.btn_clear_training_log)
        training_panel_layout.addWidget(self.training_log_box, 1)
        c_layout.addWidget(self.training_panel, 1)
        c_layout.addStretch(0)
        
        # Splitter assembly
        self.blink_splitter = QSplitter(Qt.Horizontal)
        self.blink_splitter.setObjectName("blinkMainSplitter")
        self.blink_splitter.setChildrenCollapsible(False)
        self.blink_splitter.setHandleWidth(8)
        self.blink_splitter.addWidget(self.sidebar)
        self.blink_splitter.addWidget(self.canvas_shell)
        
        right_scroll = QScrollArea()
        right_scroll.setObjectName("blinkControlsScroll")
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        right_scroll.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored)
        right_scroll.setFixedWidth(336)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.controls)
        right_panel.setMinimumWidth(320)
        right_scroll.setWidget(right_panel)
        self.blink_splitter.addWidget(right_scroll)
        self.blink_splitter.setStretchFactor(0, 2)
        self.blink_splitter.setStretchFactor(1, 5)
        self.blink_splitter.setStretchFactor(2, 2)
        self.blink_splitter.setSizes([420, 800, 336])
        
        layout.addWidget(self.blink_splitter)
        self._update_delete_expert_tooltip()

    def get_agent_context(self):
        active_session = self.active_session if isinstance(self.active_session, dict) else {}
        recent_log = ""
        if hasattr(self, "training_log_console"):
            recent_log = "\n".join(self.training_log_console.toPlainText().splitlines()[-6:])
        return {
            "source_workbench": "blink",
            "project_type": "2d_stl",
            "project_path": getattr(self.pm, "current_project_path", "") or "",
            "active_image_path": self.current_image_path or active_session.get("image_path", "") or "",
            "active_label_role": "blink_session" if active_session else "",
            "selected_part": self.session_target_part or active_session.get("target_part", "") or "",
            "recent_log_excerpt": recent_log,
        }

    def load_image(self, path):
        if path:
            self.current_image_path = path
            if not self.has_active_session():
                self.canvas.load_image(path) # Fallback full image
            self.sync_data()

    def has_active_session(self):
        return bool(self.active_session)

    def has_unsaved_session_changes(self):
        return bool(self.active_session and self.session_dirty)

    def _confirm_discard_unsaved_session_changes(self, action_name):
        reply = themed_yes_no_question(
            self,
            self.tr("Discard Blink Edits?"),
            self.tr("The current Blink session has unapplied edits. Discard them and {0}?").format(self.tr(action_name)),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        return reply == QMessageBox.StandardButton.Yes

    def is_session_for_image(self, image_path):
        if not self.active_session or not image_path:
            return False
        session_image = self.active_session.get("image_path")
        if not isinstance(session_image, str) or not session_image:
            return False
        return os.path.normpath(session_image) == os.path.normpath(image_path)

    def _session_focus_box(self):
        image_path = getattr(self, "current_image_path", None)
        if not self.active_session or not self.is_session_for_image(image_path):
            return None
        focus_roi = self.active_session.get("focus_roi", {})
        box = focus_roi.get("box")
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            return None
        try:
            clean_box = [float(v) for v in box]
        except Exception:
            return None
        if clean_box[2] <= clean_box[0] or clean_box[3] <= clean_box[1]:
            return None
        return clean_box

    def _session_focus_status(self):
        if not self.active_session:
            return self.tr("Focus: Full Image")
        focus_roi = self.active_session.get("focus_roi", {})
        focus_part = focus_roi.get("part", "ROI")
        source = focus_roi.get("source", "manual")
        source_text = self.tr("Manual Box") if source == "manual" else self.tr("Auto Box")
        target_part = self.active_session.get("target_part", focus_part)
        return self.tr("Session: {0} via {1} ({2})").format(target_part, focus_part, source_text)

    def start_session(self, session, labels=None, manual_boxes=None, auto_boxes=None):
        if not isinstance(session, dict):
            self.lbl_status.setText(self.tr("Error: Invalid Blink session."))
            return False

        if self.has_unsaved_session_changes() and not self._confirm_discard_unsaved_session_changes("open a new session"):
            self.lbl_status.setText(self.tr("Blink session kept. Apply or discard edits before switching sessions."))
            return False

        image_path = session.get("image_path")
        target_part = session.get("target_part")
        if not image_path or not target_part:
            self.lbl_status.setText(self.tr("Error: Incomplete Blink session."))
            return False

        self.active_session = {
            "image_path": image_path,
            "target_part": target_part,
            "focus_roi": dict(session.get("focus_roi") or {}),
        }
        self.session_target_part = target_part
        self.session_dirty = False
        self.current_image_path = image_path

        self.raw_labels = labels if labels is not None else self.pm.get_labels(image_path)
        self.raw_manual_boxes = manual_boxes if manual_boxes is not None else self.pm.get_boxes(image_path)
        self.raw_auto_boxes = auto_boxes if auto_boxes is not None else self.pm.get_auto_boxes(image_path)
        self.sync_data()
        self.lbl_status.setText(self._session_focus_status())
        return True

    def refresh_from_workbench(self, image_path, labels, manual_boxes, auto_boxes):
        if not image_path:
            return False
        if self.has_active_session() and not self.is_session_for_image(image_path):
            return False
        if self.has_unsaved_session_changes():
            self.lbl_status.setText(self.tr("Blink session has unsaved edits. Apply to Global or click Sync to discard before reloading."))
            return False

        previous_image = getattr(self, "current_image_path", None)
        same_image = bool(previous_image) and os.path.normpath(previous_image) == os.path.normpath(image_path)
        has_loaded_pixmap = bool(self.canvas.original_pixmap and not self.canvas.original_pixmap.isNull())

        self.current_image_path = image_path
        self.raw_labels = labels or {}
        self.raw_manual_boxes = manual_boxes or {}
        self.raw_auto_boxes = auto_boxes or {}
        self.sync_data(preserve_view=same_image and has_loaded_pixmap)
        return True

    def set_data(self, labels, manual_boxes, auto_boxes, preserve_view=False):
        self.raw_labels = labels or {}
        self.raw_manual_boxes = manual_boxes or {}
        self.raw_auto_boxes = auto_boxes or {}
        self.apply_zoom_focus(preserve_view=preserve_view)

    def apply_zoom_focus(self, preserve_view=False):
        """
        默认显示完整大图（符合当前工作流），并使用 CoordinateMapper 统一映射。
        可选模式：当 enable_head_focus_crop=True 且有 Head 框时，切换为头部裁剪聚焦。
        """
        import cv2
        from PySide6.QtGui import QImage, QPixmap
        try:
            from AntSleap.core.projection import CoordinateMapper
        except ImportError:
            from core.projection import CoordinateMapper

        image_path = getattr(self, "current_image_path", None)
        if not image_path:
            self.canvas.set_boxes(self.raw_manual_boxes, self.raw_auto_boxes)
            self.canvas.set_polygons(self.raw_labels)
            return

        img_np = cv2.imread(image_path)
        if img_np is None:
            self.canvas.set_boxes(self.raw_manual_boxes, self.raw_auto_boxes)
            self.canvas.set_polygons(self.raw_labels)
            return

        img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        h, w, _ = img_np.shape

        # 默认：完整大图
        focus_mode = "FULL"
        focus_box = [0.0, 0.0, float(w), float(h)]
        target_size = (w, h)
        focus_status = self.tr("Focus: Full Image")

        session_focus_box = self._session_focus_box()
        if session_focus_box:
            focus_mode = "SESSION_CROP"
            focus_box = session_focus_box
            target_size = (800, 800)
            focus_status = self._session_focus_status()

        self.mapper = CoordinateMapper((w, h), focus_box, target_size=target_size)
        self.zoomed_img_np = self.mapper.crop_and_resize(img_np) if focus_mode != "FULL" else img_np

        qimg = QImage(
            self.zoomed_img_np.data,
            self.zoomed_img_np.shape[1],
            self.zoomed_img_np.shape[0],
            self.zoomed_img_np.strides[0],
            QImage.Format_RGB888,
        )
        self.canvas.original_pixmap = QPixmap.fromImage(qimg)
        self.canvas.apply_enhancements()
        if not preserve_view:
            self.canvas.fit_to_view()

        crop_x1, crop_y1, crop_x2, crop_y2 = (
            self.mapper.crop_x1,
            self.mapper.crop_y1,
            self.mapper.crop_x2,
            self.mapper.crop_y2,
        )

        def _box_intersects_crop(box):
            if not isinstance(box, (list, tuple)) or len(box) != 4:
                return False
            try:
                bx1, by1, bx2, by2 = [float(v) for v in box]
            except Exception:
                return False
            if bx1 > bx2:
                bx1, bx2 = bx2, bx1
            if by1 > by2:
                by1, by2 = by2, by1
            return not (bx2 < crop_x1 or bx1 > crop_x2 or by2 < crop_y1 or by1 > crop_y2)

        def _normalize_polygon_points(polys):
            if not isinstance(polys, list) or not polys:
                return []

            candidate = polys
            first = polys[0]
            if isinstance(first, (list, tuple)) and first and isinstance(first[0], (list, tuple)):
                valid_contours = [c for c in polys if isinstance(c, (list, tuple)) and len(c) > 0]
                candidate = max(valid_contours, key=lambda c: len(c), default=[])

            clean = []
            for pt in candidate:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    try:
                        clean.append([float(pt[0]), float(pt[1])])
                    except Exception:
                        continue
            return clean

        def _poly_intersects_crop(points):
            if len(points) < 3:
                return False
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            return not (max(xs) < crop_x1 or min(xs) > crop_x2 or max(ys) < crop_y1 or min(ys) > crop_y2)

        local_manual_boxes = {}
        for part, box in self.raw_manual_boxes.items():
            if _box_intersects_crop(box):
                local_manual_boxes[part] = self.mapper.bbox_global_to_local(box)

        local_auto_boxes = {}
        for part, box in self.raw_auto_boxes.items():
            if _box_intersects_crop(box):
                local_auto_boxes[part] = self.mapper.bbox_global_to_local(box)

        local_labels = {}
        editable_target = self.session_target_part if self.is_session_for_image(image_path) else None
        for part, polys in self.raw_labels.items():
            if editable_target and part != editable_target:
                continue
            clean_global_poly = _normalize_polygon_points(polys)
            if not _poly_intersects_crop(clean_global_poly):
                continue

            local_poly = self.mapper.poly_global_to_local(clean_global_poly)
            clamped_local_poly = []
            for x, y in local_poly:
                cx = max(0.0, min(float(x), float(self.mapper.target_w - 1)))
                cy = max(0.0, min(float(y), float(self.mapper.target_h - 1)))
                clamped_local_poly.append([cx, cy])

            if len(clamped_local_poly) >= 3:
                local_labels[part] = clamped_local_poly

        self.canvas.set_boxes(local_manual_boxes, local_auto_boxes)
        self.canvas.set_polygons(local_labels)
        self.lbl_status.setText(focus_status)

    def sync_data(self, force=False, preserve_view=False):
        """Sync taxonomy and current image annotations from the main workbench."""
        if force and self.has_unsaved_session_changes():
            if not self._confirm_discard_unsaved_session_changes("reload from the workbench"):
                self.lbl_status.setText(self.tr("Sync cancelled. Blink session edits were kept."))
                return
            self.session_dirty = False

        self.part_list.blockSignals(True)
        self.part_list.clear()
        taxonomy = self.pm.project_data.get("taxonomy", [])
        if self.has_active_session() and self.session_target_part:
            visible_parts = [self.session_target_part]
        else:
            visible_parts = taxonomy
        self.part_list.addItems(visible_parts)
        self.part_list.setEnabled(not self.has_active_session())

        # 保持或设置当前部位，避免 Blink Switch 因无 active part 看起来“没反应”
        if visible_parts:
            if self.has_active_session() and self.session_target_part:
                desired_part = self.session_target_part
            else:
                desired_part = self.canvas.current_tool_part if self.canvas.current_tool_part in visible_parts else visible_parts[0]
            desired_part = str(desired_part)
            self.canvas.current_tool_part = desired_part
            items = self.part_list.findItems(desired_part, Qt.MatchFlag.MatchExactly)
            if items:
                self.part_list.setCurrentItem(items[0])
                self.lbl_status.setText(self.tr("Focus: {0}").format(desired_part))
        self.part_list.blockSignals(False)

        self.refresh_expert_registry()

        # 关键修复：除了 taxonomy，还要拉取当前图片的最新标注数据（points/polygons/boxes）
        image_path = getattr(self, "current_image_path", None)
        if image_path:
            self.set_data(
                self.pm.get_labels(image_path),
                self.pm.get_boxes(image_path),
                self.pm.get_auto_boxes(image_path),
                preserve_view=preserve_view,
            )
            if self.has_active_session():
                self.lbl_status.setText(self._session_focus_status())
            else:
                self.lbl_status.setText(self.tr("Synced from Workbench"))

    def refresh_expert_registry(self):
        """Scan the weights/experts/ directory and list trained models in a tree."""
        self.expert_tree.clear()
        expert_dir = self._expert_root_dir()
        if not os.path.exists(expert_dir):
            self._update_delete_expert_tooltip()
            return
        expert_notes = load_expert_notes(self.engine.weights_dir)
            
        for part_folder in os.listdir(expert_dir):
            part_path = os.path.join(expert_dir, part_folder)
            if not os.path.isdir(part_path):
                continue
            if not self._is_safe_expert_bucket_path(part_path, expected_part_name=part_folder):
                continue
            
            part_item = QTreeWidgetItem(self.expert_tree)
            part_item.setText(0, part_folder)
            part_item.setToolTip(0, part_folder)
            part_item.setExpanded(True)
            part_item.setData(0, Qt.UserRole, None)
            part_item.setData(0, Qt.UserRole + 1, {"bucket_path": part_path, "part_name": part_folder})
            
            pth_files = [f for f in os.listdir(part_path) if f.endswith(".pth")]
            pth_files.sort(reverse=True)
            
            for pth in pth_files:
                file_path = os.path.join(part_path, pth)
                if not self._is_safe_expert_file_path(file_path, expected_bucket_path=part_path):
                    continue
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                
                model_item = QTreeWidgetItem(part_item)
                
                full_expert_name = f"{part_folder}/{pth}"
                note = expert_notes.get(full_expert_name, "")
                display_name = format_expert_display_name(full_expert_name, note)
                model_item.setText(0, display_name)
                model_item.setText(1, f"{size_mb:.1f} MB")
                tooltip_lines = [full_expert_name, file_path]
                if note:
                    tooltip_lines.insert(0, note)
                model_item.setToolTip(0, "\n".join(tooltip_lines))
                model_item.setToolTip(1, "\n".join(tooltip_lines))
                
                # Store full path in UserRole for easy access
                model_item.setData(0, Qt.UserRole, file_path)
                model_item.setData(0, Qt.UserRole + 1, None)
                model_item.setData(0, Qt.UserRole + 2, full_expert_name)
        self._update_delete_expert_tooltip()

    def append_training_log(self, message):
        text = str(message or "").rstrip()
        if not text:
            return
        self.training_log_console.append(text)

    def _expert_root_dir(self):
        return os.path.abspath(os.path.join(self.engine.weights_dir, "experts"))

    def _is_path_within_expert_root(self, target_path):
        if not isinstance(target_path, str) or not target_path:
            return False
        expert_root = self._expert_root_dir()
        try:
            target_abs = os.path.abspath(target_path)
            return os.path.commonpath([expert_root, target_abs]) == expert_root
        except Exception:
            return False

    def _is_safe_expert_bucket_path(self, bucket_path, expected_part_name=None):
        if not isinstance(bucket_path, str) or not bucket_path:
            return False
        part_name = os.path.basename(os.path.abspath(bucket_path))
        if expected_part_name is not None and str(expected_part_name) != part_name:
            return False
        if not is_safe_part_name(part_name):
            return False
        if not self._is_path_within_expert_root(bucket_path):
            return False
        return os.path.isdir(bucket_path)

    def _is_safe_expert_file_path(self, file_path, expected_bucket_path=None):
        if not isinstance(file_path, str) or not file_path:
            return False
        if not self._is_path_within_expert_root(file_path):
            return False
        if expected_bucket_path is not None:
            try:
                bucket_abs = os.path.abspath(expected_bucket_path)
                file_abs = os.path.abspath(file_path)
                if os.path.commonpath([bucket_abs, file_abs]) != bucket_abs:
                    return False
            except Exception:
                return False
        return os.path.isfile(file_path)

    def _selected_expert_bucket_info(self):
        selected = self.expert_tree.selectedItems()
        if not selected:
            return None
        item = selected[0]
        bucket_info = item.data(0, Qt.UserRole + 1)
        if isinstance(bucket_info, dict):
            bucket_path = bucket_info.get("bucket_path")
            part_name = bucket_info.get("part_name")
            if self._is_safe_expert_bucket_path(bucket_path, expected_part_name=part_name):
                return {"bucket_path": bucket_path, "part_name": part_name}
        return None

    def _expert_bucket_files(self, bucket_path):
        if not self._is_safe_expert_bucket_path(bucket_path):
            return []
        files = []
        for filename in sorted(os.listdir(bucket_path)):
            file_path = os.path.join(bucket_path, filename)
            if self._is_safe_expert_file_path(file_path, expected_bucket_path=bucket_path):
                files.append(file_path)
        return files

    def _current_project_bucket_route_impacts(self, child_part_name):
        if not hasattr(self.pm, "get_current_project_expert_bucket_impacts"):
            return {"child_part": str(child_part_name or ""), "routes": []}
        return self.pm.get_current_project_expert_bucket_impacts(child_part_name)

    def _summarize_bucket_delete_preview(self, part_name, bucket_path, files_to_delete, route_impact):
        file_names = [os.path.basename(path) for path in files_to_delete]
        file_count = len(file_names)
        route_rows = []
        for route in route_impact.get("routes", []):
            parent_part = route.get("parent")
            child_part = route.get("child")
            appointed = route.get("appointed_expert_id") or route.get("expert_id") or "Unappointed"
            route_rows.append(f"- {parent_part} -> {child_part} [{appointed}]")

        file_lines = [f"- {name}" for name in file_names[:20]]
        if file_count > 20:
            file_lines.append(f"- ... and {file_count - 20} more file(s)")
        if not file_lines:
            file_lines.append(f"- {self.tr('No expert files were found in this bucket.')}")

        route_lines = route_rows or [f"- {self.tr('No matching current-project routes were found.')}"]

        sections = [
            self.tr("This is a high-risk action. It deletes the expert bucket from disk and can also remove matching route branches in the currently open project."),
            "",
            f"{self.tr('Target bucket path:')}\n{bucket_path}",
            "",
            f"{self.tr('Files to delete ({0}):').format(file_count)}\n" + "\n".join(file_lines),
            "",
            f"{self.tr('Affected routes in the current project ({0}):').format(len(route_rows))}\n" + "\n".join(route_lines),
            "",
            f"{self.tr('Default cleanup action:')}\n{self.tr('If checked, TaxaMask will remove the matching route branches from the currently open project only after the bucket files are deleted successfully. Other projects are not scanned or changed.')}\n\n{self.tr('If unchecked, the files will still be deleted, but the current project routes will remain and later show missing-expert behavior until you clean them manually.')}",
        ]
        return "\n".join(str(section) for section in sections)

    def _show_bucket_delete_preview_dialog(self, *, part_name, bucket_path, files_to_delete, route_impact):
        body_text = self._summarize_bucket_delete_preview(part_name, bucket_path, files_to_delete, route_impact)
        dialog = BucketDeletePreviewDialog(
            self,
            title=self.tr("Bucket Delete Review"),
            body_text=body_text,
            cleanup_label=self.tr("Delete Current Project Route Branches"),
            cleanup_checked=True,
            lang=self.lang,
        )
        dialog.body_text.setPlainText(body_text)
        result = dialog.exec()
        return result == QDialog.DialogCode.Accepted, dialog.cleanup_requested(), dialog

    def _show_bucket_delete_type_confirm_dialog(self, part_name):
        prompt_prefix = str(self.tr("Please type the child-part name exactly to confirm bucket deletion:"))
        dialog = BucketDeleteTypeConfirmDialog(
            self,
            title=self.tr("Type-to-Confirm Bucket Delete"),
            prompt_text=f"{prompt_prefix}\n\n{part_name}",
            expected_text=part_name,
            placeholder_text=self.tr("Type child-part name here"),
            lang=self.lang,
        )
        confirmed = dialog.exec() == QDialog.DialogCode.Accepted
        return confirmed, dialog

    def _delete_expert_bucket_files(self, bucket_path):
        if not self._is_safe_expert_bucket_path(bucket_path):
            raise FileNotFoundError(bucket_path)
        deleted_paths = []
        for file_path in self._expert_bucket_files(bucket_path):
            os.remove(file_path)
            deleted_paths.append(file_path)
        shutil.rmtree(bucket_path)
        return deleted_paths

    def _delete_selected_expert_bucket(self, bucket_info):
        part_name = bucket_info.get("part_name")
        bucket_path = bucket_info.get("bucket_path")
        files_to_delete = self._expert_bucket_files(bucket_path)
        route_impact = self._current_project_bucket_route_impacts(part_name)

        confirmed_preview, cleanup_routes, preview_dialog = self._show_bucket_delete_preview_dialog(
            part_name=part_name,
            bucket_path=bucket_path,
            files_to_delete=files_to_delete,
            route_impact=route_impact,
        )
        if not confirmed_preview:
            self.lbl_status.setText(self.tr("Delete cancelled. The expert bucket was kept."))
            return

        confirmed_type, type_dialog = self._show_bucket_delete_type_confirm_dialog(part_name)
        if not confirmed_type:
            self.lbl_status.setText(self.tr("Delete cancelled. The expert bucket was kept."))
            return

        try:
            self._delete_expert_bucket_files(bucket_path)
        except Exception as exc:
            QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to delete expert bucket: {0}").format(exc))
            self.lbl_status.setText(self.tr("Failed to delete expert bucket: {0}").format(exc))
            return

        for deleted_path in files_to_delete:
            expert_id = build_expert_id(part_name, os.path.basename(deleted_path))
            if expert_id:
                set_expert_note(self.engine.weights_dir, expert_id, "")

        cleanup_count = 0
        if cleanup_routes and hasattr(self.pm, "remove_current_project_expert_bucket_routes"):
            cleanup_count = int(self.pm.remove_current_project_expert_bucket_routes(part_name) or 0)

        self.refresh_expert_registry()
        self.route_registry_refresh_requested.emit()
        self.global_labels_updated.emit()
        if cleanup_routes:
            self.lbl_status.setText(self.tr("Deleted {0} current-project route branch(es) for {1}.").format(cleanup_count, part_name))
        else:
            self.lbl_status.setText(self.tr("Expert bucket deleted, but current-project route cleanup was skipped."))

    def _update_delete_expert_tooltip(self):
        file_path = None
        selected = self.expert_tree.selectedItems()
        if selected:
            file_path = selected[0].data(0, Qt.UserRole)
        if file_path:
            self.btn_delete_expert.setToolTip(self.tr("Delete the selected expert model file from disk."))
            self.btn_edit_expert_note.setEnabled(True)
            return
        self.btn_edit_expert_note.setEnabled(False)
        if self._selected_expert_bucket_info():
            self.btn_delete_expert.setToolTip(self.tr("Delete the selected child-part expert bucket from disk."))
            return
        self.btn_delete_expert.setToolTip(self.tr("Select a trained expert file or a child-part bucket first."))

    def _find_expert_tree_item_by_id(self, expert_id):
        clean_id = str(expert_id or "").strip()
        if not clean_id:
            return None
        for part_index in range(self.expert_tree.topLevelItemCount()):
            part_item = self.expert_tree.topLevelItem(part_index)
            if part_item is None:
                continue
            for model_index in range(part_item.childCount()):
                model_item = part_item.child(model_index)
                if model_item is None:
                    continue
                if str(model_item.data(0, Qt.UserRole + 2) or "").strip() == clean_id:
                    return model_item
        return None

    def _selected_expert_file_info(self):
        selected = self.expert_tree.selectedItems()
        if not selected:
            return None
        item = selected[0]
        file_path = item.data(0, Qt.UserRole)
        if not file_path or not self._is_safe_expert_file_path(file_path):
            return None
        expert_id = item.data(0, Qt.UserRole + 2)
        if not expert_id:
            expert_filename = os.path.basename(file_path)
            expert_part = os.path.basename(os.path.dirname(file_path))
            expert_id = build_expert_id(expert_part, expert_filename)
        if not expert_id:
            return None
        return {"file_path": file_path, "expert_id": str(expert_id)}

    def edit_selected_expert_note(self):
        info = self._selected_expert_file_info()
        if not info:
            QMessageBox.information(self, self.tr("Info"), self.tr("Select a trained expert file first."))
            return
        expert_id = info["expert_id"]
        current_note = load_expert_notes(self.engine.weights_dir).get(expert_id, "")
        note, ok = QInputDialog.getText(
            self,
            self.tr("Expert Note"),
            self.tr("Set a short note for {0}:").format(expert_id),
            text=current_note,
        )
        if not ok:
            return
        saved_note = set_expert_note(self.engine.weights_dir, expert_id, note)
        self.refresh_expert_registry()
        refreshed_item = self._find_expert_tree_item_by_id(expert_id)
        if refreshed_item is not None:
            self.expert_tree.setCurrentItem(refreshed_item)
        self.lbl_status.setText(self.tr("Note saved.") if saved_note else self.tr("Note cleared."))

    def appoint_selected_expert_to_current_route(self):
        selected = self.expert_tree.selectedItems()
        if not selected: return
        item = selected[0]
        file_path = item.data(0, Qt.UserRole)
        if not file_path: return # Selected a part folder, not a file

        context = self._route_context_for_training(
            (self.active_session.get("focus_roi") or {}).get("part") if self.active_session else None,
            self.session_target_part or self.canvas.current_tool_part,
        )
        parent_part = context.get("parent_part")
        child_part = context.get("child_part")
        if not parent_part or not child_part or parent_part == child_part:
            QMessageBox.information(self, self.tr("Info"), self.tr("Open a Blink session with a parent ROI before appointing a route expert."))
            return

        expert_filename = os.path.basename(file_path)
        expert_part = os.path.basename(os.path.dirname(file_path))
        expert_id = build_expert_id(expert_part, expert_filename)
        if not expert_id:
            QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to delete file: {0}").format(file_path))
            return

        existing_route = self.pm.get_cascade_route(parent_part, child_part) if hasattr(self.pm, "get_cascade_route") else None
        existing_expert = (existing_route or {}).get("appointed_expert") if isinstance(existing_route, dict) else {}
        if isinstance(existing_expert, dict) and existing_expert.get("expert_id") == expert_id:
            QMessageBox.information(self, self.tr("Info"), self.tr("This model is already appointed to the current route."))
            return
            
        reply = themed_yes_no_question(
            self,
            self.tr("Appoint to Current Route"),
            self.tr("Appoint this model to {0}?\n(This will only update the current route manifest; it will not copy or overwrite model files.)").format(f"{parent_part} -> {child_part}"),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply == QMessageBox.Yes:
            if hasattr(self.pm, "register_cascade_route_candidate"):
                self.pm.register_cascade_route_candidate(
                    parent_part,
                    child_part,
                    expert_id=expert_id,
                    focus_source=(self.active_session.get("focus_roi") or {}).get("source") if self.active_session else None,
                    registration_source="blink_manual_appointment",
                    save=True,
                )
            appointed = self.pm.appoint_cascade_route_expert(parent_part, child_part, expert_id=expert_id, save=True)
            if appointed and hasattr(self.pm, "set_cascade_route_enabled"):
                self.pm.set_cascade_route_enabled(parent_part, child_part, True, save=True)
            cascade_manager = getattr(self.engine, "cascade_manager", None)
            loaded_experts = getattr(cascade_manager, "loaded_experts", None)
            if isinstance(loaded_experts, dict):
                loaded_experts.clear()
            self.refresh_expert_registry()
            self.route_registry_refresh_requested.emit()
            QMessageBox.information(self, self.tr("Success"), self.tr("Route expert updated successfully."))

    def delete_expert_model(self):
        selected = self.expert_tree.selectedItems()
        if not selected: return
        item = selected[0]
        file_path = item.data(0, Qt.UserRole)
        if not file_path:
            bucket_info = self._selected_expert_bucket_info()
            if bucket_info:
                self._delete_selected_expert_bucket(bucket_info)
            return # Selected a part folder
        if not self._is_safe_expert_file_path(file_path):
            QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to delete file: {0}").format(file_path))
            return
        
        reply = themed_yes_no_question(
            self,
            self.tr("Delete Model"),
            self.tr("Are you sure you want to delete {0}?").format(os.path.basename(file_path)),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply == QMessageBox.Yes:
            try:
                expert_id = item.data(0, Qt.UserRole + 2)
                if not expert_id:
                    expert_id = build_expert_id(os.path.basename(os.path.dirname(file_path)), os.path.basename(file_path))
                os.remove(file_path)
                if expert_id:
                    set_expert_note(self.engine.weights_dir, expert_id, "")
                self.refresh_expert_registry()
                self.route_registry_refresh_requested.emit()
            except Exception as e:
                QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to delete file: {0}").format(e))

    def _confirm_replace_existing_polygon(self, part):
        existing_poly = self.canvas.polygons.get(part)
        if not existing_poly or len(existing_poly) < 3:
            return True

        reply = themed_yes_no_question(
            self,
            self.tr("Replace current polygon for {0}?").format(part),
            self.tr("A draft polygon already exists for this target. Replacing it will discard the current local polygon."),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self.lbl_status.setText(self.tr("Auto-annotate cancelled. Current polygon kept."))
            return False
        return True

    def _reset_to_shrink_box_mode(self):
        self.box_tool_role = "shrink"
        self.rb_box.setChecked(True)
        self.canvas.set_mode("BOX_PROMPT")

    def _reset_to_draw_mode(self):
        self.box_tool_role = "shrink"
        self.rb_draw.setChecked(True)
        self.canvas.set_mode("DRAW")

    def _normalize_local_box(self, raw_box):
        if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4 or not hasattr(self, "mapper"):
            return None

        try:
            local_box = [float(v) for v in raw_box]
        except Exception:
            return None

        local_box = [
            max(0.0, min(local_box[0], float(self.mapper.target_w - 1))),
            max(0.0, min(local_box[1], float(self.mapper.target_h - 1))),
            max(1.0, min(local_box[2], float(self.mapper.target_w))),
            max(1.0, min(local_box[3], float(self.mapper.target_h))),
        ]
        if local_box[2] <= local_box[0] or local_box[3] <= local_box[1]:
            return None
        return local_box

    def _install_draft_polygon_from_local_box(self, part, local_box, missing_polygon_text):
        normalized_box = self._normalize_local_box(local_box)
        if not normalized_box:
            self._reset_to_shrink_box_mode()
            return False

        if not self._confirm_replace_existing_polygon(part):
            self._reset_to_shrink_box_mode()
            return False

        polygon = self.engine.predict_base_sam_polygon(self.zoomed_img_np, normalized_box)
        if not polygon or len(polygon) < 3:
            self.lbl_status.setText(missing_polygon_text)
            self._reset_to_shrink_box_mode()
            return False

        self.canvas.save_state()
        self.canvas.polygons[part] = polygon
        self.canvas.current_tool_part = part
        self._reset_to_draw_mode()
        self.canvas.update()
        self.on_local_polygon_changed(part, polygon)
        self.lbl_status.setText(self.tr("Draft polygon generated for {0}. Refine it, then draw a loose box for shrink.").format(part))
        return True

    def on_tool_changed(self, button):
        if button == self.rb_draw:
            self.box_tool_role = "shrink"
            self.canvas.set_mode("DRAW")
            self.lbl_status.setText(self.tr("Mode: Draw Polygon"))
        elif button == self.rb_box_prompt:
            self.box_tool_role = "prompt"
            self.canvas.set_mode("BOX_PROMPT")
            self.lbl_status.setText(self.tr("Mode: Draw Prompt Box"))
        elif button == self.rb_box:
            self.box_tool_role = "shrink"
            self.canvas.set_mode("BOX_PROMPT")
            self.lbl_status.setText(self.tr("Mode: Draw Box"))

    def on_box_drawn(self, x1, y1, x2, y2):
        part = self.canvas.current_tool_part
        if part:
            if self.box_tool_role == "prompt":
                if not hasattr(self, "zoomed_img_np"):
                    self.lbl_status.setText(self.tr("Error: Zoomed image not ready."))
                    return
                self.lbl_status.setText(self.tr("Generating SAM draft from manual box for {0}...").format(part))
                self.repaint()
                self._install_draft_polygon_from_local_box(
                    part,
                    [x1, y1, x2, y2],
                    self.tr("Base SAM returned no polygon for the prompt box of {0}. Adjust the box or refine manually.").format(part),
                )
                return

            self.canvas.manual_boxes[part] = [x1, y1, x2, y2]
            if self.has_active_session() and part == self.session_target_part:
                self.session_dirty = True
            self.canvas.update()
            self.lbl_status.setText(self.tr("Box drawn for {0}. Ready to Shrink.").format(part))

    def on_local_polygon_changed(self, part, points):
        if self.has_active_session() and part == self.session_target_part:
            self.session_dirty = True
            self.lbl_status.setText(self.tr("Edited {0} in Blink session. Apply to Global to keep changes.").format(part))

    def on_part_selected(self, item):
        part_name = item.text()
        if self.has_active_session() and self.session_target_part:
            part_name = self.session_target_part
        self.canvas.current_tool_part = part_name
        self.lbl_status.setText(self.tr("Focus: {0}").format(part_name))
        self.canvas.update()

    def cycle_blink(self):
        modes = ["NORMAL", "INSIDE", "OUTSIDE"]
        idx = modes.index(self.canvas.blink_mode)
        next_mode = modes[(idx + 1) % 3]
        self.canvas.set_blink_mode(next_mode)
        self.lbl_status.setText(self.tr("Mode: {0}").format(self.tr(next_mode)))

    def run_auto_annotate(self):
        if not self.has_active_session():
            self.lbl_status.setText(self.tr("Error: Open a Blink session first."))
            return

        part = self.session_target_part or self.canvas.current_tool_part
        if not part:
            self.lbl_status.setText(self.tr("Error: Select a part first!"))
            return

        focus_box = self._session_focus_box()
        if not focus_box or not hasattr(self, "mapper") or not hasattr(self, "zoomed_img_np"):
            self.lbl_status.setText(self.tr("Error: Blink auto-annotate needs a valid session ROI."))
            return

        self.lbl_status.setText(self.tr("Generating SAM draft for {0}...").format(part))
        self.btn_auto_annotate.setEnabled(False)
        self.repaint()

        try:
            parent_part = None
            if self.active_session:
                focus_roi = self.active_session.get("focus_roi") or {}
                if isinstance(focus_roi, dict):
                    raw_parent_part = focus_roi.get("part")
                    if isinstance(raw_parent_part, str) and raw_parent_part.strip():
                        parent_part = raw_parent_part.strip()
            route_manifest = self.pm.get_cascade_routes() if hasattr(self.pm, "get_cascade_routes") else None
            if not parent_part:
                self.lbl_status.setText(self.tr("Error: No appointed route expert found for {0}. Train one or appoint a candidate first.").format(part))
                return

            expert_result = self.engine.cascade_manager.infer_child_part(
                self.current_image_path,
                focus_box,
                part,
                parent_part=parent_part,
                route_manifest=route_manifest,
            )
            if not isinstance(expert_result, dict):
                self.lbl_status.setText(self.tr("Error: No appointed route expert found for {0}. Train one or appoint a candidate first.").format(part))
                return

            raw_box = expert_result.get("box")
            if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
                self.lbl_status.setText(self.tr("Error: No appointed route expert found for {0}. Train one or appoint a candidate first.").format(part))
                return

            local_box = self.mapper.bbox_global_to_local(raw_box)
            if not self._normalize_local_box(local_box):
                self.lbl_status.setText(self.tr("Error: No appointed route expert found for {0}. Train one or appoint a candidate first.").format(part))
                return

            self._install_draft_polygon_from_local_box(
                part,
                local_box,
                self.tr("Expert found a box for {0}, but base SAM returned no polygon. Refine manually.").format(part),
            )
        except Exception as exc:
            self.lbl_status.setText(self.tr("Error generating draft polygon for {0}: {1}").format(part, str(exc)))
        finally:
            self.btn_auto_annotate.setEnabled(True)

    def apply_to_global(self):
        """
        逆向投射：将局部图（如 800x800）中修改的选框和多边形，
        精准映射回 4000x3000 的大图坐标，并保存到主项目。
        """
        if not hasattr(self, 'mapper') or not self.current_image_path:
            return

        target_part = self.session_target_part or self.canvas.current_tool_part
        if not target_part:
            self.lbl_status.setText(self.tr("Error: Select a part first!"))
            return

        local_box = self.canvas.manual_boxes.get(target_part)
        local_polys = self.canvas.polygons.get(target_part)
        existing_polys = self.pm.get_labels(self.current_image_path).get(target_part, [])
        existing_box = self.pm.get_boxes(self.current_image_path).get(target_part)

        global_box = self.mapper.bbox_local_to_global(local_box) if local_box else existing_box

        if local_polys and len(local_polys) >= 3:
            global_polys = self.mapper.poly_local_to_global(local_polys)
            self.pm.update_label(self.current_image_path, target_part, global_polys, box=global_box)
        elif global_box and existing_polys:
            self.pm.update_label(self.current_image_path, target_part, existing_polys, box=global_box)
        else:
            self.lbl_status.setText(self.tr("Nothing to apply for {0}.").format(target_part))
            return

        self.session_dirty = False
        self.lbl_status.setText(self.tr("Applied {0} to Global!").format(target_part))
        self.global_labels_updated.emit() # Notify main window

    def run_auto_shrink(self):
        """
        阶段二核心 (遵循白皮书重构)：生成基于黄金掩码的收缩轨迹。
        人类必须先提供一个松散框和一个精修过的完美多边形。
        """
        if not (self.session_target_part or self.canvas.current_tool_part):
            self.lbl_status.setText(self.tr("Error: Select a part first!"))
            return
            
        part = self.session_target_part or self.canvas.current_tool_part
        
        # 1. 检查是否存在初始大框
        initial_box = None
        if part in self.canvas.manual_boxes:
            initial_box = self.canvas.manual_boxes[part]
            
        if not initial_box:
            self.lbl_status.setText(self.tr("Error: Draw a loose BOX for {0} first!").format(part))
            return
            
        # 2. 检查是否存在人类画好的“黄金多边形”
        golden_poly = None
        if part in self.canvas.polygons:
            golden_poly = self.canvas.polygons[part]
            
        if not golden_poly or len(golden_poly) < 3:
            self.lbl_status.setText(self.tr("Error: Draw a golden POLYGON for {0}!").format(part))
            return
            
        if not hasattr(self, 'zoomed_img_np'):
            self.lbl_status.setText(self.tr("Error: Zoomed image not ready."))
            return

        self.lbl_status.setText(self.tr("Generating Trajectory for {0}...").format(part))
        self.btn_auto_shrink.setEnabled(False)
        self.prog_shrink.setValue(0)
        self.repaint()

        # 调用核心引擎
        if "core.blink_refiner" in sys.modules:
            from core.blink_refiner import BlinkRefiner
        else:
            try:
                from AntSleap.core.blink_refiner import BlinkRefiner
            except ImportError:
                from core.blink_refiner import BlinkRefiner
        if hasattr(self.engine, "ensure_parts_model_loaded"):
            parts_model = self.engine.ensure_parts_model_loaded()
        else:
            parts_model = self.engine.parts_model
        sam_model = parts_model.ultralytics_sam
        refiner = BlinkRefiner(sam_model=sam_model, device=self.runtime_device)
        
        # 执行靶向轨迹生成
        trajectory = refiner.generate_shrink_trajectory(
            image_input=self.zoomed_img_np,
            initial_box=initial_box,
            golden_poly=golden_poly
        )
        
        if not trajectory:
            self.lbl_status.setText(self.tr("Error generating trajectory."))
            self.btn_auto_shrink.setEnabled(True)
            return
            
        # UI 展示：我们将画布上的框直接更新为最后一步（完美贴合状态）
        best_box = trajectory[-1]["box"]
        self.canvas.manual_boxes[part] = best_box
        if self.has_active_session() and part == self.session_target_part:
            self.session_dirty = True
        self.canvas.update()
        
        steps = len(trajectory)
        self.prog_shrink.setValue(100)
        self.lbl_status.setText(self.tr("Generated {0} trajectory frames.").format(steps))
        self.btn_auto_shrink.setEnabled(True)
        
        # 将轨迹中的局部坐标转换为大图的全局坐标，然后存入 ProjectManager
        global_trajectory = []
        for frame in trajectory:
            global_frame = frame.copy()
            global_frame["box"] = self.mapper.bbox_local_to_global(frame["box"])
            if "target_box" in frame:
                global_frame["target_box"] = self.mapper.bbox_local_to_global(frame["target_box"])
            global_frame["coord_frame"] = "global"
            global_trajectory.append(global_frame)

        focus_roi = dict(self.active_session.get("focus_roi") or {}) if self.active_session else {}
        parent_context = {
            "parent_part": focus_roi.get("part"),
            "parent_box": focus_roi.get("box") or [
                float(self.mapper.crop_x1),
                float(self.mapper.crop_y1),
                float(self.mapper.crop_x2),
                float(self.mapper.crop_y2),
            ],
            "source": focus_roi.get("source", "session_roi" if self.active_session else "workbench"),
        }
            
        self.pm.update_trajectory(self.current_image_path, part, global_trajectory, parent_context=parent_context)
        self.lbl_status.setText(self.tr("Saved {0} trajectory frames for {1}.").format(steps, part))
        print(f"[Data Factory] Stored {steps} training frames for {part}.")

    def train_expert_model(self):
        """
        阶段三核心：利用积攒的轨迹数据，训练轻量级微观专家。
        """
        if not self.canvas.current_tool_part:
            self.lbl_status.setText(self.tr("Error: Select a part to train!"))
            return
            
        part = self.session_target_part or self.canvas.current_tool_part
        if self.training_thread and self.training_thread.isRunning():
            self.lbl_status.setText(self.tr("Training already running..."))
            return

        self.lbl_status.setText(self.tr("Training Expert for {0}...").format(part))
        self.btn_train_expert.setEnabled(False)
        self.repaint()

        epochs = self.spin_epochs.value()
        batch_size = self.spin_batch.value()
        learning_rate = self._coerce_float(self.edit_lr.text(), self.default_learning_rate)
        weight_decay = self._coerce_float(self.edit_weight_decay.text(), self.default_weight_decay)
        input_size = self._normalize_input_size(self.combo_input_size.currentData())
        parent_part = None
        if self.active_session:
            focus_roi = self.active_session.get("focus_roi") or {}
            if isinstance(focus_roi, dict):
                raw_parent_part = focus_roi.get("part")
                if isinstance(raw_parent_part, str) and raw_parent_part.strip():
                    parent_part = raw_parent_part.strip()
        self.training_route_context = self._route_context_for_training(parent_part, part)
        self.training_thread = BlinkTrainingThread(
            project_path=self.pm.current_project_path,
            part_name=part,
            parent_part=parent_part,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            weight_decay=weight_decay,
            input_size=input_size,
            device=self.runtime_device,
        )
        self.training_thread.result_signal.connect(self._on_training_result)
        self.training_thread.report_signal.connect(self._on_training_report)
        self.training_thread.error_signal.connect(self._on_training_error)
        self.training_thread.log_signal.connect(self.append_training_log)
        self.training_thread.progress_signal.connect(self.prog_training.setValue)
        self.training_thread.cancelled_signal.connect(self._on_training_cancelled)
        self.training_thread.finished.connect(self._on_training_finished)
        self.training_log_console.clear()
        self.prog_training.setValue(0)
        self.append_training_log(self.tr("Training Expert for {0}...").format(part))
        self.btn_stop_training.setEnabled(True)
        self.training_thread.start()

    def _on_training_report(self, report_data):
        if isinstance(report_data, dict) and report_data:
            dlg = BlinkExpertTrainingReportDialog(report_data, self.lang, self)
            dlg.exec()

    def stop_expert_training(self):
        if self.training_thread and self.training_thread.isRunning():
            self.training_thread.requestInterruption()
            self.btn_stop_training.setEnabled(False)
            self.lbl_status.setText(self.tr("Stopping training after the current batch..."))
            self.append_training_log(self.tr("Stopping training after the current batch..."))

    def _route_has_appointed_expert(self, parent_part, child_part):
        get_route = getattr(self.pm, "get_cascade_route", None)
        if not callable(get_route):
            return False
        try:
            route = get_route(parent_part, child_part)
        except Exception:
            return False
        if not isinstance(route, dict):
            return False
        appointed = route.get("appointed_expert")
        if isinstance(appointed, dict) and appointed.get("expert_id"):
            return True
        return bool(route.get("expert_id") or route.get("expert_part") or route.get("expert_filename"))

    def _route_context_for_training(self, parent_part, child_part):
        clean_parent = str(parent_part or "").strip()
        clean_child = str(child_part or "").strip()
        return {
            "parent_part": clean_parent or None,
            "child_part": clean_child or None,
            "had_appointed_expert": bool(clean_parent and clean_child and self._route_has_appointed_expert(clean_parent, clean_child)),
        }

    def _auto_link_training_route(self, save_path):
        context = dict(self.training_route_context or {})
        parent_part = str(context.get("parent_part") or "").strip()
        child_part = str(context.get("child_part") or "").strip()
        if not parent_part or not child_part or parent_part == child_part:
            return None

        expert_filename = os.path.basename(str(save_path or "").strip())
        expert_id = build_expert_id(child_part, expert_filename)
        if not expert_id:
            return None

        register_route = getattr(self.pm, "register_cascade_route_candidate", None)
        if not callable(register_route):
            return None

        focus_source = None
        if self.active_session:
            focus_roi = self.active_session.get("focus_roi") or {}
            if isinstance(focus_roi, dict):
                focus_source = focus_roi.get("source")

        if bool(context.get("had_appointed_expert")):
            register_route(
                parent_part,
                child_part,
                expert_id=expert_id,
                focus_source=focus_source,
                registration_source="blink_training",
                save=True,
            )
            self.route_registry_refresh_requested.emit()
            return {
                "parent_part": parent_part,
                "child_part": child_part,
                "expert_id": expert_id,
                "skipped_appointment": True,
            }

        register_route(
            parent_part,
            child_part,
            expert_id=expert_id,
            focus_source=focus_source,
            registration_source="blink_training",
            save=True,
        )

        self.route_registry_refresh_requested.emit()
        return {
            "parent_part": parent_part,
            "child_part": child_part,
            "expert_id": expert_id,
            "candidate_only": True,
        }

    def _on_training_result(self, save_path):
        if save_path:
            self.prog_training.setValue(100)
            cascade_manager = getattr(self.engine, "cascade_manager", None)
            loaded_experts = getattr(cascade_manager, "loaded_experts", None)
            if isinstance(loaded_experts, dict):
                loaded_experts.clear()
            self.refresh_expert_registry()
            try:
                linked_route = self._auto_link_training_route(save_path)
            except Exception as exc:
                message = self.tr("Training finished. Expert saved, but route auto-link failed: {0}").format(exc)
                self.lbl_status.setText(message)
                self.append_training_log(message)
                return

            if linked_route:
                if linked_route.get("skipped_appointment"):
                    message = self.tr(
                        "Training finished. Route {0} -> {1} already has an appointed expert, so the new model was saved as a candidate and was not appointed automatically."
                    ).format(linked_route["parent_part"], linked_route["child_part"])
                elif linked_route.get("candidate_only"):
                    message = self.tr(
                        "Training finished. Expert was added as a route candidate for {0} -> {1}. Appoint it manually if the report looks better."
                    ).format(linked_route["parent_part"], linked_route["child_part"])
                else:
                    message = self.tr(
                        "Training finished. Expert was linked to route {0} -> {1} and enabled for workbench auto-annotation."
                    ).format(linked_route["parent_part"], linked_route["child_part"])
                self.lbl_status.setText(message)
                self.append_training_log(message)
            else:
                message = self.tr("Training finished. Expert saved, but no parent-part route was available to enable.")
                self.lbl_status.setText(message)
                self.append_training_log(message)
        else:
            self.lbl_status.setText(self.tr("Training failed. Need more data."))

    def _on_training_error(self, error_msg):
        self.lbl_status.setText(self.tr("Training Error: {0}").format(error_msg))
        print(f"Training Exception: {error_msg}")

    def _on_training_cancelled(self):
        self.lbl_status.setText(self.tr("Training cancelled."))
        self.append_training_log(self.tr("Training cancelled."))

    def _on_training_finished(self):
        self.btn_train_expert.setEnabled(True)
        self.btn_stop_training.setEnabled(False)
        if self.training_thread:
            self.training_thread.deleteLater()
            self.training_thread = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.cycle_blink()
        super().keyPressEvent(event)
