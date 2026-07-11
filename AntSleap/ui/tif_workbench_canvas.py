import math
import os

import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QSlider, QSpinBox, QTreeWidget

try:
    from AntSleap.ui.style import get_theme_config, normalize_theme
    from AntSleap.ui.tif_gpu_volume_canvas import (
        TifGpuVolumeCanvas,
        TifGpuVolumeOffscreenWidget,
        gpu_volume_canvas_available,
        gpu_volume_offscreen_available,
        gpu_volume_unavailable_reason,
    )
    from AntSleap.ui.tif_workbench_translations import tt
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from ui.style import get_theme_config, normalize_theme
    from ui.tif_gpu_volume_canvas import (
        TifGpuVolumeCanvas,
        TifGpuVolumeOffscreenWidget,
        gpu_volume_canvas_available,
        gpu_volume_offscreen_available,
        gpu_volume_unavailable_reason,
    )
    from ui.tif_workbench_translations import tt


def _tif_canvas_background(theme="dark"):
    theme = normalize_theme(theme)
    return "#111A2B" if theme == "light" else "#07101D"


def _tif_overlay_background(alpha=190, theme="dark"):
    color = QColor(_tif_canvas_background(theme))
    color.setAlpha(int(alpha))
    return color


class WheelSafeComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class MirroredStatusLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._mirror_label = None

    def set_mirror_label(self, label):
        self._mirror_label = label
        if label is not None:
            label.setText(self.text())
            label.setToolTip(self.toolTip())

    def setText(self, text):
        super().setText(text)
        if self._mirror_label is not None:
            self._mirror_label.setText(str(text or ""))
            self._mirror_label.setToolTip(str(text or ""))

    def setToolTip(self, text):
        super().setToolTip(text)
        if self._mirror_label is not None:
            self._mirror_label.setToolTip(str(text or ""))


class LazyRegionMaskVolume:
    def __init__(self, source, region_id):
        self.source = source
        self.region_id = int(region_id)
        self.shape = tuple(int(value) for value in getattr(source, "shape", ()) or ())
        self.dtype = np.dtype(np.uint8)
        self.ndim = len(self.shape)

    @property
    def size(self):
        if not self.shape:
            return 0
        return int(np.prod(self.shape))

    @property
    def nbytes(self):
        return int(self.size)

    def __getitem__(self, key):
        return np.asarray(np.asarray(self.source[key]) == self.region_id, dtype=np.uint8)

    def __array__(self, dtype=None, copy=None):
        array = np.asarray(self.source) == self.region_id
        if copy is False:
            return np.asarray(array, dtype=dtype or np.uint8)
        return np.array(array, dtype=dtype or np.uint8, copy=True)


class WheelSafeSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()

    def _tif_shortcut_parent(self):
        parent = self.parent()
        while parent is not None:
            if callable(getattr(parent, "_handle_slice_shortcut_key", None)):
                return parent
            parent = parent.parent()
        return None

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            parent = self._tif_shortcut_parent()
            handler = getattr(parent, "_handle_slice_shortcut_key", None)
            if callable(handler) and handler(event.key()):
                event.accept()
                return
        super().keyPressEvent(event)


class WheelSafeSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class TifSpecimenTree(QTreeWidget):
    """Tree widget with a tiny QListWidget-like surface for older tests/helpers."""

    def count(self):
        return self.topLevelItemCount()

    def item(self, row):
        return self.topLevelItem(row)

    def addItem(self, item):
        self.addTopLevelItem(item)

    def setCurrentRow(self, row):
        item = self.topLevelItem(row)
        if item is not None:
            child = item.child(0)
            self.setCurrentItem(child or item)


