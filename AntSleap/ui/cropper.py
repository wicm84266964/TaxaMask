from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QListWidget, QScrollArea, QWidget, QLineEdit, QFileDialog, QMessageBox, QSplitter, QGroupBox)
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QImage
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
import os
from PIL import Image

from .style import (
    BUTTON_ROLE_COMMIT,
    BUTTON_ROLE_NEUTRAL,
    SURFACE_ROLE_CANVAS,
    SURFACE_ROLE_PANEL,
    SURFACE_ROLE_RAISED,
    apply_semantic_button_style,
    apply_surface_role,
)

CROPPER_TRANSLATIONS = {
    "zh": {
        "Crop {0}": "裁剪 {0}",
        "Smart Image Cropper": "智能图片裁剪器",
        "1. Load Image with Multiple Views": "1. 加载含多个视角的图片",
        "Load Image": "加载图片",
        "2. Draw Boxes (Crops)": "2. 绘制裁剪框",
        "Undo Last Crop": "撤销上一个裁剪框",
        "3. Export": "3. 导出",
        "Save & Add to Project": "保存并加入项目",
        "Open Image": "打开图片",
        "View {0} ({1}x{2})": "视角 {0}（{1}x{2}）",
        "Empty": "空内容",
        "Please load an image and draw at least one crop box.": "请先加载图片，并至少绘制一个裁剪框。",
        "Success": "成功",
        "Created {0} images.": "已生成 {0} 张图片。",
        "Error": "错误",
        "Failed to save crops:\n{0}": "保存裁剪结果失败：\n{0}",
        "Cropping: {0}": "正在裁剪：{0}",
    }
}


def translate_cropper_text(text, lang="en"):
    if lang == "zh":
        return CROPPER_TRANSLATIONS["zh"].get(text, text)
    return text

class CropCanvas(QWidget):
    crop_added = Signal(QRectF)

    def __init__(self):
        super().__init__()
        self.lang = "en"
        self.pixmap = None
        self.crops = [] # List of QRectF
        self.current_rect = QRectF()
        self.is_drawing = False
        self.start_pos = QPointF()
        self.scale = 1.0
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #202020;")

    def load_image(self, path):
        self.pixmap = QPixmap(path)
        self.crops = []
        self.current_rect = QRectF()
        self.update()

    def set_language(self, lang):
        self.lang = lang
        self.update()

    def paintEvent(self, event):
        if not self.pixmap: return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Scale to fit width
        w_ratio = self.width() / self.pixmap.width()
        h_ratio = self.height() / self.pixmap.height()
        self.scale = min(w_ratio, h_ratio) * 0.95
        
        # Center image
        disp_w = self.pixmap.width() * self.scale
        disp_h = self.pixmap.height() * self.scale
        offset_x = (self.width() - disp_w) / 2
        offset_y = (self.height() - disp_h) / 2
        
        painter.translate(offset_x, offset_y)
        painter.scale(self.scale, self.scale)
        
        painter.drawPixmap(0, 0, self.pixmap)
        
        # Draw Existing Crops
        painter.setPen(QPen(QColor(0, 255, 0), 3))
        painter.setBrush(QColor(0, 255, 0, 30))
        for i, r in enumerate(self.crops):
            painter.drawRect(r)
            painter.drawText(r.topLeft(), translate_cropper_text("Crop {0}", self.lang).format(i+1))
            
        # Draw Current Rect
        if self.is_drawing:
            painter.setPen(QPen(QColor(255, 255, 0), 2, Qt.DashLine))
            painter.setBrush(QColor(255, 255, 0, 30))
            painter.drawRect(self.current_rect)

    def mousePressEvent(self, event):
        if not self.pixmap: return
        if event.button() == Qt.LeftButton:
            self.is_drawing = True
            # Convert screen to image coords
            self.start_pos = self.screen_to_image(event.position())
            self.current_rect = QRectF(self.start_pos, self.start_pos)
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            curr_pos = self.screen_to_image(event.position())
            self.current_rect = QRectF(self.start_pos, curr_pos).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.is_drawing:
            self.is_drawing = False
            if self.current_rect.width() > 10 and self.current_rect.height() > 10:
                self.crops.append(self.current_rect)
                self.crop_added.emit(self.current_rect)
                self.current_rect = QRectF()
            self.update()

    def screen_to_image(self, pos):
        # Inverse logic of paintEvent transform
        disp_w = self.pixmap.width() * self.scale
        disp_h = self.pixmap.height() * self.scale
        offset_x = (self.width() - disp_w) / 2
        offset_y = (self.height() - disp_h) / 2
        
        x = (pos.x() - offset_x) / self.scale
        y = (pos.y() - offset_y) / self.scale
        
        # Clamp
        x = max(0, min(x, self.pixmap.width()))
        y = max(0, min(y, self.pixmap.height()))
        
        return QPointF(x, y)
    
    def remove_last(self):
        if self.crops:
            self.crops.pop()
            self.update()

