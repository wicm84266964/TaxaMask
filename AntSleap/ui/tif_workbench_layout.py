from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def make_panel(title, object_name, title_registry=None):
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
    if title_registry is not None:
        title_registry[object_name] = (title, title_label)
    return panel, layout


def make_section(title, object_name, title_registry=None):
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
    if title_registry is not None:
        title_registry[object_name] = (title, title_label)
    return section, layout


def relax_right_sidebar_widget_width(widget):
    if widget is None:
        return
    current_policy = widget.sizePolicy()
    vertical_policy = current_policy.verticalPolicy()
    if isinstance(widget, QLabel):
        if widget.wordWrap():
            widget.setSizePolicy(QSizePolicy.Ignored, vertical_policy)
        return
    if isinstance(widget, (QPushButton, QCheckBox, QRadioButton)):
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Ignored, vertical_policy)
        text = ""
        try:
            text = str(widget.text() or "")
        except Exception:
            text = ""
        if text and not widget.toolTip():
            widget.setToolTip(text)
        return
    if isinstance(widget, QComboBox):
        widget.setMinimumWidth(0)
        try:
            widget.setMinimumContentsLength(0)
            widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        except Exception:
            pass
        widget.setSizePolicy(QSizePolicy.Ignored, vertical_policy)
        return
    if isinstance(widget, (QLineEdit, QProgressBar)):
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Ignored, vertical_policy)
        return
    if isinstance(widget, (QTableWidget, QTextEdit)):
        widget.setMinimumWidth(0)
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        widget.setSizePolicy(QSizePolicy.Ignored, vertical_policy)


def make_right_sidebar_responsive(right_panel, pages):
    right_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
    right_panel.setMinimumWidth(360)
    right_panel.setMaximumWidth(520)
    for page in pages:
        page.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        body = page.widget()
        if body is not None:
            body.setMinimumWidth(0)
            body.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    for section in right_panel.findChildren(QFrame):
        if str(section.objectName() or "").startswith("tif"):
            section.setMinimumWidth(0)
            section.setSizePolicy(QSizePolicy.Ignored, section.sizePolicy().verticalPolicy())
    for widget in right_panel.findChildren(QWidget):
        relax_right_sidebar_widget_width(widget)


def make_task_page(object_name):
    scroll = QScrollArea()
    scroll.setObjectName("tifInspectorScroll")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setFrameShape(QFrame.NoFrame)
    body = QWidget()
    body.setObjectName(object_name)
    body.setMinimumWidth(0)
    body.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    layout = QVBoxLayout(body)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    scroll.setWidget(body)
    return scroll, layout
