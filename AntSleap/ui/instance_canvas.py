"""Instance editing on the existing image viewport and navigation machinery."""
import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

from .canvas import AnnotationCanvas
from ..core.instance_project import decode_mask, encode_mask


class InstanceCanvas(AnnotationCanvas):
    selected = Signal(str)
    geometry_ready = Signal(object)
    prompt_ready = Signal(object)

    def __init__(self, parent=None):
        super().__init__()
        if parent:
            self.setParent(parent)
        self.objects = []
        self.names = {}
        self.active_id = ""
        self.tool = "select"
        self.start = None
        self.end = None
        self.vertices = []
        self.vertex_index = None
        self.edit_polygon = None
        self.brush_mask = None
        self.brush_radius = 6
        self.mask_cache = {}
        self.opacity = 0.35
        self.show_masks = True
        self._pan = None

    def set_objects(self, objects, names):
        self.objects, self.names = objects, names
        self.mask_cache.clear()
        for record in objects:
            if record.get("mask"):
                a = decode_mask(record["mask"])
                ys, xs = np.where(a)
                if not len(xs):
                    continue
                left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1)
                a = a[top:bottom, left:right]
                rgba = np.zeros((*a.shape, 4), dtype=np.uint8)
                rgba[..., :3] = self.color(record).getRgb()[:3]
                rgba[..., 3] = a * int(255 * self.opacity)
                self.mask_cache[record["id"]] = (QPointF(left, top), QImage(rgba.data, a.shape[1], a.shape[0], rgba.strides[0], QImage.Format_RGBA8888).copy())
        self.update()

    def color(self, record):
        import hashlib
        hue = int(hashlib.sha256(str(record.get("category_id", "")).encode()).hexdigest()[:4], 16) % 360
        return QColor.fromHsv(hue, 180, 245)

    def set_tool(self, tool):
        self.tool = tool
        self.cancel_gesture()

    def cancel_gesture(self):
        self.start = self.end = self.brush_mask = self.edit_polygon = self.vertex_index = None
        self.vertices = []
        self.update()

    def _point(self, event):
        x, y = self.screen_to_image(event.position().x(), event.position().y())
        return [max(0, min(float(x), self.original_pixmap.width())), max(0, min(float(y), self.original_pixmap.height()))]

    def paintEvent(self, event):
        # Existing canvas retains image display, fit, zoom, and coordinate conversion.
        super().paintEvent(event)
        if self.original_pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.offset)
        painter.scale(self.scale, self.scale)
        for n, record in enumerate(self.objects, 1):
            if self.show_masks and record["id"] in self.mask_cache:
                origin, overlay = self.mask_cache[record["id"]]
                painter.drawImage(origin, overlay)
            color = self.color(record)
            pen = QPen(color, (3 if record["id"] == self.active_id else 1.5) / self.scale)
            if record["review"] != "confirmed":
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            x1, y1, x2, y2 = record["box"]
            painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))
            painter.save()
            painter.resetTransform()
            pos = self.image_to_screen(x1, y1)
            painter.drawText(pos, f"#{n} {self.names.get(record.get('category_id'), '未鉴定')} · {'已确认' if record['review'] == 'confirmed' else '待确认'}")
            painter.restore()
        painter.setPen(QPen(QColor("#ffffff"), 2 / self.scale))
        if self.start and self.end and self.tool in {"box", "sam_box"}:
            painter.drawRect(QRectF(QPointF(*self.start), QPointF(*self.end)).normalized())
        points = self.edit_polygon or self.vertices
        if points:
            painter.drawPolyline(QPolygonF([QPointF(*p) for p in points]))
            for p in points:
                painter.drawEllipse(QPointF(*p), 4 / self.scale, 4 / self.scale)
        if self.brush_mask is not None:
            rgba = np.zeros((*self.brush_mask.shape, 4), np.uint8)
            rgba[..., :3] = [255, 255, 255]
            rgba[..., 3] = self.brush_mask * 110
            painter.drawImage(QPointF(), QImage(rgba.data, rgba.shape[1], rgba.shape[0], rgba.strides[0], QImage.Format_RGBA8888).copy())
        painter.end()

    def mousePressEvent(self, event):
        if self.original_pixmap is None:
            return
        if event.button() == Qt.MiddleButton:
            self._pan = event.position()
            return
        if event.button() == Qt.RightButton:
            self.cancel_gesture()
            return
        if event.button() != Qt.LeftButton:
            return
        p = self._point(event)
        if self.tool == "select":
            hits = [r["id"] for r in self.objects if r["box"][0] <= p[0] <= r["box"][2] and r["box"][1] <= p[1] <= r["box"][3]]
            if hits:
                selected = hits[(hits.index(self.active_id) + 1) % len(hits)] if self.active_id in hits else hits[0]
                self.selected.emit(selected)
            return
        if self.tool in {"sam_point", "sam_negative"}:
            self.prompt_ready.emit({"points": [p], "labels": [0 if self.tool == "sam_negative" else 1]})
        elif self.tool == "polygon":
            self.vertices.append(p)
        elif self.tool == "vertices":
            record = next((r for r in self.objects if r["id"] == self.active_id), None)
            if record and record.get("mask"):
                from ..core.instance_dataset import mask_polygon
                try:
                    self.edit_polygon = mask_polygon(record["mask"])
                except ValueError:
                    self.geometry_ready.emit({"error": "多区域或含孔洞掩膜请用画笔/橡皮修补"})
                    return
                distances = [np.linalg.norm(np.array(q) - p) for q in self.edit_polygon]
                index = int(np.argmin(distances))
                if event.modifiers() & Qt.ShiftModifier and len(self.edit_polygon) > 3:
                    self.edit_polygon.pop(index)
                    self.geometry_ready.emit({"polygon": self.edit_polygon, "replace": True})
                    self.cancel_gesture()
                elif event.modifiers() & Qt.ControlModifier:
                    self.edit_polygon.insert(index + 1, p)
                    self.geometry_ready.emit({"polygon": self.edit_polygon, "replace": True})
                    self.cancel_gesture()
                else:
                    self.vertex_index = index
        elif self.tool in {"brush", "erase"}:
            record = next((r for r in self.objects if r["id"] == self.active_id), None)
            if record and record.get("mask"):
                self.brush_mask = decode_mask(record["mask"])
                self._dab(p)
        else:
            self.start = self.end = p
        self.update()

    def _dab(self, p):
        im = Image.fromarray(self.brush_mask)
        x, y = p
        r = self.brush_radius
        ImageDraw.Draw(im).ellipse((x-r, y-r, x+r, y+r), fill=0 if self.tool == "erase" else 1)
        self.brush_mask = np.asarray(im).copy()

    def mouseMoveEvent(self, event):
        if self._pan is not None:
            self.offset += event.position() - self._pan
            self._pan = event.position()
            self.update()
            return
        if self.original_pixmap is None:
            return
        p = self._point(event)
        if self.start:
            self.end = p
        if self.vertex_index is not None:
            self.edit_polygon[self.vertex_index] = p
        if self.brush_mask is not None:
            self._dab(p)
        self.update()

    def mouseReleaseEvent(self, event):
        if self._pan is not None:
            self._pan = None
            return
        if event.button() != Qt.LeftButton:
            return
        try:
            if self.start and self.end:
                x1, y1 = self.start
                x2, y2 = self.end
                box = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
                if box[2] > box[0] and box[3] > box[1]:
                    (self.prompt_ready if self.tool == "sam_box" else self.geometry_ready).emit({"box": box})
            if self.brush_mask is not None:
                self.geometry_ready.emit({"mask": encode_mask(self.brush_mask), "replace": True})
            if self.vertex_index is not None:
                self.geometry_ready.emit({"polygon": self.edit_polygon, "replace": True})
        except ValueError as exc:
            self.geometry_ready.emit({"error": str(exc)})
        if self.tool != "polygon":
            self.cancel_gesture()

    def mouseDoubleClickEvent(self, event):
        if self.tool == "polygon" and len(self.vertices) >= 3:
            points = list(self.vertices)
            self.cancel_gesture()
            self.geometry_ready.emit({"polygon": points})

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancel_gesture()
        elif event.key() in {Qt.Key_Return, Qt.Key_Enter} and len(self.vertices) >= 3:
            points = list(self.vertices)
            self.cancel_gesture()
            self.geometry_ready.emit({"polygon": points})
        # Domain history is owned by the project, never by AnnotationCanvas.