class ImageCropper(QDialog):
    def __init__(self, initial_image=None, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(translate_cropper_text("Smart Image Cropper", self.lang))
        self.resize(1200, 800)
        self.generated_files = [] # List of abs paths
        self.generated_crops = [] # List of crop metadata dicts
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Left: Controls & List
        left_panel = QWidget()
        apply_surface_role(left_panel, SURFACE_ROLE_PANEL, "cropperFlowPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(12)

        self.load_panel = QGroupBox(translate_cropper_text("1. Load Image with Multiple Views", self.lang))
        apply_surface_role(self.load_panel, SURFACE_ROLE_PANEL, "cropperLoadPanel")
        load_layout = QVBoxLayout(self.load_panel)
        load_layout.setContentsMargins(12, 12, 12, 12)
        load_layout.setSpacing(8)
        
        self.btn_load = QPushButton(translate_cropper_text("Load Image", self.lang))
        self.btn_load.clicked.connect(self.browse_image)
        apply_semantic_button_style(self.btn_load, BUTTON_ROLE_NEUTRAL, "padding: 10px;")
        load_layout.addWidget(self.btn_load)
        left_layout.addWidget(self.load_panel)
        
        self.draw_panel = QGroupBox(translate_cropper_text("2. Draw Boxes (Crops)", self.lang))
        apply_surface_role(self.draw_panel, SURFACE_ROLE_PANEL, "cropperDrawPanel")
        draw_layout = QVBoxLayout(self.draw_panel)
        draw_layout.setContentsMargins(12, 12, 12, 12)
        draw_layout.setSpacing(8)
        self.crop_list = QListWidget()
        self.crop_list.setObjectName("cropperCropList")
        draw_layout.addWidget(self.crop_list)
        
        self.btn_undo = QPushButton(translate_cropper_text("Undo Last Crop", self.lang))
        self.btn_undo.clicked.connect(self.undo_crop)
        apply_semantic_button_style(self.btn_undo, BUTTON_ROLE_NEUTRAL)
        draw_layout.addWidget(self.btn_undo)
        left_layout.addWidget(self.draw_panel, 1)
        
        left_layout.addStretch()
        
        self.export_panel = QGroupBox(translate_cropper_text("3. Export", self.lang))
        apply_surface_role(self.export_panel, SURFACE_ROLE_RAISED, "cropperExportPanel")
        export_layout = QVBoxLayout(self.export_panel)
        export_layout.setContentsMargins(12, 12, 12, 12)
        export_layout.setSpacing(8)
        self.btn_save = QPushButton(translate_cropper_text("Save & Add to Project", self.lang))
        self.btn_save.clicked.connect(self.save_crops)
        apply_semantic_button_style(self.btn_save, BUTTON_ROLE_COMMIT, "font-weight: bold; padding: 12px;")
        export_layout.addWidget(self.btn_save)
        left_layout.addWidget(self.export_panel)
        
        left_panel.setFixedWidth(300)
        layout.addWidget(left_panel)
        
        # Right: Canvas
        self.canvas = CropCanvas()
        self.canvas.setObjectName("cropperCanvas")
        self.canvas.set_language(self.lang)
        self.canvas.crop_added.connect(self.on_crop_added)
        self.canvas_shell = QWidget()
        apply_surface_role(self.canvas_shell, SURFACE_ROLE_CANVAS, "cropperCanvasShell")
        canvas_layout = QVBoxLayout(self.canvas_shell)
        canvas_layout.setContentsMargins(12, 12, 12, 12)
        canvas_layout.addWidget(self.canvas)
        layout.addWidget(self.canvas_shell, 1)
        
        self.current_image_path = None
        
        if initial_image:
            self.load_image_by_path(initial_image)

    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, translate_cropper_text("Open Image", self.lang), "", "Images (*.png *.jpg *.jpeg *.tif)")
        if path:
            self.load_image_by_path(path)

    def load_image_by_path(self, path):
        self.current_image_path = path
        self.canvas.load_image(path)
        self.crop_list.clear()
        self.setWindowTitle(translate_cropper_text("Cropping: {0}", self.lang).format(os.path.basename(path)))

    def on_crop_added(self, rect):
        idx = self.crop_list.count() + 1
        item = translate_cropper_text("View {0} ({1}x{2})", self.lang).format(idx, int(rect.width()), int(rect.height()))
        self.crop_list.addItem(item)

    def undo_crop(self):
        self.canvas.remove_last()
        if self.crop_list.count() > 0:
            self.crop_list.takeItem(self.crop_list.count() - 1)

    def save_crops(self):
        if not self.current_image_path or not self.canvas.crops:
            QMessageBox.warning(self, translate_cropper_text("Empty", self.lang), translate_cropper_text("Please load an image and draw at least one crop box.", self.lang))
            return
            
        # Determine save directory (same as original image)
        save_dir = os.path.dirname(self.current_image_path)
        base_name = os.path.splitext(os.path.basename(self.current_image_path))[0]
        
        try:
            with Image.open(self.current_image_path) as img:
                self.generated_files = []
                self.generated_crops = []
                for i, rect in enumerate(self.canvas.crops):
                    # Crop logic
                    crop_box = (int(rect.left()), int(rect.top()), int(rect.right()), int(rect.bottom()))
                    cropped_img = img.crop(crop_box)
                    
                    # Save
                    new_filename = f"{base_name}__crop_{i+1:03d}.jpg"
                    new_path = os.path.join(save_dir, new_filename)
                    cropped_img.save(new_path, quality=95)
                    
                    abs_new_path = os.path.abspath(new_path)
                    self.generated_files.append(abs_new_path)
                    self.generated_crops.append(
                        {
                            "path": abs_new_path,
                            "source_image": os.path.abspath(self.current_image_path),
                            "crop_index": i + 1,
                            "crop_box": list(crop_box),
                            "source_size": [int(img.width), int(img.height)],
                        }
                    )
            
            QMessageBox.information(self, translate_cropper_text("Success", self.lang), translate_cropper_text("Created {0} images.", self.lang).format(len(self.generated_files)))
            self.accept() # Close dialog
            
        except Exception as e:
            QMessageBox.critical(self, translate_cropper_text("Error", self.lang), translate_cropper_text("Failed to save crops:\n{0}", self.lang).format(e))

    def get_files(self):
        return self.generated_files

    def get_crop_records(self):
        return [dict(item) for item in self.generated_crops]
