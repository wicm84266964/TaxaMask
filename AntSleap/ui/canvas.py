from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QPolygonF, QBrush, QCursor, QImage
from PySide6.QtCore import Qt, Signal, QPointF, QLineF, QRectF
import math
import copy
import numpy as np
import cv2

class AnnotationCanvas(QWidget):
    # Signals
    polygon_completed = Signal(str, list) 
    magic_wand_clicked = Signal(float, float) 
    magic_box_completed = Signal(float, float, float, float)
    scale_defined = Signal(float)

    def __init__(self):
        super().__init__()
        self.original_pixmap = None 
        self.display_pixmap = None  
        self.polygons = {} 
        self.manual_boxes = {} # part -> [x1, y1, x2, y2]
        self.auto_boxes = {}   # part -> [x1, y1, x2, y2]
        
        # Image Enhancement
        self.brightness = 0
        self.contrast = 1.0
        
        # Undo/Redo Stacks
        self.history = []
        self.redo_stack = []
        
        # State
        self.current_tool_part = None 
        self.temp_points = [] 
        self.is_drawing = False
        
        # Modes
        self.mode = "DRAW" 
        
        # Editing State
        self.hover_vertex = None # (part_name, index)
        self.is_dragging = False
        self.edit_tolerance = 10 
        
        # Eraser State
        self.is_selecting = False
        self.selection_start = QPointF(0, 0)
        self.selection_rect = QRectF()
        
        # Box Prompt State
        self.is_box_prompting = False
        self.box_start = QPointF(0, 0)
        self.box_rect = QRectF()

        # Scale Tool State
        self.is_scaling = False
        self.scale_start = QPointF(0, 0)
        self.scale_end = QPointF(0, 0)

        # View transformations
        self.scale = 1.0
        self.offset = QPointF(0, 0)
        self.last_mouse_pos = QPointF(0, 0)
        self.is_panning = False

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("background-color: #202020;") 

    def load_image(self, path):
        self.original_pixmap = QPixmap(path)
        self.apply_enhancements()
        
        if not self.original_pixmap.isNull():
            self.fit_to_view()
        self.history = []
        self.redo_stack = []
        self.polygons = {}
        self.update()
        self.setFocus()

    def set_enhancements(self, brightness, contrast):
        self.brightness = brightness
        self.contrast = contrast
        self.apply_enhancements()
        self.update()

    def apply_enhancements(self):
        if not self.original_pixmap or self.original_pixmap.isNull():
            self.display_pixmap = None
            return

        if self.brightness == 0 and self.contrast == 1.0:
            self.display_pixmap = self.original_pixmap
            return

        try:
            qimg = self.original_pixmap.toImage()
            qimg = qimg.convertToFormat(QImage.Format_RGBA8888)
            w, h = qimg.width(), qimg.height()
            arr = np.frombuffer(qimg.bits(), dtype=np.uint8).reshape(h, w, 4)
            rgb = arr[:, :, :3]
            enhanced_rgb = cv2.convertScaleAbs(rgb, alpha=self.contrast, beta=self.brightness)
            arr[:, :, :3] = enhanced_rgb
            self.display_pixmap = QPixmap.fromImage(qimg)
        except Exception as e:
            print(f"Enhancement error: {e}")
            self.display_pixmap = self.original_pixmap

    def fit_to_view(self):
        if not self.original_pixmap or self.original_pixmap.isNull() or self.width() == 0 or self.height() == 0:
            return
        w_ratio = self.width() / self.original_pixmap.width()
        h_ratio = self.height() / self.original_pixmap.height()
        self.scale = min(w_ratio, h_ratio) * 0.9 
        disp_w = self.original_pixmap.width() * self.scale
        disp_h = self.original_pixmap.height() * self.scale
        self.offset = QPointF((self.width() - disp_w) / 2, (self.height() - disp_h) / 2)

    def set_polygons(self, polys):
        self.polygons = copy.deepcopy(polys)
        self.temp_points = []
        self.is_drawing = False
        self.hover_vertex = None
        self.update()

    def set_boxes(self, manual=None, auto=None):
        if manual is not None:
            self.manual_boxes = copy.deepcopy(manual)
        if auto is not None:
            self.auto_boxes = copy.deepcopy(auto)
        self.update()

    def save_state(self):
        if len(self.history) > 20: 
            self.history.pop(0)
        self.history.append(copy.deepcopy(self.polygons))
        self.redo_stack.clear()

    def undo(self):
        if not self.history: return
        self.redo_stack.append(copy.deepcopy(self.polygons))
        self.polygons = self.history.pop()
        self.update()
        for part in self.polygons:
            self.polygon_completed.emit(part, self.polygons[part])

    def redo(self):
        if not self.redo_stack: return
        self.history.append(copy.deepcopy(self.polygons))
        self.polygons = self.redo_stack.pop()
        self.update()
        for part in self.polygons:
            self.polygon_completed.emit(part, self.polygons[part])

    def set_active_part(self, part_name):
        self.current_tool_part = part_name
        self.temp_points = []
        self.is_drawing = False
        self.update()
        self.setFocus()
    
    def set_mode(self, mode):
        self.mode = mode
        if mode in ["MAGIC_WAND", "BOX_PROMPT", "SCALE"]:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def image_to_screen(self, img_x, img_y):
        return QPointF(img_x * self.scale + self.offset.x(), img_y * self.scale + self.offset.y())

    def screen_to_image(self, scr_x, scr_y):
        return ((scr_x - self.offset.x()) / self.scale, (scr_y - self.offset.y()) / self.scale)

    def get_vertex_at(self, pos):
        if self.is_drawing: return None 
        
        closest_dist = self.edit_tolerance
        found = None
        
        for part, points in self.polygons.items():
            for i, pt in enumerate(points):
                screen_pt = self.image_to_screen(pt[0], pt[1])
                dist = math.hypot(screen_pt.x() - pos.x(), screen_pt.y() - pos.y())
                if dist < closest_dist:
                    closest_dist = dist
                    found = (part, i)
        return found

    def get_edge_at(self, pos):
        if self.is_drawing: return None
        
        closest_dist = self.edit_tolerance
        found = None
        
        for part, points in self.polygons.items():
            if len(points) < 2: continue
            
            # Check all edges including the closing edge
            for i in range(len(points)):
                p1 = points[i]
                p2 = points[(i + 1) % len(points)]
                
                screen_p1 = self.image_to_screen(p1[0], p1[1])
                screen_p2 = self.image_to_screen(p2[0], p2[1])
                
                line = QLineF(screen_p1, screen_p2)
                
                # Project point onto line
                # Formula: dot(AP, AB) / dot(AB, AB)
                ap = QPointF(pos.x() - screen_p1.x(), pos.y() - screen_p1.y())
                ab = QPointF(screen_p2.x() - screen_p1.x(), screen_p2.y() - screen_p1.y())
                
                ab_len_sq = ab.x()**2 + ab.y()**2
                if ab_len_sq == 0: continue
                
                t = (ap.x() * ab.x() + ap.y() * ab.y()) / ab_len_sq
                
                # Check if projection falls strictly within the segment (0 < t < 1)
                if 0 < t < 1:
                    # Perpendicular distance
                    proj = QPointF(screen_p1.x() + t * ab.x(), screen_p1.y() + t * ab.y())
                    dist = math.hypot(pos.x() - proj.x(), pos.y() - proj.y())
                    
                    if dist < closest_dist:
                        closest_dist = dist
                        # Store (part_name, index_to_insert_after, projected_point_on_image)
                        
                        # Convert projection back to image coords for the new point
                        img_proj = self.screen_to_image(proj.x(), proj.y())
                        found = (part, i + 1, img_proj) 
                        
        return found
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self.display_pixmap: 
            painter.translate(self.offset)
            painter.scale(self.scale, self.scale)
            painter.drawPixmap(0, 0, self.display_pixmap)
            
            painter.resetTransform()
            
            # Draw Finished Polygons
            for part, points in self.polygons.items():
                if not points: continue
                
                screen_poly = QPolygonF()
                for pt in points:
                    screen_poly.append(self.image_to_screen(pt[0], pt[1]))
                
                is_selected = (part == self.current_tool_part)
                fill_color = QColor(0, 255, 0, 50) if is_selected else QColor(255, 255, 0, 30)
                stroke_color = QColor(0, 255, 0) if is_selected else QColor(255, 255, 0)
                
                painter.setPen(Qt.NoPen)
                painter.setBrush(fill_color)
                painter.drawPolygon(screen_poly)
                
                pen = QPen(stroke_color, 2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPolygon(screen_poly)
                
                painter.setBrush(stroke_color)
                for pt in screen_poly:
                    painter.drawEllipse(pt, 3, 3)

                if len(screen_poly) > 0:
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(screen_poly[0], part)
            
            # Draw Manual Boxes (Green Dashed - User Ground Truth)
            for part, box in self.manual_boxes.items():
                if not box or len(box) != 4: continue
                x1, y1, x2, y2 = box
                tl = self.image_to_screen(x1, y1)
                br = self.image_to_screen(x2, y2)
                rect = QRectF(tl, br)
                
                painter.setPen(QPen(QColor(0, 255, 0), 2, Qt.DashLine)) # Green
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect)
                painter.drawText(tl + QPointF(5, 15), f"{part} [Manual]")

            # Draw Auto Boxes (Orange Dashed - AI Prediction)
            for part, box in self.auto_boxes.items():
                if not box or len(box) != 4: continue
                x1, y1, x2, y2 = box
                tl = self.image_to_screen(x1, y1)
                br = self.image_to_screen(x2, y2)
                rect = QRectF(tl, br)
                
                painter.setPen(QPen(QColor(255, 165, 0), 2, Qt.DashDotLine)) # Orange
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect)
                painter.drawText(tl + QPointF(5, -5), f"{part} [Auto]")

            # Draw Highlighted Vertex
            if self.hover_vertex:
                part, idx = self.hover_vertex
                if part in self.polygons and idx < len(self.polygons[part]):
                    pt = self.polygons[part][idx]
                    screen_pt = self.image_to_screen(pt[0], pt[1])
                    painter.setPen(QPen(QColor(255, 255, 255), 2))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(screen_pt, 8, 8) 

            # Draw Current Drawing
            if self.temp_points:
                screen_poly = QPolygonF()
                for pt in self.temp_points:
                    screen_poly.append(self.image_to_screen(pt[0], pt[1]))
                
                pen = QPen(QColor(0, 255, 255), 2, Qt.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPolyline(screen_poly)
                
                if self.underMouse():
                    last_pt = screen_poly[-1]
                    cursor_pos = self.mapFromGlobal(self.cursor().pos())
                    painter.drawLine(last_pt, cursor_pos)

            # Draw Selection Rect
            if self.is_selecting:
                painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.DashLine))
                painter.setBrush(QColor(255, 0, 0, 50))
                painter.drawRect(self.selection_rect)

            # Draw Box Prompt
            if self.is_box_prompting:
                painter.setPen(QPen(QColor(0, 100, 255), 2, Qt.DashLine))
                painter.setBrush(QColor(0, 100, 255, 50))
                painter.drawRect(self.box_rect)

            # Draw Scale Line
            if self.is_scaling:
                painter.setPen(QPen(QColor(255, 0, 255), 2))
                painter.drawLine(self.scale_start, self.scale_end)
                painter.setBrush(QColor(255, 0, 255))
                painter.drawEllipse(self.scale_start, 4, 4)
                painter.drawEllipse(self.scale_end, 4, 4)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            # Delete Vertex
            hit = self.get_vertex_at(event.position())
            if hit:
                self.save_state()
                part, idx = hit
                if part in self.polygons:
                    self.polygons[part].pop(idx)
                    self.polygon_completed.emit(part, self.polygons[part])
                    self.hover_vertex = None 
                    self.update()
                return 

            # Pan
            self.is_panning = True
            self.last_mouse_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            
        elif event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ShiftModifier:
                self.is_selecting = True
                self.selection_start = event.position()
                self.selection_rect = QRectF(self.selection_start, self.selection_start)
                self.update()
                return
            
            # --- 1. Edge Insertion (Alt + Click) ---
            if event.modifiers() & Qt.AltModifier:
                edge_hit = self.get_edge_at(event.position())
                if edge_hit:
                    self.save_state()
                    part, idx, new_pt = edge_hit
                    # Insert the new point
                    self.polygons[part].insert(idx, list(new_pt))
                    
                    # Immediately start dragging this new point
                    self.is_dragging = True
                    self.hover_vertex = (part, idx)
                    self.current_tool_part = part
                    self.update()
                    return

            if self.mode == "BOX_PROMPT":
                self.is_box_prompting = True
                self.box_start = event.position()
                self.box_rect = QRectF(self.box_start, self.box_start)
                self.update()
                return

            if self.mode == "SCALE":
                self.is_scaling = True
                self.scale_start = event.position()
                self.scale_end = event.position()
                self.update()
                return

            hit = self.get_vertex_at(event.position())
            if hit:
                self.save_state()
                self.is_dragging = True
                self.hover_vertex = hit
                self.current_tool_part = hit[0] 
                return

            if self.original_pixmap and self.current_tool_part:
                img_x, img_y = self.screen_to_image(event.position().x(), event.position().y())
                
                if 0 <= img_x <= self.original_pixmap.width() and 0 <= img_y <= self.original_pixmap.height():
                    
                    if self.mode == "MAGIC_WAND":
                        self.save_state()
                        self.magic_wand_clicked.emit(img_x, img_y)
                    else:
                        self.temp_points.append([img_x, img_y])
                        self.is_drawing = True
                        self.update()

    def mouseMoveEvent(self, event):
        if self.is_panning:
            delta = event.position() - self.last_mouse_pos
            self.offset += delta
            self.last_mouse_pos = event.position()
            self.update()
            return
        
        if self.is_selecting:
            curr_pos = event.position()
            self.selection_rect = QRectF(self.selection_start, curr_pos).normalized()
            self.update()
            return

        if self.is_box_prompting:
            curr_pos = event.position()
            self.box_rect = QRectF(self.box_start, curr_pos).normalized()
            self.update()
            return

        if self.is_scaling:
            self.scale_end = event.position()
            self.update()
            return

        if self.is_dragging and self.hover_vertex:
            part, idx = self.hover_vertex
            img_x, img_y = self.screen_to_image(event.position().x(), event.position().y())
            if self.original_pixmap:
                 img_x = max(0, min(img_x, self.original_pixmap.width()))
                 img_y = max(0, min(img_y, self.original_pixmap.height()))
            self.polygons[part][idx] = [img_x, img_y]
            self.update()
            return

        if not self.is_drawing and not self.is_box_prompting:
            hit = self.get_vertex_at(event.position())
            edge_hit = None
            if not hit and (event.modifiers() & Qt.AltModifier):
                edge_hit = self.get_edge_at(event.position())

            if hit != self.hover_vertex:
                self.hover_vertex = hit
                self.update()
            
            # Cursor Logic
            if hit or edge_hit or self.mode in ["MAGIC_WAND", "BOX_PROMPT", "SCALE"]:
                self.setCursor(Qt.CrossCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        
        if self.is_drawing:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self.is_panning = False
            self.setCursor(Qt.ArrowCursor)
        elif event.button() == Qt.LeftButton:
            if self.is_selecting:
                self.save_state()
                self.is_selecting = False
                changed_parts = set()
                
                for part, points in self.polygons.items():
                    new_points = []
                    for pt in points:
                        screen_pt = self.image_to_screen(pt[0], pt[1])
                        if not self.selection_rect.contains(screen_pt):
                            new_points.append(pt)
                        else:
                            changed_parts.add(part)
                    self.polygons[part] = new_points
                
                self.update()
                for part in changed_parts:
                    self.polygon_completed.emit(part, self.polygons[part])
                return

            if self.is_box_prompting:
                self.is_box_prompting = False
                self.update()
                tl = self.box_rect.topLeft()
                br = self.box_rect.bottomRight()
                x1, y1 = self.screen_to_image(tl.x(), tl.y())
                x2, y2 = self.screen_to_image(br.x(), br.y())
                
                # Clamp to image bounds
                if self.original_pixmap:
                    w = self.original_pixmap.width()
                    h = self.original_pixmap.height()
                    x1 = max(0, min(x1, w))
                    y1 = max(0, min(y1, h))
                    x2 = max(0, min(x2, w))
                    y2 = max(0, min(y2, h))
                
                if abs(x2-x1) > 2 and abs(y2-y1) > 2:
                    self.save_state()
                    self.magic_box_completed.emit(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))
                return

            if self.is_scaling:
                self.is_scaling = False
                self.update()
                x1, y1 = self.screen_to_image(self.scale_start.x(), self.scale_start.y())
                x2, y2 = self.screen_to_image(self.scale_end.x(), self.scale_end.y())
                length = math.hypot(x2 - x1, y2 - y1)
                if length > 2:
                    self.scale_defined.emit(length)
                return

            if self.is_dragging:
                self.is_dragging = False
                if self.hover_vertex:
                    part, _ = self.hover_vertex
                    self.polygon_completed.emit(part, self.polygons[part])

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_drawing and len(self.temp_points) > 2:
            self.save_state()
            self.polygons[self.current_tool_part] = self.temp_points
            self.polygon_completed.emit(self.current_tool_part, self.temp_points)
            self.temp_points = []
            self.is_drawing = False
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.is_drawing:
                self.temp_points = []
                self.is_drawing = False
                self.update()
        elif event.key() == Qt.Key_Backspace and self.is_drawing:
            if self.temp_points:
                self.temp_points.pop()
                if not self.temp_points:
                    self.is_drawing = False
                self.update()
        elif event.key() == Qt.Key_Delete:
            if self.current_tool_part and self.current_tool_part in self.polygons:
                self.save_state()
                del self.polygons[self.current_tool_part]
                self.polygon_completed.emit(self.current_tool_part, [])
                self.update()
    
    def wheelEvent(self, event):
        if not self.original_pixmap: return
        zoom_in = event.angleDelta().y() > 0
        factor = 1.1 if zoom_in else 0.9
        old_pos = self.screen_to_image(event.position().x(), event.position().y())
        self.scale *= factor
        new_screen_x = old_pos[0] * self.scale + self.offset.x()
        new_screen_y = old_pos[1] * self.scale + self.offset.y()
        self.offset.setX(self.offset.x() + (event.position().x() - new_screen_x))
        self.offset.setY(self.offset.y() + (event.position().y() - new_screen_y))
        self.update()
