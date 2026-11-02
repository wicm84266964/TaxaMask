"""Species/individual workspace using shared Qt canvas and SAM services."""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QThread, QProcess, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QShortcut, QKeySequence, QFont
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton,
    QListWidget, QListWidgetItem, QComboBox, QLabel, QLineEdit, QFileDialog, QMessageBox,
    QInputDialog, QPlainTextEdit, QDialog, QFormLayout, QSpinBox, QDialogButtonBox, QCheckBox, QScrollArea, QMenu)

from ..core.instance_project import InstanceProject, polygon_mask, uid
from ..core.instance_dataset import export_dataset, import_coco, import_directory, FrozenInstanceDataset
from ..core.safe_io import atomic_write_json
from .instance_canvas import InstanceCanvas
from .instance_jobs import InstanceJobWorker


class InstanceWorkbench(QWidget):
    return_requested = Signal()
    project_opened = Signal(str)
    agent_requested = Signal(object)
    job_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        from .style import register_windows_scholarly_ui_fonts, apply_semantic_button_style, BUTTON_ROLE_NEUTRAL
        register_windows_scholarly_ui_fonts()
        from .style import apply_surface_role, SURFACE_ROLE_TOOLBAR, SURFACE_ROLE_SUBTLE, SURFACE_ROLE_PANEL, SURFACE_ROLE_CANVAS
        self.setFont(QFont("Microsoft YaHei", 10))
        self.project = None
        self.image_id = ""
        self.busy = False
        self.process = None
        self.candidate = None
        self.cancel_event = threading.Event()
        self.replace_existing = False
        self.prompt_points = []
        self.prompt_labels = []
        default_sam = Path(__file__).parent / "weights" / "sam_b.pt"
        self.sam_options = {"model": str(default_sam), "device": "auto"}
        engine = getattr(parent, "engine", None)
        if getattr(engine, "base_sam_path", None):
            self.sam_options["model"] = str(engine.base_sam_path)
        self.default_sam_options = dict(self.sam_options)
        self.thread = QThread(self)
        self.worker = InstanceJobWorker()
        self.worker.moveToThread(self.thread)
        self.job_requested.connect(self.worker.execute)
        self.worker.finished.connect(self._job_done)
        self.worker.failed.connect(self._job_failed)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.start()
        self.agent_timer = QTimer(self)
        self.agent_timer.setInterval(1500)
        self.agent_timer.timeout.connect(self.poll_agent_requests)
        self.agent_timer.start()
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        toolbar_widget = QWidget()
        apply_surface_role(toolbar_widget, SURFACE_ROLE_TOOLBAR, "instanceTopBar")
        row = QHBoxLayout(toolbar_widget)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)
        root.addWidget(toolbar_widget)
        for label, callback in [("导出数据集", self.export), ("返回主界面", self.return_requested.emit), ("Ask Agent", self.ask_agent)]:
            if label == "返回主界面":
                row.addStretch(1)
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, cb=callback: self.guard(cb))
            row.addWidget(button)
        more = QPushButton("更多操作")
        menu = QMenu(more)
        for label, callback in [("新建项目", self.new_project), ("打开项目", self.open_project),
                                ("备份", self.backup), ("恢复备份", self.restore), ("模型设置", self.model_settings)]:
            menu.addAction(label, lambda checked=False, cb=callback: self.guard(cb))
        more.setMenu(menu)
        row.addWidget(more)
        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        root.addWidget(splitter, 1)
        left = QWidget()
        apply_surface_role(left, SURFACE_ROLE_SUBTLE, "instanceLibraryPanel")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)
        title = QLabel("项目图片")
        title.setObjectName("HeaderLabel")
        left_layout.addWidget(title)
        import_button = QPushButton("导入材料")
        import_menu = QMenu(import_button)
        for label, callback in [("导入图片", self.import_images), ("导入文件夹", self.import_folder), ("导入标注", self.import_annotations)]:
            import_menu.addAction(label, lambda checked=False, cb=callback: self.guard(cb))
        import_button.setMenu(import_menu)
        left_layout.addWidget(import_button)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索图片名称")
        self.search.textChanged.connect(self.refresh_images)
        left_layout.addWidget(self.search)
        self.image_filter = QComboBox()
        for label, code in [("全部图片", ""), ("未开始", "unreviewed"), ("待复核", "in_progress"),
                            ("完整检查", "complete"), ("确认无目标", "confirmed_empty"), ("排除", "excluded")]:
            self.image_filter.addItem(label, code)
        self.image_filter.currentIndexChanged.connect(self.refresh_images)
        left_layout.addWidget(self.image_filter)
        self.images = QListWidget()
        self.images.currentItemChanged.connect(lambda item, old: self.guard(lambda: self.select_image(item)))
        left_layout.addWidget(self.images)
        splitter.addWidget(left)
        center = QWidget()
        center.setObjectName("workbenchCenterPanel")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(10)
        tools = QHBoxLayout()
        self.tool = QComboBox()
        for label, code in [("选择（重叠点击循环）", "select"), ("标注框", "box"), ("多边形（双击完成）", "polygon"),
                            ("SAM 点选", "sam_point"), ("SAM 框选", "sam_box"), ("SAM 背景点修正", "sam_negative"),
                            ("顶点编辑（Ctrl 加点/Shift 删点）", "vertices"), ("画笔修补", "brush"), ("橡皮", "erase")]:
            self.tool.addItem(label, code)
        self.tool.currentIndexChanged.connect(lambda: self.canvas.set_tool(self.tool.currentData()))
        tools.addWidget(self.tool)
        self.redraw = QCheckBox("重描选中个体")
        self.redraw.setToolTip("未勾选时画框或描边会创建新个体；修补/顶点编辑始终作用于选中个体")
        tools.addWidget(self.redraw)
        tools.addStretch(1)
        fit = QPushButton("适应窗口")
        fit.clicked.connect(lambda: self.canvas.fit_to_view())
        tools.addWidget(fit)
        center_layout.addLayout(tools)
        display = QHBoxLayout()
        self.show_masks = QCheckBox("显示掩膜")
        self.show_masks.setChecked(True)
        self.show_masks.toggled.connect(lambda value: self._mask_display(value))
        display.addWidget(self.show_masks)
        self.opacity_control = QSpinBox()
        self.opacity_control.setRange(5, 90)
        self.opacity_control.setValue(35)
        self.opacity_control.setSuffix("%")
        self.opacity_control.valueChanged.connect(lambda value: self._mask_opacity(value))
        display.addWidget(QLabel("透明层"))
        display.addWidget(self.opacity_control)
        brush = QSpinBox()
        brush.setRange(1, 100)
        brush.setValue(6)
        brush.valueChanged.connect(lambda value: setattr(self.canvas, "brush_radius", value))
        display.addWidget(QLabel("修补半径/像素"))
        display.addWidget(brush)
        display.addStretch()
        center_layout.addLayout(display)
        self.canvas = InstanceCanvas()
        self.canvas.selected.connect(self.select_instance)
        self.canvas.geometry_ready.connect(lambda geometry: self.guard(lambda: self.geometry(geometry)))
        self.canvas.prompt_ready.connect(lambda prompt: self.guard(lambda: self.sam_prompt(prompt)))
        canvas_shell = QWidget()
        apply_surface_role(canvas_shell, SURFACE_ROLE_CANVAS, "instanceCanvasShell")
        canvas_layout = QVBoxLayout(canvas_shell)
        canvas_layout.setContentsMargins(12, 12, 12, 12)
        canvas_layout.addWidget(self.canvas)
        center_layout.addWidget(canvas_shell, 1)
        self.candidate_row = QHBoxLayout()
        self.candidate_label = QLabel("中键拖动平移；滚轮缩放；Esc 取消当前绘制")
        self.candidate_row.addWidget(self.candidate_label, 1)
        accept = QPushButton("采用候选")
        accept.clicked.connect(lambda: self.guard(self.accept_candidate))
        reject = QPushButton("取消候选")
        reject.clicked.connect(self.clear_candidate)
        self.candidate_row.addWidget(accept)
        self.candidate_row.addWidget(reject)
        center_layout.addLayout(self.candidate_row)
        splitter.addWidget(center)
        right = QWidget()
        apply_surface_role(right, SURFACE_ROLE_PANEL, "instanceInspectorPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)
        self.categories = QComboBox()
        self.categories.setEditable(False)
        self.categories.currentIndexChanged.connect(lambda: self.refresh_objects() if hasattr(self, "object_filter") else None)
        right_layout.addWidget(QLabel("当前物种（用于新建或改类）"))
        right_layout.addWidget(self.categories)
        category_buttons = QHBoxLayout()
        for label, callback in [("新增物种", self.add_category), ("更名", self.rename_category)]:
            b = QPushButton(label)
            b.clicked.connect(lambda checked=False, cb=callback: self.guard(cb))
            category_buttons.addWidget(b)
        right_layout.addLayout(category_buttons)
        merge = QPushButton("合并/删除类别")
        merge.clicked.connect(lambda: self.guard(self.manage_category))
        right_layout.addWidget(merge)
        self.object_filter = QComboBox()
        self.object_filter.addItems(["全部个体", "待确认", "已确认", "当前物种", "仅画框", "有轮廓"])
        self.object_filter.currentIndexChanged.connect(lambda: self.refresh_objects())
        right_layout.addWidget(self.object_filter)
        self.instances = QListWidget()
        self.instances.setSelectionMode(QListWidget.ExtendedSelection)
        self.instances.currentItemChanged.connect(self._list_selected)
        right_layout.addWidget(self.instances, 1)
        for label, operation in [("确认选中个体", "confirm"), ("选中改为当前物种", "reclassify"), ("删除选中个体", "delete")]:
            b = QPushButton(label)
            b.clicked.connect(lambda checked=False, op=operation: self.guard(lambda: self.batch(op)))
            right_layout.addWidget(b)
        specimen = QPushButton("设置选中个体的标本 ID")
        specimen.clicked.connect(lambda: self.guard(self.set_specimen))
        right_layout.addWidget(specimen)
        model_title = QLabel("模型辅助")
        model_title.setObjectName("HeaderLabel")
        right_layout.addWidget(model_title)
        model_actions = QHBoxLayout()
        for label, callback in [("预测", self.predict_dialog), ("训练", self.train_dialog)]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, cb=callback: self.guard(cb))
            model_actions.addWidget(button)
        right_layout.addLayout(model_actions)
        model_menu_button = QPushButton("模型与任务")
        model_menu = QMenu(model_menu_button)
        for label, callback in [("模型设置", self.model_settings), ("取消当前任务", self.cancel_task)]:
            model_menu.addAction(label, lambda checked=False, cb=callback: self.guard(cb))
        model_menu_button.setMenu(model_menu)
        right_layout.addWidget(model_menu_button)
        inspector_scroll = QScrollArea()
        inspector_scroll.setObjectName("workbenchInspectorScroll")
        inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inspector_scroll.setMinimumWidth(250)
        inspector_scroll.setWidget(right)
        splitter.addWidget(inspector_scroll)
        splitter.setSizes([200, 850, 260])
        bottom = QHBoxLayout()
        root.addLayout(bottom)
        for label, cb in [("上一张", lambda: self.navigate(-1)), ("下一张", lambda: self.navigate(1)),
                          ("撤销", lambda: self.history(False)), ("重做", lambda: self.history(True)),
                          ("本图已完整检查", lambda: self.review("complete")),
                          ("确认无目标", lambda: self.review("confirmed_empty")),
                          ("暂不用于训练", lambda: self.review("excluded"))]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, fn=cb: self.guard(fn))
            bottom.addWidget(button)
        self.status = QLabel("新建或打开物种与个体项目")
        root.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(95)
        self.log.setObjectName("MutedLogConsole")
        root.addWidget(self.log)
        for button in self.findChildren(QPushButton):
            apply_semantic_button_style(button, BUTTON_ROLE_NEUTRAL)
        for key, fn in [("Ctrl+Z", lambda: self.history(False)), ("Ctrl+Shift+Z", lambda: self.history(True)),
                        ("Delete", lambda: self.batch("delete")), ("B", lambda: self.tool.setCurrentIndex(1)),
                        ("V", lambda: self.tool.setCurrentIndex(0))]:
            shortcut = QShortcut(QKeySequence(key), self.canvas)
            shortcut.setContext(Qt.WidgetShortcut)
            shortcut.activated.connect(lambda fn=fn: self.guard(fn))

    def guard(self, callback):
        try:
            return callback()
        except Exception as exc:
            self.log.appendPlainText(str(exc))
            QMessageBox.warning(self, "物种与个体标注", str(exc))

    def _mask_display(self, value):
        self.canvas.show_masks = value
        self.canvas.update()

    def _mask_opacity(self, value):
        self.canvas.opacity = value / 100
        self.refresh_objects()

    def import_folder(self):
        self.require_project()
        folder = QFileDialog.getExistingDirectory(self, "导入图片文件夹（递归复制）")
        if folder:
            self.import_images([str(p) for p in Path(folder).rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}])

    def require_project(self):
        if self.project is None:
            raise ValueError("请先新建或打开物种与个体项目")
        return self.project

    def can_close(self):
        if self.busy or self.process is not None:
            QMessageBox.information(self, "任务运行中", "请等待后台任务结束，或先取消训练。")
            return False
        return True

    def shutdown(self):
        if not self.can_close():
            return False
        self.agent_timer.stop()
        self.thread.quit()
        self.thread.wait()
        if self.project:
            self.project.close()
            self.project = None
        return True

    def set_project(self, project):
        if self.project:
            self.project.close()
        self.project = project
        self.agent_timer.start()
        stored_sam = project.settings().get("sam")
        self.sam_options = dict(self.default_sam_options)
        if isinstance(stored_sam, dict) and set(stored_sam) == {"model", "device"}:
            self.sam_options = stored_sam
        self.image_id = ""
        self.canvas.load_image("")
        self.canvas.objects = []
        self.clear_candidate()
        self.refresh()
        self.project_opened.emit(str(project.path))

    def new_project(self):
        if not self.can_close():
            return
        folder = QFileDialog.getExistingDirectory(self, "选择空文件夹创建物种与个体项目")
        if folder:
            self.set_project(InstanceProject.create(folder, Path(folder).name))

    def open_path(self, path):
        if self.project and self.project.path == Path(path).resolve():
            return
        if self.can_close():
            self.set_project(InstanceProject(path))

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开物种与个体项目", "", "实例项目 (*.instance.json)")
        if path:
            self.open_path(path)

    def import_images(self, paths=None, provenance=None):
        project = self.require_project()
        if paths is None:
            paths, _ = QFileDialog.getOpenFileNames(self, "导入图片（复制到项目）", "", "图片 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)")
        if not paths:
            return
        created, errors = project.import_images(paths, provenance=provenance)
        self.log.appendPlainText(f"导入 {len(created)} 张；失败 {len(errors)} 张；同内容图片自动跳过。")
        if errors:
            self.log.appendPlainText(json.dumps(errors, ensure_ascii=False))
        self.refresh()

    def import_annotations(self):
        project = self.require_project()
        kind, ok = QInputDialog.getItem(self, "导入格式", "所有导入标签均待人工确认", ["COCO", "YOLO 检测", "YOLO 分割", "分类目录"], 0, False)
        if not ok:
            return
        if kind != "COCO":
            folder = QFileDialog.getExistingDirectory(self, "选择数据集根目录")
            if folder and QMessageBox.question(self, "导入预览", "同名类别将匹配，图片与对象经校验后一次写入，所有标签保持待确认。继续？") == QMessageBox.Yes:
                count = import_directory(project, folder, task={"YOLO 检测": "detect", "YOLO 分割": "segment", "分类目录": "classify"}[kind])
                self.log.appendPlainText(f"导入 {count} 个体，报告位于项目 imports 目录。")
                self.refresh()
            return
        path, _ = QFileDialog.getOpenFileName(self, "导入 COCO 标注（均作为待确认）", "", "COCO (*.json)")
        if not path:
            return
        root = QFileDialog.getExistingDirectory(self, "选择 COCO file_name 对应的图像根目录")
        if root and QMessageBox.question(self, "导入预览", "将检查图片、类别、框和掩膜；同名类别合并，所有对象保持待确认。继续？") == QMessageBox.Yes:
            count = import_coco(project, path, root)
            self.log.appendPlainText(f"已导入 {count} 个候选实例。")
            self.refresh()

    def refresh_images(self, *_):
        self.images.blockSignals(True)
        self.images.clear()
        if self.project:
            for im in self.project.records("images"):
                if self.search.text().casefold() not in im["name"].casefold():
                    continue
                if self.image_filter.currentData() and im["review"] != self.image_filter.currentData():
                    continue
                state = {"unreviewed": "未开始", "in_progress": "待复核", "complete": "已检查", "confirmed_empty": "无目标", "excluded": "暂不训练"}.get(im["review"], im["review"])
                item = QListWidgetItem(f"{im['name']} · {state}")
                item.setToolTip(f"{im['name']} · {state}")
                item.setData(Qt.UserRole, im["id"])
                self.images.addItem(item)
                if im["id"] == self.image_id:
                    self.images.setCurrentItem(item)
        self.images.blockSignals(False)

    def refresh(self):
        if not self.project:
            return
        current = self.categories.currentData()
        self.categories.blockSignals(True)
        self.categories.clear()
        self.categories.addItem("未鉴定", None)
        for c in self.project.records("categories"):
            self.categories.addItem(c["name"], c["id"])
        self.categories.setCurrentIndex(max(0, self.categories.findData(current)))
        self.categories.blockSignals(False)
        self.refresh_images()
        if not self.image_id and self.images.count():
            self.images.setCurrentRow(0)
        self.refresh_objects()

    def select_image(self, item):
        if item is None or not self.project:
            return
        self.image_id = item.data(Qt.UserRole)
        record = self.project.get("images", self.image_id)
        self.canvas.load_image(str(self.project.image_path(record)))
        self.canvas.cancel_gesture()
        self.canvas.active_id = ""
        self.clear_candidate()
        self.refresh_objects()

    def refresh_objects(self):
        self.instances.blockSignals(True)
        self.instances.clear()
        if not self.project or not self.image_id:
            self.instances.blockSignals(False)
            return
        records = self.project.records("instances", self.image_id)
        names = {c["id"]: c["name"] for c in self.project.records("categories")}
        for n, r in enumerate(records, 1):
            choice = self.object_filter.currentText()
            if (choice == "待确认" and r["review"] == "confirmed" or choice == "已确认" and r["review"] != "confirmed"
                or choice == "当前物种" and r.get("category_id") != self.categories.currentData()
                or choice == "仅画框" and r.get("mask") or choice == "有轮廓" and not r.get("mask")):
                continue
            item = QListWidgetItem(f"#{n} {names.get(r.get('category_id'), '未鉴定')} · {'已确认' if r['review'] == 'confirmed' else '待确认'}")
            item.setData(Qt.UserRole, r["id"])
            self.instances.addItem(item)
            if r["id"] == self.canvas.active_id:
                self.instances.setCurrentItem(item)
        self.instances.blockSignals(False)
        self.canvas.set_objects(records, names)
        image = self.project.get("images", self.image_id)
        state = {"unreviewed": "未开始", "in_progress": "待完整检查", "complete": "已完整检查", "confirmed_empty": "确认无目标", "excluded": "暂不训练"}[image["review"]]
        self.status.setText(f"{self.project.name} · 个体 {len(records)} · 已确认 {sum(self.project.trusted(r) for r in records)} · 整图：{state} · 已保存")

    def _list_selected(self, item, old):
        if item is not old:
            self.prompt_points, self.prompt_labels = [], []
        self.canvas.active_id = item.data(Qt.UserRole) if item else ""
        self.canvas.update()

    def select_instance(self, key):
        for i in range(self.instances.count()):
            item = self.instances.item(i)
            if item.data(Qt.UserRole) == key:
                self.instances.setCurrentItem(item)
                break

    def geometry(self, payload):
        project = self.require_project()
        if "error" in payload:
            raise ValueError(payload["error"])
        if not self.image_id:
            raise ValueError("请先选择图片")
        image = project.get("images", self.image_id)
        mask = payload.get("mask")
        if "polygon" in payload:
            mask = polygon_mask(payload["polygon"], image["width"], image["height"])
        replace = payload.get("replace") or self.redraw.isChecked()
        key = self.canvas.active_id if replace else None
        if replace and not key:
            raise ValueError("请先选择要修改的个体")
        category_id = project.get("instances", key).get("category_id") if key else self.categories.currentData()
        key = project.put_instance(self.image_id, category_id, payload.get("box"), mask=mask, key=key)
        self.canvas.active_id = key
        self.refresh()

    def add_category(self):
        project = self.require_project()
        name, ok = QInputDialog.getText(self, "新增物种", "学名或暂定形态种名")
        if ok:
            key = project.category(name)
            self.refresh()
            self.categories.setCurrentIndex(self.categories.findData(key))

    def rename_category(self):
        project = self.require_project()
        key = self.categories.currentData()
        if not key:
            raise ValueError("请选择物种类别")
        name, ok = QInputDialog.getText(self, "类别更名", "保留类别 ID 和所有个体关联", text=self.categories.currentText())
        if ok:
            project.category(name, key)
            self.refresh()

    def manage_category(self):
        project = self.require_project()
        source = self.categories.currentData()
        if not source:
            raise ValueError("请选择类别")
        others = [c for c in project.records("categories") if c["id"] != source]
        options = ["删除无引用类别"] + ["合并到 " + c["name"] for c in others]
        value, ok = QInputDialog.getItem(self, "类别管理", "合并后关联个体需重新审核，操作可撤销", options, 0, False)
        if not ok:
            return
        count = sum(r.get("category_id") == source for r in project.records("instances"))
        if QMessageBox.question(self, "确认影响", f"当前类别关联 {count} 个体。执行 {value}？") != QMessageBox.Yes:
            return
        if value == options[0]:
            project.remove_category(source)
        else:
            project.merge_categories(source, others[options.index(value)-1]["id"])
        self.refresh()

    def batch(self, operation):
        project = self.require_project()
        keys = [i.data(Qt.UserRole) for i in self.instances.selectedItems()]
        if not keys:
            return
        if QMessageBox.question(self, "操作范围", f"对选中的 {len(keys)} 个个体执行操作？可撤销。") != QMessageBox.Yes:
            return
        project.batch(keys, operation, self.categories.currentData())
        self.refresh()

    def set_specimen(self):
        project = self.require_project()
        keys = [i.data(Qt.UserRole) for i in self.instances.selectedItems()]
        if not keys:
            return
        value, ok = QInputDialog.getText(self, "标本身份", "同一实体标本的多视图使用相同 ID；不同个体勿共用")
        if ok:
            changes = []
            for key in keys:
                record = project.get("instances", key)
                record["specimen_id"] = value.strip()
                changes.append(("instances", key, record))
            project.change("specimen_identity", changes)
            self.refresh()

    def review(self, status):
        self.require_project().review_image(self.image_id, status)
        self.refresh()

    def history(self, redo):
        project = self.require_project()
        (project.redo if redo else project.undo)()
        self.clear_candidate()
        if self.image_id and not any(i["id"] == self.image_id for i in project.records("images")):
            self.image_id = ""
        self.refresh()

    def navigate(self, step):
        index = self.images.currentRow() + step
        if 0 <= index < self.images.count():
            self.images.setCurrentRow(index)

    def backup(self):
        self.log.appendPlainText("备份：" + str(self.require_project().backup()))

    def restore(self):
        project = self.require_project()
        if not self.can_close():
            return
        path, _ = QFileDialog.getOpenFileName(self, "恢复当前项目备份", str(project.root / "backups"), "SQLite (*.sqlite)")
        if path and QMessageBox.question(self, "恢复备份", "先保存当前数据库备份，再恢复所选版本。恢复标注均需重新确认。继续？") == QMessageBox.Yes:
            project.restore_backup(path)
            self.image_id = ""
            self.refresh()

    def model_settings(self):
        from ..core.instance_external_backend import sanitize_instance_backend
        project = self.require_project()
        settings = project.settings()
        external = sanitize_instance_backend(settings.get("external_backend"))
        dialog = QDialog(self)
        dialog.setWindowTitle("物种与个体模型设置")
        dialog.resize(850, 650)
        form = QFormLayout(dialog)
        backend = QComboBox()
        backend.addItem("内置 Ultralytics", "builtin")
        backend.addItem("外部脚本（实例契约 v1）", "external")
        backend.setCurrentIndex(1 if settings.get("backend") == "external" else 0)
        form.addRow("训练/预测后端", backend)
        model = QLineEdit(self.sam_options["model"])
        device = QLineEdit(self.sam_options["device"])
        form.addRow("SAM 权重路径", model)
        form.addRow("SAM 设备", device)
        edits = {}
        for field, label in [("backend_id", "外部后端 ID"), ("display_name", "外部模型显示名"),
                             ("python_executable", "Python 解释器"), ("model_manifest", "外部模型清单"),
                             ("prepare_dataset_command", "准备命令（可选）"), ("train_command", "训练命令"),
                             ("predict_command", "预测命令")]:
            edit = QLineEdit(str(external[field]))
            edits[field] = edit
            if field.endswith("command"):
                edit.setPlaceholderText('"{python}" "path/to/adapter.py" --contract "{contract_json}"')
            form.addRow(label, edit)
        tasks = QLineEdit(",".join(external["tasks"]))
        form.addRow("支持任务", tasks)
        fmt = QComboBox()
        fmt.addItems(["yolo", "coco"])
        fmt.setCurrentText(external["dataset_format"])
        form.addRow("检测/分割数据格式", fmt)
        timeout = QSpinBox()
        timeout.setRange(1, 604800)
        timeout.setValue(external["timeout_seconds"])
        form.addRow("超时（秒）", timeout)
        params = QPlainTextEdit(json.dumps(external["train_params"], ensure_ascii=False, indent=2))
        params.setMaximumHeight(120)
        form.addRow("外部有效训练参数 JSON", params)
        notes = QLabel("配置仅作用于当前实例项目，不改动 2D/STL/TIF 配置。外部命令使用 shell=False；\n模型输出必须包含实例数组、类别映射与来源身份。接口说明：docs/contracts/instance_backend_contract_zh.md")
        notes.setWordWrap(True)
        form.addRow(notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            return
        value = {key: edit.text().strip() for key, edit in edits.items()}
        value.update(tasks=[s.strip() for s in tasks.text().split(",") if s.strip()], dataset_format=fmt.currentText(),
                     timeout_seconds=timeout.value(), train_params=json.loads(params.toPlainText()))
        external = sanitize_instance_backend(value)
        if backend.currentData() == "external" and not (external["train_command"] or external["predict_command"]):
            raise ValueError("选择外部后端时至少配置训练或预测命令")
        self.sam_options = {"model": model.text().strip(), "device": device.text().strip()}
        settings.update(sam=self.sam_options, backend=backend.currentData(), external_backend=external)
        project.set_settings(settings)
        self.log.appendPlainText("实例模型设置已保存；其他工作台配置未修改。")

    def start_job(self, job, callback):
        if self.busy or self.process is not None:
            raise ValueError("已有后台任务运行，请等待或取消训练")
        self.busy = True
        self.cancel_event.clear()
        self.job_callback = callback
        self.status.setText("后台处理中；已保存的标注保留")
        self.job_requested.emit(job)

    def _job_done(self, result):
        self.busy = False
        if self.cancel_event.is_set():
            self.log.appendPlainText("任务已取消，后台结果未写入标注。")
            self.refresh_objects()
            return
        self.guard(lambda: self.job_callback(result))
        if self.candidate:
            self.preview_candidate()
        else:
            self.refresh_objects()

    def _job_failed(self, message):
        self.busy = False
        self.log.appendPlainText(message)
        self.refresh_objects()
        QMessageBox.warning(self, "后台任务失败", message)

    def cancel_task(self):
        if self.busy:
            self.cancel_event.set()
            self.log.appendPlainText("已请求取消；正在执行的模型计算结束后丢弃结果，导出将在下一张图片前停止。")
        if self.process is not None:
            self.training_cancelled = True
            (Path(self.training_record["config"]["run_dir"]) / "CANCEL_REQUESTED").touch()
            process = self.process
            QTimer.singleShot(15000, lambda: process.kill() if self.process is process else None)
            self.log.appendPlainText("已请求取消训练，等待当前批次结束；15 秒仍未结束时停止进程。")

    def sam_prompt(self, payload):
        project = self.require_project()
        if not self.image_id:
            raise ValueError("请选择图片")
        image = project.get("images", self.image_id)
        key = self.canvas.active_id if self.redraw.isChecked() else None
        if self.redraw.isChecked() and not key:
            raise ValueError("请选择重描个体")
        revision = project.get("instances", key)["revision"] if key else None
        if "points" in payload:
            self.prompt_points.extend(payload["points"])
            self.prompt_labels.extend(payload["labels"])
            prompt = {"points": list(self.prompt_points), "labels": list(self.prompt_labels)}
        else:
            self.prompt_points, self.prompt_labels = [], []
            prompt = {"box": payload["box"]}
        context = (project.project_id, self.image_id, image["revision"], key, revision, self.categories.currentData(), project.revision)
        options = dict(self.sam_options)
        if not Path(options["model"]).is_file():
            raise ValueError("SAM 权重不存在，请在模型设置中选择已有权重")
        path = str(project.image_path(image))
        def ready(masks):
            if not self.context_matches(context):
                self.log.appendPlainText("图片或标注已变化，迟到的 SAM 结果未写入。")
                return
            index = 0
            if len(masks) > 1:
                value, ok = QInputDialog.getInt(self, "SAM 候选", f"返回 {len(masks)} 个候选，请选择序号", 1, 1, len(masks))
                if not ok:
                    return
                index = value - 1
            self.candidate = (context, [{"mask": masks[index], "category_id": context[5], "source": "sam"}])
            self.preview_candidate()
        project_root = self.project.root
        self.start_job(lambda worker: worker.sam_predict(path, options, prompt, project_root), ready)

    def context_matches(self, context):
        if not self.project or self.project.project_id != context[0] or self.image_id != context[1]:
            return False
        if len(context) > 6 and self.project.revision != context[6]:
            return False
        if self.project.get("images", context[1])["revision"] != context[2]:
            return False
        if context[3]:
            try:
                return self.project.get("instances", context[3])["revision"] == context[4]
            except KeyError:
                return False
        return True

    def preview_candidate(self):
        from ..core.instance_project import mask_box
        context, items = self.candidate
        display = self.project.records("instances", self.image_id)
        for n, item in enumerate(items):
            if item.get("task") == "classify":
                continue
            display.append({"id": f"candidate_{n}", "box": mask_box(item["mask"]) if item.get("mask") else item["box"], "mask": item.get("mask"), "category_id": item.get("category_id"), "review": "draft"})
        self.canvas.set_objects(display, self.canvas.names)
        self.candidate_label.setText(f"{len(items)} 个候选：采用后仍需人工确认；取消不改变原标注")

    def clear_candidate(self):
        self.candidate = None
        self.prompt_points, self.prompt_labels = [], []
        self.candidate_label.setText("中键平移；滚轮缩放；Esc 取消绘制")
        self.refresh_objects()

    def accept_candidate(self):
        if not self.candidate:
            return
        context, proposals = self.candidate
        if not self.context_matches(context):
            raise ValueError("图片或对象已变化，请重新推理")
        changes = []
        for proposal in proposals:
            key = context[3]
            if proposal.get("task") == "classify":
                if not key:
                    raise ValueError("分类结果必须关联选中个体")
                record = self.project.get("instances", key)
                record.update(category_id=proposal["category_id"], class_source=proposal.get("source", "model"), score=proposal["score"], review="draft", revision=record["revision"]+1)
                changes.extend([("instances", key, record), self.project._dirty_image(context[1])])
            else:
                self.project.put_instance(context[1], proposal.get("category_id"), proposal.get("box"), mask=proposal.get("mask"), key=key,
                                          source=proposal.get("source", "model"), expected_revision=context[4], changes=changes, score=proposal.get("score"))
        if changes:
            self.project.change("accept_prediction_candidates", changes)
        self.clear_candidate()
        self.refresh()

    def export(self):
        project = self.require_project()
        choice, ok = QInputDialog.getItem(self, "导出任务", "选择格式（仅导出符合审核条件的数据）", ["COCO 检测", "COCO 实例分割", "YOLO 检测", "YOLO 分割", "单体分类"], 0, False)
        if not ok:
            return
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not folder:
            return
        task = "classify" if choice == "单体分类" else "segment" if "分割" in choice else "detect"
        fmt = "classification" if task == "classify" else "yolo" if "YOLO" in choice else "coco"
        snapshot = FrozenInstanceDataset(project)
        def ready(result):
            destination, report = result
            self.log.appendPlainText(f"导出 {report['images']} 张图/{report['instances']} 个体：{destination}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(destination)))
        self.start_job(lambda worker: export_dataset(snapshot, folder, task=task, format=fmt, cancel_check=self.cancel_event.is_set), ready)

    def train_dialog(self):
        project = self.require_project()
        if self.process is not None:
            if QMessageBox.question(self, "取消训练", "停止当前训练进程？已保存标注不受影响。") == QMessageBox.Yes:
                self.cancel_task()
            return
        if self.busy:
            raise ValueError("请等待 SAM/预测结束")
        dialog = QDialog(self)
        dialog.setWindowTitle("物种模型训练")
        form = QFormLayout(dialog)
        task_combo = QComboBox()
        for label, value in [("目标检测", "detect"), ("实例分割", "segment"), ("单体分类", "classify")]:
            task_combo.addItem(label, value)
        form.addRow("任务", task_combo)
        weights = QLineEdit()
        weights.setPlaceholderText("本地 .pt 权重或已安装模型 YAML 路径")
        form.addRow("初始模型", weights)
        epochs, batch, size = QSpinBox(), QSpinBox(), QSpinBox()
        for spin, low, high, default in [(epochs, 1, 10000, 50), (batch, 1, 512, 4), (size, 32, 4096, 640)]:
            spin.setRange(low, high)
            spin.setValue(default)
        form.addRow("轮次", epochs)
        form.addRow("批大小", batch)
        form.addRow("输入尺寸", size)
        device = QLineEdit("cpu")
        form.addRow("设备 cpu / 0", device)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            return
        if not Path(weights.text()).is_file():
            raise ValueError("请选择存在的本地初始权重/模型配置，避免意外下载")
        task = task_combo.currentData()
        settings = project.settings()
        external = settings.get("external_backend") if settings.get("backend") == "external" else None
        if external:
            from ..core.instance_external_backend import sanitize_instance_backend
            external = sanitize_instance_backend(external)
            if task not in external["tasks"] or not external["train_command"]:
                raise ValueError("外部后端未配置此任务的训练能力")
        export_format = external["dataset_format"] if external else "yolo"
        destination, report = export_dataset(project, project.root / "exports", task=task, format="classification" if task == "classify" else export_format)
        from ..core.instance_training import verify_export
        verify_export(destination, task)
        run_id = uid("run")
        run_dir = project.root / "runs" / run_id
        run_dir.mkdir(parents=True)
        config = {"task": task, "weights": str(Path(weights.text()).resolve()), "dataset": str(destination), "run_dir": str(run_dir),
                  "epochs": epochs.value(), "batch": batch.value(), "imgsz": size.value(), "device": device.text()}
        if external:
            config["external_backend"] = external
        atomic_write_json(run_dir / "config.json", config)
        self.training_record = {"id": run_id, "status": "running", "config": config}
        project.record_run(self.training_record)
        self.training_cancelled = False
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._training_output)
        self.process.finished.connect(self._training_finished)
        self.process.errorOccurred.connect(self._training_error)
        self.process.start(sys.executable, ["-u", "-m", "AntSleap.core.instance_training", str(run_dir / "config.json")])

    def _training_output(self):
        if self.process:
            text = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
            self.log.appendPlainText(text)
            path = Path(self.training_record["config"]["run_dir"]) / "training.log"
            with path.open("a", encoding="utf-8") as stream:
                stream.write(text)

    def _training_finished(self, code, status):
        if self.process is None:
            return
        self._training_output()
        self.training_record["status"] = "cancelled" if self.training_cancelled else "succeeded" if code == 0 else "failed"
        from ..core.training_run_recorder import TrainingRunRecorder
        ledger = Path(self.training_record["config"]["run_dir"]) / "ledger"
        if ledger.is_dir():
            recorder = TrainingRunRecorder(ledger)
            self.training_record["ledger_statuses"] = [r["status"] for r in recorder.list_records()]
        self.project.record_run(self.training_record)
        self.log.appendPlainText("训练状态：" + self.training_record["status"] + "；输出：" + self.training_record["config"]["run_dir"])
        self.process.deleteLater()
        self.process = None

    def _training_error(self, error):
        if error == QProcess.FailedToStart:
            self._training_finished(-1, QProcess.CrashExit)

    def predict_dialog(self):
        project = self.require_project()
        if not self.image_id:
            raise ValueError("请选择图片")
        settings = project.settings()
        external = settings.get("external_backend") if settings.get("backend") == "external" else None
        path = external.get("model_manifest", "") if external else ""
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "选择实例模型清单", str(project.root / "runs"), "模型清单 (*.json)")
        if not path:
            return
        threshold, ok = QInputDialog.getDouble(self, "候选筛选", "最低置信度（候选仍需人工审核）", .25, 0, 1, 2)
        if not ok:
            return
        from ..core.instance_training import predict
        image = project.get("images", self.image_id)
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        key = self.canvas.active_id if manifest["task"] == "classify" else None
        if manifest["task"] == "classify" and not key:
            raise ValueError("分类预测请先选中一个个体")
        image_path = project.image_path(image)
        revision = project.get("instances", key)["revision"] if key else None
        if key:
            from PIL import Image
            crop_dir = project.root / "runs" / uid("prediction")
            crop_dir.mkdir(parents=True)
            crop = crop_dir / "crop.png"
            with Image.open(image_path) as im:
                im.crop(tuple(project.get("instances", key)["box"])).save(crop)
            image_path = crop
        context = (project.project_id, self.image_id, image["revision"], key, revision, None, project.revision)
        category_ids = [c["id"] for c in project.records("categories")]
        def ready(items):
            if self.context_matches(context):
                filtered = [item for item in items if item.get("score", 0) >= threshold]
                self.candidate = (context, filtered)
                self.preview_candidate()
                self.log.appendPlainText(f"预测 {len(items)} 个候选，阈值后保留 {len(filtered)} 个；不会覆盖已确认个体。")
        if external:
            from ..core.instance_external_backend import external_predict
            external = dict(external, model_manifest=path)
            categories = project.records("categories")
            inference_image = dict(image)
            if key:
                from ..core.instance_project import digest
                with Image.open(image_path) as cropped:
                    inference_image.update(width=cropped.width, height=cropped.height, hash=digest(image_path))
            self.start_job(lambda worker: external_predict(external, run_root=project.root / "runs", project_id=project.project_id,
                          revision=context[6], image=inference_image, image_path=image_path, categories=categories, task=manifest["task"],
                          instance_id=key, cancel_check=self.cancel_event.is_set), ready)
        else:
            self.start_job(lambda worker: predict(path, image_path, category_ids, project_root=project.root), ready)

    def ask_agent(self):
        self.agent_requested.emit(self.get_agent_context())

    def get_agent_context(self):
        project = self.require_project()
        return {"source_workbench": "species_instances", "project_type": "species_instances_2d",
                                   "project_path": str(project.path), "project_id": project.project_id,
                                   "image_id": self.image_id, "instance_count": len(project.records("instances")),
                                   "diagnostic_route": "species_instances", "safety_notes": "禁止调用旧 labels.parts/Blink 写入命令；实例 CLI 可读、校验、导出、训练、预测及提交草稿。人工确认只能在工作台进行。",
                                   "source_code_refs": "tools/agentic/instance_workbench.py",
                                   "llm_context_refs": "docs/contracts/instance_agent_contract_zh.md; docs/contracts/instance_backend_contract_zh.md"}

    def poll_agent_requests(self):
        if not self.project or self.busy or self.process is not None or self.canvas.start or self.canvas.vertices or self.canvas.brush_mask is not None:
            return
        from ..core.instance_agent import process_inbox
        try:
            results = process_inbox(self.project)
            if results:
                for result in results:
                    self.log.appendPlainText(f"智能体请求 {result['request_id']}：{result['status']}；所有新增对象仍需人工确认。")
                self.refresh()
        except Exception as exc:
            self.agent_timer.stop()
            self.log.appendPlainText(f"智能体请求处理暂停：{exc}；重开项目后可重试。")