class TifSliceCanvas(QLabel):
    ZOOM_STEPS = (1.0, 1.25, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tifSliceCanvas")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(360, 280)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFrameShape(QFrame.NoFrame)
        self.setMouseTracking(True)
        self.setText("No TIF volume loaded")
        self._pixmap = None
        self._draw_rect = QRectF()
        self._zoom_index = 0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._panning = False
        self._last_pan_pos = None
        self._hover_pos = None
        self._last_annotation_preview = {}
        self._roi_drag_start = None
        self._roi_drag_current = None
        self._contour_drag_points = []
        self._annotation_drag_active = False
        self._annotation_drag_erase = False
        self._lasso_drag_points = []
        self._shape_drag_mode = ""
        self._shape_drag_start = None
        self._shape_drag_current = None
        self.current_theme = "dark"
        self.workbench = None

    def set_theme(self, theme):
        self.current_theme = normalize_theme(theme)
        self._refresh_scaled_pixmap()

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
        theme = getattr(self.workbench, "current_theme", self.current_theme)
        composed.fill(QColor(_tif_canvas_background(theme)))
        painter = QPainter(composed)
        painter.drawPixmap(int(round(x)), int(round(y)), zoomed)
        self._draw_roi_overlays(painter)
        self._draw_contour_overlays(painter)
        self._draw_lasso_preview(painter)
        self._draw_shape_fill_preview(painter)
        self._draw_annotation_cursor_preview(painter)
        self._draw_status_overlay(painter)
        painter.end()
        self.setPixmap(composed)

    def _image_rect_to_widget_rect(self, image_rect):
        if self._pixmap is None or self._pixmap.isNull() or self._draw_rect.isNull():
            return QRectF()
        x0, y0, x1, y1 = [float(value) for value in image_rect]
        width = max(1.0, float(self._pixmap.width()))
        height = max(1.0, float(self._pixmap.height()))
        left = self._draw_rect.x() + (x0 / width) * self._draw_rect.width()
        right = self._draw_rect.x() + (x1 / width) * self._draw_rect.width()
        top = self._draw_rect.y() + (y0 / height) * self._draw_rect.height()
        bottom = self._draw_rect.y() + (y1 / height) * self._draw_rect.height()
        return QRectF(min(left, right), min(top, bottom), abs(right - left), abs(bottom - top))

    def _draw_roi_overlays(self, painter):
        if self.workbench is None:
            return
        rects = []
        if callable(getattr(self.workbench, "current_roi_overlay_rects", None)):
            rects = self.workbench.current_roi_overlay_rects()
        painter.save()
        for entry in rects:
            if isinstance(entry, dict):
                image_rect = entry.get("rect", [])
                color = QColor(str(entry.get("color", "#FFD34D")))
                fill = QColor(color)
                fill.setAlpha(34)
            else:
                image_rect = entry
                color = QColor("#FFD34D")
                fill = QColor(255, 211, 77, 34)
            rect = self._image_rect_to_widget_rect(image_rect)
            if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
                continue
            painter.fillRect(rect, fill)
            pen = QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect)
        if self._roi_drag_start is not None and self._roi_drag_current is not None:
            start = self._roi_drag_start
            current = self._roi_drag_current
            rect = QRectF(
                min(start.x(), current.x()),
                min(start.y(), current.y()),
                abs(current.x() - start.x()),
                abs(current.y() - start.y()),
            )
            if rect.width() > 1 and rect.height() > 1:
                painter.fillRect(rect, QColor(103, 168, 184, 36))
                pen = QPen(QColor("#67A8B8"))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(rect)
        painter.restore()

    def _image_point_to_widget_point(self, point):
        if self._pixmap is None or self._pixmap.isNull() or self._draw_rect.isNull():
            return None
        px, py = [float(value) for value in point]
        width = max(1.0, float(self._pixmap.width()))
        height = max(1.0, float(self._pixmap.height()))
        return (
            self._draw_rect.x() + (px / width) * self._draw_rect.width(),
            self._draw_rect.y() + (py / height) * self._draw_rect.height(),
        )

    def _draw_polyline(self, painter, points, color, closed=False, fill_alpha=0):
        if len(points) < 2:
            return
        widget_points = [self._image_point_to_widget_point(point) for point in points]
        widget_points = [point for point in widget_points if point is not None]
        if len(widget_points) < 2:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        polygon = None
        if closed and fill_alpha > 0 and len(widget_points) >= 3:
            polygon = QPolygonF([QPointF(float(x), float(y)) for x, y in widget_points])
            fill = QColor(color)
            fill.setAlpha(fill_alpha)
            painter.setBrush(fill)
        else:
            painter.setBrush(Qt.NoBrush)
        pen = QPen(QColor(color))
        pen.setWidth(2)
        painter.setPen(pen)
        if polygon is not None:
            painter.drawPolygon(polygon)
        for first, second in zip(widget_points, widget_points[1:]):
            painter.drawLine(QPointF(float(first[0]), float(first[1])), QPointF(float(second[0]), float(second[1])))
        if closed and len(widget_points) >= 3:
            painter.drawLine(
                QPointF(float(widget_points[-1][0]), float(widget_points[-1][1])),
                QPointF(float(widget_points[0][0]), float(widget_points[0][1])),
            )
        painter.restore()

    def _draw_contour_overlays(self, painter):
        if self.workbench is None:
            return
        contours = []
        if callable(getattr(self.workbench, "current_contour_overlay_polygons", None)):
            contours = self.workbench.part_mask_workflow_controller.current_contour_overlay_polygons()
        for contour in contours:
            if isinstance(contour, dict):
                self._draw_polyline(
                    painter,
                    contour.get("polygon", []),
                    str(contour.get("color", "#FF8C42")),
                    closed=True,
                    fill_alpha=int(contour.get("fill_alpha", 24)),
                )
        if self._contour_drag_points:
            self._draw_polyline(painter, self._contour_drag_points, "#FF8C42", closed=False, fill_alpha=0)

    def _draw_lasso_preview(self, painter):
        if len(self._lasso_drag_points) < 2:
            return
        closed = len(self._lasso_drag_points) >= 3
        self._draw_polyline(painter, self._lasso_drag_points, "#8ED2DE", closed=closed, fill_alpha=28 if closed else 0)

    def _draw_shape_fill_preview(self, painter):
        if not self._shape_drag_mode or self._shape_drag_start is None or self._shape_drag_current is None:
            return
        start = self._shape_drag_start
        current = self._shape_drag_current
        rect = QRectF(
            min(start.x(), current.x()),
            min(start.y(), current.y()),
            abs(current.x() - start.x()),
            abs(current.y() - start.y()),
        )
        if rect.width() <= 1 or rect.height() <= 1:
            return
        painter.save()
        fill = QColor("#8ED2DE")
        fill.setAlpha(34)
        pen = QPen(QColor("#8ED2DE"))
        pen.setWidth(2)
        painter.setBrush(fill)
        painter.setPen(pen)
        if self._shape_drag_mode == "ellipse":
            painter.drawEllipse(rect)
        else:
            painter.drawRect(rect)
        painter.restore()

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
        theme = getattr(self.workbench, "current_theme", self.current_theme)
        painter.fillRect(rect, _tif_overlay_background(190, theme))
        painter.setPen(QColor("#DCE4E8"))
        painter.drawText(rect.adjusted(8, 4, -8, -4), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()

    def _draw_annotation_cursor_preview(self, painter):
        self._last_annotation_preview = {}
        if self.workbench is None or self._hover_pos is None:
            return
        if (
            self.workbench.part_mask_workflow_controller.is_part_contour_draw_mode()
        ):
            return
        if self._pixmap is None or self._pixmap.isNull() or self._draw_rect.isNull():
            return
        pixel = self.widget_to_image_pixel(self._hover_pos.x(), self._hover_pos.y())
        if pixel is None:
            return
        preview = {}
        if callable(getattr(self.workbench, "annotation_cursor_preview", None)):
            preview = self.workbench.annotation_cursor_preview(pixel) or {}
        if not preview:
            return
        px, py = pixel
        center = self._image_point_to_widget_point([float(px) + 0.5, float(py) + 0.5])
        if center is None:
            return
        mode = str(preview.get("mode") or "")
        disabled = bool(preview.get("disabled"))
        radius = max(1.0, float(preview.get("radius", 1.0)))
        scale_x = self._draw_rect.width() / max(1.0, float(self._pixmap.width()))
        scale_y = self._draw_rect.height() / max(1.0, float(self._pixmap.height()))
        radius_x = max(3.0, radius * scale_x)
        radius_y = max(3.0, radius * scale_y)
        color = QColor("#8ED2DE")
        if mode == "eraser":
            color = QColor("#FFB3A6")
        elif mode in {"lasso", "rectangle", "ellipse"}:
            color = QColor("#8ED2DE")
        elif mode == "picker":
            color = QColor("#F6D365")
        if disabled:
            color = QColor("#C9D0D4")
        painter.save()
        pen = QPen(color)
        pen.setWidth(2)
        if mode == "eraser" or disabled:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        if mode in {"brush", "eraser"}:
            rect = QRectF(center[0] - radius_x, center[1] - radius_y, radius_x * 2.0, radius_y * 2.0)
            painter.drawEllipse(rect)
            if mode == "eraser":
                painter.drawLine(int(center[0] - radius_x * 0.55), int(center[1]), int(center[0] + radius_x * 0.55), int(center[1]))
        elif mode == "lasso":
            size = 7
            painter.drawLine(int(center[0] - size), int(center[1]), int(center[0] + size), int(center[1]))
            painter.drawLine(int(center[0]), int(center[1] - size), int(center[0]), int(center[1] + size))
            painter.drawEllipse(QRectF(center[0] - size * 0.6, center[1] - size * 0.6, size * 1.2, size * 1.2))
        elif mode in {"rectangle", "ellipse"}:
            size = 9
            rect = QRectF(center[0] - size, center[1] - size, size * 2.0, size * 2.0)
            if mode == "ellipse":
                painter.drawEllipse(rect)
            else:
                painter.drawRect(rect)
        elif mode == "picker":
            size = 8
            painter.drawLine(int(center[0] - size), int(center[1]), int(center[0] + size), int(center[1]))
            painter.drawLine(int(center[0]), int(center[1] - size), int(center[0]), int(center[1] + size))
        if disabled:
            painter.drawLine(int(center[0] - radius_x * 0.7), int(center[1] - radius_y * 0.7), int(center[0] + radius_x * 0.7), int(center[1] + radius_y * 0.7))
        painter.restore()
        self._last_annotation_preview = {
            "mode": mode,
            "disabled": disabled,
            "radius": radius,
            "pixel": [int(px), int(py)],
            "widget_radius": [float(radius_x), float(radius_y)],
        }

    def widget_to_image_point(self, x, y):
        if self._pixmap is None or self._pixmap.isNull() or self._draw_rect.isNull():
            return None
        if not self._draw_rect.contains(float(x), float(y)):
            return None
        rel_x = (float(x) - self._draw_rect.x()) / max(1.0, self._draw_rect.width())
        rel_y = (float(y) - self._draw_rect.y()) / max(1.0, self._draw_rect.height())
        px = rel_x * float(self._pixmap.width())
        py = rel_y * float(self._pixmap.height())
        return (
            max(0.0, min(float(self._pixmap.width()) - 1.0, px)),
            max(0.0, min(float(self._pixmap.height()) - 1.0, py)),
        )

    def widget_to_image_pixel(self, x, y):
        point = self.widget_to_image_point(x, y)
        if point is None:
            return None
        px, py = point
        return (
            max(0, min(int(self._pixmap.width()) - 1, int(px))),
            max(0, min(int(self._pixmap.height()) - 1, int(py))),
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
        self._hover_pos = event.position()
        if (
            self.workbench is not None
            and event.button() == Qt.LeftButton
            and callable(getattr(self.workbench, "is_part_roi_draw_mode", None))
            and self.workbench.is_part_roi_draw_mode()
        ):
            self._roi_drag_start = event.position()
            self._roi_drag_current = event.position()
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if (
            self.workbench is not None
            and event.button() == Qt.LeftButton
            and
            self.workbench.part_mask_workflow_controller.is_part_contour_draw_mode()
        ):
            point = self.widget_to_image_point(event.position().x(), event.position().y())
            self._contour_drag_points = [list(point)] if point is not None else []
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if event.button() == Qt.RightButton and self.zoom_factor() > 1.0:
            self._panning = True
            self._last_pan_pos = event.position()
            event.accept()
            return
        if self.workbench is not None and event.button() == Qt.LeftButton:
            mode = getattr(self.workbench, "annotation_tool_mode", "brush")
            if mode == "pan":
                if self.zoom_factor() > 1.0:
                    self._panning = True
                    self._last_pan_pos = event.position()
                elif callable(getattr(self.workbench, "_set_operation_feedback", None)):
                    self.workbench._set_operation_feedback(tt("Pan/view mode is active. Labels were not changed.", self.workbench.lang))
                event.accept()
                return
            if mode == "picker":
                self.workbench.part_mask_workflow_controller.pick_material_at_widget_position(event.position().x(), event.position().y())
                event.accept()
                return
            if mode == "lasso":
                pixel = self.widget_to_image_pixel(event.position().x(), event.position().y())
                if pixel is None:
                    event.accept()
                    return
                block_reason = ""
                if callable(getattr(self.workbench, "_editable_label_block_reason", None)):
                    block_reason = self.workbench._editable_label_block_reason(require_working_edit=True)
                if block_reason:
                    self.workbench._set_operation_feedback(block_reason)
                    event.accept()
                    return
                self._lasso_drag_points = [list(pixel)]
                self._refresh_scaled_pixmap()
                event.accept()
                return
            if mode in {"rectangle", "ellipse"}:
                pixel = self.widget_to_image_pixel(event.position().x(), event.position().y())
                if pixel is None:
                    event.accept()
                    return
                block_reason = ""
                if callable(getattr(self.workbench, "_editable_label_block_reason", None)):
                    block_reason = self.workbench._editable_label_block_reason(require_working_edit=True)
                if block_reason:
                    self.workbench._set_operation_feedback(block_reason)
                    event.accept()
                    return
                self._shape_drag_mode = mode
                self._shape_drag_start = event.position()
                self._shape_drag_current = event.position()
                self._refresh_scaled_pixmap()
                event.accept()
                return
            self._annotation_drag_active = True
            self._annotation_drag_erase = bool(event.modifiers() & Qt.ControlModifier) or mode == "eraser"
            if getattr(self.workbench, "annotation_workflow_controller", None) is not None:
                self.workbench.annotation_workflow_controller.begin_annotation_stroke()
            self.workbench.annotation_workflow_controller.paint_at_widget_position(
                event.position().x(),
                event.position().y(),
                erase=self._annotation_drag_erase,
                continue_stroke=True,
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._hover_pos = event.position()
        if self._roi_drag_start is not None and event.buttons() & Qt.LeftButton:
            self._roi_drag_current = event.position()
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if self._contour_drag_points and event.buttons() & Qt.LeftButton:
            point = self.widget_to_image_point(event.position().x(), event.position().y())
            if point is not None:
                last = self._contour_drag_points[-1] if self._contour_drag_points else None
                distance = math.hypot(float(point[0]) - float(last[0]), float(point[1]) - float(last[1])) if last else 999.0
                if distance >= 0.15:
                    self._contour_drag_points.append(list(point))
                    self._refresh_scaled_pixmap()
            event.accept()
            return
        if self._lasso_drag_points and event.buttons() & Qt.LeftButton:
            pixel = self.widget_to_image_pixel(event.position().x(), event.position().y())
            if pixel is not None:
                if self._lasso_drag_points[-1] != list(pixel):
                    self._lasso_drag_points.append(list(pixel))
                    self._refresh_scaled_pixmap()
            event.accept()
            return
        if self._shape_drag_mode and self._shape_drag_start is not None and event.buttons() & Qt.LeftButton:
            self._shape_drag_current = event.position()
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if self._panning and event.buttons() & (Qt.LeftButton | Qt.RightButton) and self._last_pan_pos is not None:
            current = event.position()
            self._pan_x += current.x() - self._last_pan_pos.x()
            self._pan_y += current.y() - self._last_pan_pos.y()
            self._last_pan_pos = current
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if self.workbench is not None and event.buttons() & Qt.LeftButton:
            mode = getattr(self.workbench, "annotation_tool_mode", "brush")
            if mode in {"picker", "pan"}:
                event.accept()
                return
            if mode in {"lasso", "rectangle", "ellipse"}:
                event.accept()
                return
            self.workbench.annotation_workflow_controller.paint_at_widget_position(
                event.position().x(),
                event.position().y(),
                erase=self._annotation_drag_erase if self._annotation_drag_active else bool(event.modifiers() & Qt.ControlModifier) or mode == "eraser",
                continue_stroke=self._annotation_drag_active,
            )
            event.accept()
            return
        if not event.buttons():
            self._refresh_scaled_pixmap()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._hover_pos = event.position()
        if event.button() == Qt.LeftButton and self._roi_drag_start is not None:
            start = self._roi_drag_start
            end = event.position()
            self._roi_drag_start = None
            self._roi_drag_current = None
            if self.workbench is not None:
                self.workbench.roi_workflow_controller.finish_drag(start.x(), start.y(), end.x(), end.y())
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._contour_drag_points:
            points = list(self._contour_drag_points)
            self._contour_drag_points = []
            if self.workbench is not None:
                self.workbench.part_mask_workflow_controller.finish_part_contour_drag(points)
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._lasso_drag_points:
            points = list(self._lasso_drag_points)
            self._lasso_drag_points = []
            if self.workbench is not None and callable(getattr(self.workbench, "finish_lasso_fill", None)):
                self.workbench.annotation_workflow_controller.finish_lasso_fill(points)
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._shape_drag_mode and self._shape_drag_start is not None:
            mode = self._shape_drag_mode
            start = self._shape_drag_start
            end = event.position()
            self._shape_drag_mode = ""
            self._shape_drag_start = None
            self._shape_drag_current = None
            if self.workbench is not None and callable(getattr(self.workbench, "finish_shape_fill_drag", None)):
                self.workbench.annotation_workflow_controller.finish_shape_fill_drag(mode, start.x(), start.y(), end.x(), end.y())
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._annotation_drag_active:
            if self.workbench is not None and getattr(self.workbench, "annotation_workflow_controller", None) is not None:
                self.workbench.annotation_workflow_controller.finish_annotation_stroke()
            self._annotation_drag_active = False
            self._annotation_drag_erase = False
            event.accept()
            return
        if event.button() in (Qt.LeftButton, Qt.RightButton) and self._panning:
            self._panning = False
            self._last_pan_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._hover_pos = None
        self._last_annotation_preview = {}
        self._refresh_scaled_pixmap()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.workbench is not None and event.button() == Qt.LeftButton:
            controller = getattr(self.workbench, "roi_workflow_controller", None)
            if controller is not None and controller.open_at_widget_position(event.position().x(), event.position().y()):
                event.accept()
                return
        super().mouseDoubleClickEvent(event)


class TifVolumeCanvas(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tifVolumeCanvas")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(360, 280)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFrameShape(QFrame.NoFrame)
        self.setText("No TIF volume loaded")
        self.workbench = None
        self._mouse_mode = ""
        self._last_drag_pos = None
        self._axis_overlays = []
        self._volume_pixmap = None
        self.current_theme = "dark"

    def set_theme(self, theme):
        self.current_theme = normalize_theme(theme)
        self._refresh_volume_pixmap()

    def _try_start_local_axis_endpoint_drag(self, event):
        if self.workbench is None or event.button() != Qt.LeftButton:
            return False
        handler = getattr(getattr(self.workbench, "local_axis_controller", None), "start_endpoint_drag", None)
        if not callable(handler):
            return False
        if not handler(event.position().x(), event.position().y()):
            return False
        self._mouse_mode = "local_axis_endpoint"
        self._last_drag_pos = event.position()
        event.accept()
        return True

    def set_axis_overlays(self, overlays):
        self._axis_overlays = list(overlays or [])
        self._refresh_volume_pixmap()
        self.update()

    def set_volume_pixmap(self, pixmap):
        if pixmap is None or pixmap.isNull():
            self._volume_pixmap = None
            self.clear()
            return
        self._volume_pixmap = QPixmap(pixmap)
        self._refresh_volume_pixmap()

    def _refresh_volume_pixmap(self):
        if self._volume_pixmap is None or self._volume_pixmap.isNull():
            return
        scaled = self._volume_pixmap.scaled(
            max(1, int(self.width())),
            max(1, int(self.height())),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        composed = QPixmap(max(1, int(self.width())), max(1, int(self.height())))
        theme = getattr(self.workbench, "current_theme", self.current_theme)
        composed.fill(QColor(_tif_canvas_background(theme)))
        painter = QPainter(composed)
        x = int(round((composed.width() - scaled.width()) / 2.0))
        y = int(round((composed.height() - scaled.height()) / 2.0))
        painter.drawPixmap(x, y, scaled)
        self._draw_status_overlay(painter)
        self._draw_axis_overlays(painter)
        painter.end()
        self.setPixmap(composed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_volume_pixmap()
        if self.workbench is not None:
            self.workbench.volume_render_controller.schedule_volume_preview_render()

    def _draw_status_overlay(self, painter):
        if self.workbench is None:
            return
        text = self.workbench.volume_status_text()
        if not text:
            return
        painter.save()
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        rect = QRectF(10, 10, text_w + 16, metrics.height() + 8)
        theme = getattr(self.workbench, "current_theme", self.current_theme)
        painter.fillRect(rect, _tif_overlay_background(190, theme))
        painter.setPen(QColor("#DCE4E8"))
        painter.drawText(rect.adjusted(8, 4, -8, -4), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()

    def _draw_axis_overlays(self, painter):
        if not self._axis_overlays:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        for overlay in self._axis_overlays:
            if overlay.get("kind") == "polyline":
                points = overlay.get("points_xy") if isinstance(overlay.get("points_xy"), (list, tuple)) else []
                points = [point for point in points if isinstance(point, (list, tuple)) and len(point) >= 2]
                if len(points) < 2:
                    continue
                color = QColor(str(overlay.get("color") or "#FFFFFF"))
                painter.setPen(QPen(color, int(overlay.get("width", 2))))
                for first, second in zip(points, points[1:]):
                    painter.drawLine(int(round(float(first[0]))), int(round(float(first[1]))), int(round(float(second[0]))), int(round(float(second[1]))))
                label = str(overlay.get("label") or "")
                anchor = overlay.get("label_anchor_xy") if isinstance(overlay.get("label_anchor_xy"), (list, tuple)) else points[-1]
                if label and anchor:
                    dx, dy = overlay.get("label_offset_xy") or (8, -8)
                    self._draw_axis_label(painter, label, float(anchor[0]) + float(dx), float(anchor[1]) + float(dy), color, str(overlay.get("label_position") or "right"))
                continue
            if overlay.get("kind") == "point":
                point = overlay.get("point_xy")
                if not point:
                    continue
                color = QColor(str(overlay.get("color") or "#FFFFFF"))
                x, y = float(point[0]), float(point[1])
                radius = int(overlay.get("radius", 5))
                painter.setPen(QPen(color, 2))
                theme = getattr(self.workbench, "current_theme", self.current_theme)
                painter.setBrush(_tif_overlay_background(150, theme))
                painter.drawEllipse(int(round(x - radius)), int(round(y - radius)), radius * 2, radius * 2)
                label = str(overlay.get("label") or "")
                if label:
                    dx, dy = overlay.get("label_offset_xy") or (8, -8)
                    self._draw_axis_label(painter, label, x + float(dx), y + float(dy), color, str(overlay.get("label_position") or "right"))
                continue
            start = overlay.get("start_xy")
            end = overlay.get("end_xy")
            if not start or not end:
                continue
            color = QColor(str(overlay.get("color") or "#FFB84D"))
            painter.setPen(QPen(color, int(overlay.get("width", 2))))
            x0, y0 = float(start[0]), float(start[1])
            x1, y1 = float(end[0]), float(end[1])
            painter.drawLine(int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1)))
            role = str(overlay.get("role") or "")
            handle_radius = 6 if role == "editable_output" else 3
            if role == "editable_output":
                theme = getattr(self.workbench, "current_theme", self.current_theme)
                painter.setBrush(_tif_overlay_background(185, theme))
            else:
                painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(
                int(round(x0 - handle_radius)),
                int(round(y0 - handle_radius)),
                handle_radius * 2,
                handle_radius * 2,
            )
            painter.drawEllipse(
                int(round(x1 - handle_radius)),
                int(round(y1 - handle_radius)),
                handle_radius * 2,
                handle_radius * 2,
            )
            label = str(overlay.get("label") or "")
            if label:
                anchor = overlay.get("label_anchor_xy") or end
                dx, dy = overlay.get("label_offset_xy") or (8, -8)
                self._draw_axis_label(
                    painter,
                    label,
                    float(anchor[0]) + float(dx),
                    float(anchor[1]) + float(dy),
                    color,
                    str(overlay.get("label_position") or "right"),
                )
        painter.restore()

    def _draw_axis_label(self, painter, text, x, y, color, position="right"):
        metrics = painter.fontMetrics()
        padding_x = 6
        padding_y = 3
        text_w = metrics.horizontalAdvance(text)
        text_h = metrics.height()
        rect_x = float(x)
        rect_y = float(y) - text_h - padding_y
        if str(position) == "left":
            rect_x -= text_w + padding_x * 2
        elif str(position) == "center":
            rect_x -= (text_w + padding_x * 2) / 2.0
        rect = QRect(
            int(round(rect_x)),
            int(round(rect_y)),
            int(round(text_w + padding_x * 2)),
            int(round(text_h + padding_y * 2)),
        )
        bounds = self.rect().adjusted(2, 2, -2, -2)
        if rect.right() > bounds.right():
            rect.moveRight(bounds.right())
        if rect.left() < bounds.left():
            rect.moveLeft(bounds.left())
        if rect.top() < bounds.top():
            rect.moveTop(bounds.top())
        if rect.bottom() > bounds.bottom():
            rect.moveBottom(bounds.bottom())
        theme = getattr(self.workbench, "current_theme", self.current_theme)
        painter.fillRect(rect, _tif_overlay_background(205, theme))
        painter.setPen(QPen(color, 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.setPen(QColor("#F4F7F9"))
        painter.drawText(rect.adjusted(padding_x, padding_y, -padding_x, -padding_y), Qt.AlignLeft | Qt.AlignVCenter, text)

    def mousePressEvent(self, event):
        self.setFocus(Qt.MouseFocusReason)
        if self.workbench is not None and event.button() == Qt.LeftButton:
            picker = getattr(getattr(self.workbench, "local_axis_controller", None), "pick_roll_reference_at", None)
            if callable(picker) and picker(event.position().x(), event.position().y()):
                event.accept()
                return
        if self._try_start_local_axis_endpoint_drag(event):
            return
        if self.workbench is not None and event.button() in (Qt.LeftButton, Qt.RightButton):
            self._mouse_mode = "rotate" if event.button() == Qt.LeftButton else "pan"
            self._last_drag_pos = event.position()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        buttons = event.buttons()
        active = (
            (self._mouse_mode == "rotate" and buttons & Qt.LeftButton)
            or (self._mouse_mode == "local_axis_endpoint" and buttons & Qt.LeftButton)
            or (self._mouse_mode == "pan" and buttons & Qt.RightButton)
        )
        if self.workbench is not None and active and self._last_drag_pos is not None:
            current = event.position()
            dx = current.x() - self._last_drag_pos.x()
            dy = current.y() - self._last_drag_pos.y()
            self._last_drag_pos = current
            if self._mouse_mode == "local_axis_endpoint":
                self.workbench.local_axis_controller.drag_endpoint(current.x(), current.y())
            elif self._mouse_mode == "pan":
                self.workbench.volume_render_controller.pan_volume_preview(dx, dy)
            else:
                self.workbench.volume_render_controller.rotate_volume_preview(dx, dy)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.RightButton) and self._mouse_mode:
            if self._mouse_mode == "local_axis_endpoint" and self.workbench is not None:
                self.workbench.local_axis_controller.finish_endpoint_drag()
            self._mouse_mode = ""
            self._last_drag_pos = None
            if self.workbench is not None:
                self.workbench.volume_render_controller.finish_volume_interaction_debounced()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self.workbench is None:
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        self.workbench.volume_render_controller.zoom_volume_preview(1 if delta > 0 else -1)
        event.accept()


def create_tif_volume_canvas(parent=None):
    gpu_flag = os.environ.get("TAXAMASK_TIF_GPU_VOLUME_PREVIEW", "").strip().lower()
    if gpu_flag in {"0", "false", "no", "off"}:
        return TifVolumeCanvas(parent), "cpu", "GPU volume preview disabled by TAXAMASK_TIF_GPU_VOLUME_PREVIEW."
    embedded_flag = os.environ.get("TAXAMASK_TIF_EMBEDDED_QOPENGLWIDGET", "").strip().lower()
    if embedded_flag in {"1", "true", "yes", "on"} and gpu_volume_canvas_available() and TifGpuVolumeCanvas is not None:
        try:
            canvas = TifGpuVolumeCanvas(parent)
            canvas.setProperty("tifVolumeRenderer", "gpu-embedded")
            return canvas, "gpu", ""
        except Exception as exc:
            return TifVolumeCanvas(parent), "cpu", str(exc)
    if gpu_volume_offscreen_available() and TifGpuVolumeOffscreenWidget is not None:
        try:
            canvas = TifGpuVolumeOffscreenWidget(parent)
            if hasattr(canvas, "initialize_renderer"):
                canvas.initialize_renderer(emit_info=False)
            canvas.setProperty("tifVolumeRenderer", "gpu-offscreen")
            return canvas, "gpu", ""
        except Exception as exc:
            return TifVolumeCanvas(parent), "cpu", str(exc)
    return TifVolumeCanvas(parent), "cpu", gpu_volume_unavailable_reason()
