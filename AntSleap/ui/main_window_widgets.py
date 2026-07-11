from __future__ import annotations

import json

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QListWidget, QSlider, QSpinBox


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()


class ImageGroupListWidget(QListWidget):
    imagesDroppedToGroup = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    def startDrag(self, _supported_actions):
        paths = [item.data(Qt.UserRole) for item in self.selectedItems() if item and item.data(Qt.UserRole)]
        if not paths:
            return
        mime = QMimeData()
        mime.setData("application/x-taxamask-image-paths", json.dumps(paths).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-taxamask-image-paths"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-taxamask-image-paths"):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasFormat("application/x-taxamask-image-paths"):
            super().dropEvent(event)
            return
        target_item = self.itemAt(event.position().toPoint())
        if target_item is None:
            return
        group_key = target_item.data(Qt.UserRole + 1) or target_item.data(Qt.UserRole + 2)
        if not group_key:
            return
        try:
            paths = json.loads(bytes(event.mimeData().data("application/x-taxamask-image-paths")).decode("utf-8"))
        except Exception:
            paths = []
        paths = [str(path) for path in paths if str(path or "").strip()]
        if not paths:
            return
        self.imagesDroppedToGroup.emit(paths, str(group_key))
        event.acceptProposedAction()
