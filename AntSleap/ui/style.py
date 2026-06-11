# Scientific Theme System
# Supports both light and dark modes while preserving the release branch's
# stable UI contracts and Windows font-registration behavior.

import os
import sys
from typing import Final, TypedDict

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox, QPushButton, QWidget

BUTTON_ROLE_COMMIT: Final[str] = "commit"
BUTTON_ROLE_RUN: Final[str] = "run"
BUTTON_ROLE_NEUTRAL: Final[str] = "neutral"
BUTTON_ROLE_DESTRUCTIVE: Final[str] = "destructive"
BUTTON_ROLE_STOP: Final[str] = "stop"

DIALOG_ACTION_BUTTON_EXTRAS: Final[str] = "min-width: 104px; min-height: 36px; padding: 8px 18px; font-weight: 700;"

SURFACE_ROLE_PANEL: Final[str] = "panel"
SURFACE_ROLE_SUBTLE: Final[str] = "subtle"
SURFACE_ROLE_RAISED: Final[str] = "raised"
SURFACE_ROLE_TOOLBAR: Final[str] = "toolbar"
SURFACE_ROLE_CANVAS: Final[str] = "canvas"

SKY_500: Final[str] = "#0EA5E9"
SKY_400: Final[str] = "#38BDF8"
SKY_600: Final[str] = "#0284C7"
SKY_300: Final[str] = "#7DD3FC"

_WINDOWS_SCHOLARLY_FONT_FILES: Final[tuple[str, ...]] = (
    r"C:\Windows\Fonts\cambria.ttc",
    r"C:\Windows\Fonts\cambriab.ttf",
    r"C:\Windows\Fonts\cambriai.ttf",
    r"C:\Windows\Fonts\cambriaz.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\simsunb.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
)

_windows_scholarly_fonts_registered = False


def normalize_theme(theme: str | None = "dark") -> str:
    """Public GitHub build currently ships the fully audited dark theme only."""
    return "dark"


class ThemeConfig(TypedDict):
    is_light: bool
    bg_main: str
    bg_surface: str
    bg_surface_alt: str
    bg_panel: str
    bg_input: str
    bg_hover: str
    bg_pressed: str
    text_main: str
    text_soft: str
    text_dim: str
    accent: str
    accent_hover: str
    accent_soft: str
    border: str
    border_strong: str
    selection: str
    success: str
    warning: str
    error: str


def register_windows_scholarly_ui_fonts() -> None:
    global _windows_scholarly_fonts_registered

    if _windows_scholarly_fonts_registered or sys.platform != "win32":
        return

    for font_path in _WINDOWS_SCHOLARLY_FONT_FILES:
        if os.path.exists(font_path):
            _ = QFontDatabase.addApplicationFont(font_path)

    _windows_scholarly_fonts_registered = True


def get_theme_config(theme: str = "dark") -> ThemeConfig:
    theme = normalize_theme(theme)
    is_light = theme.lower() == "light"
    return {
        "is_light": is_light,
        "bg_main": "#F4F7FB" if is_light else "#17191D",
        "bg_surface": "#FBFDFE" if is_light else "#1E2126",
        "bg_surface_alt": "#F6F9FC" if is_light else "#252930",
        "bg_panel": "#EEF3F8" if is_light else "#1A1D22",
        "bg_input": "#FEFFFF" if is_light else "#2A2F37",
        "bg_hover": "#EAF1F8" if is_light else "#30353D",
        "bg_pressed": "#E0EAF5" if is_light else "#2A2F36",
        "text_main": "#122033" if is_light else "#E8ECF1",
        "text_soft": "#31435B" if is_light else "#C7CDD6",
        "text_dim": "#63748A" if is_light else "#959EAA",
        "accent": SKY_500 if is_light else SKY_400,
        "accent_hover": SKY_600 if is_light else SKY_300,
        "accent_soft": "#E6F4FD" if is_light else "#213140",
        "border": "#DCE4EE" if is_light else "#363C45",
        "border_strong": "#C7D3E1" if is_light else "#4A525E",
        "selection": "#DCEFFA" if is_light else "#2C343E",
        "success": "#10B981",
        "warning": "#F59E0B",
        "error": "#EF4444",
    }


def get_button_style_for_theme(role: str, extras: str = "", theme: str = "dark") -> str:
    theme = normalize_theme(theme)
    c = get_theme_config(theme)
    is_light = theme.lower() == "light"

    bg = "#FDFEFF" if is_light else c["bg_surface_alt"]
    border = "#D7E2ED" if is_light else c["border"]
    text = c["text_soft"] if is_light else c["text_main"]
    hover_bg = "#F2F7FB" if is_light else c["bg_hover"]
    pressed_bg = "#E8F0F8" if is_light else c["bg_pressed"]
    hover_border = border
    pressed_border = border

    if role in {BUTTON_ROLE_COMMIT, BUTTON_ROLE_RUN}:
        bg = c["accent"]
        border = c["accent"]
        text = "#FFFFFF"
        hover_bg = c["accent_hover"]
        pressed_bg = c["accent_hover"]
        hover_border = c["accent_hover"]
        pressed_border = c["accent_hover"]
        if not is_light:
            bg = "#5B7486"
            border = "#5B7486"
            hover_bg = "#6A8293"
            pressed_bg = "#4E6677"
            hover_border = "#6A8293"
            pressed_border = "#4E6677"
    elif role == BUTTON_ROLE_DESTRUCTIVE:
        bg = c["error"]
        border = c["error"]
        text = "#FFFFFF"
        hover_bg = "#DC2626"
        pressed_bg = "#B91C1C"
        hover_border = "#DC2626"
        pressed_border = "#B91C1C"
    elif role == BUTTON_ROLE_STOP:
        bg = "#F8FBFE" if is_light else c["bg_surface"]
        border = "#CBD8E5" if is_light else c["border_strong"]
        text = c["text_main"]
        hover_bg = "#EEF4FA" if is_light else c["bg_hover"]
        pressed_bg = "#E4EDF7" if is_light else c["bg_pressed"]
        hover_border = border
        pressed_border = border

    disabled_bg = c["bg_panel"]
    disabled_color = c["text_dim"]
    extra_block = f"\n        {extras.strip()}" if extras and extras.strip() else ""

    return f"""
    QPushButton {{
        background-color: {bg};
        border: 1px solid {border};
        color: {text};
        border-radius: 8px;
        padding: 7px 16px;
        font-weight: 600;{extra_block}
    }}
    QPushButton:hover {{
        background-color: {hover_bg};
        border-color: {hover_border};
    }}
    QPushButton:pressed {{
        background-color: {pressed_bg};
        border-color: {pressed_border};
    }}
    QPushButton:disabled {{
        background-color: {disabled_bg};
        color: {disabled_color};
        border: 1px solid {disabled_bg};
    }}
    """


def semantic_button_style(role: str, extras: str = "") -> str:
    return get_button_style_for_theme(role, extras, "dark")


def _merge_button_extras(base_extras: str = "", extras: str = "") -> str:
    base_clean = str(base_extras or "").strip()
    extras_clean = str(extras or "").strip()
    if base_clean and extras_clean:
        return f"{base_clean} {extras_clean}"
    return base_clean or extras_clean


def apply_theme_button_style(button: QPushButton | None, role: str, extras: str = "", theme: str = "dark") -> None:
    if button is not None:
        button.setStyleSheet(get_button_style_for_theme(role, extras, theme))


def apply_semantic_button_style(button: QPushButton | None, role: str, extras: str = "") -> None:
    if button is not None:
        button.setStyleSheet(semantic_button_style(role, extras))


def apply_theme_dialog_button_box_style(
    button_box: QDialogButtonBox | None,
    *,
    ok_role: str,
    cancel_role: str,
    theme: str = "dark",
    ok_extras: str = "",
    cancel_extras: str = "",
) -> None:
    if button_box is None:
        return

    apply_theme_button_style(
        button_box.button(QDialogButtonBox.StandardButton.Ok),
        ok_role,
        _merge_button_extras(DIALOG_ACTION_BUTTON_EXTRAS, ok_extras),
        theme,
    )
    apply_theme_button_style(
        button_box.button(QDialogButtonBox.StandardButton.Cancel),
        cancel_role,
        _merge_button_extras(DIALOG_ACTION_BUTTON_EXTRAS, cancel_extras),
        theme,
    )


def _resolve_widget_theme(widget: QWidget | None, fallback: str = "dark") -> str:
    current = widget
    while isinstance(current, QWidget):
        theme = getattr(current, "current_theme", None)
        if isinstance(theme, str) and theme.strip():
            return normalize_theme(theme.strip())
        current = current.parentWidget()

    app = QApplication.instance()
    if isinstance(app, QApplication):
        app_theme = app.property("activeTheme")
        if isinstance(app_theme, str) and app_theme.strip():
            return normalize_theme(app_theme.strip())

    return normalize_theme(fallback)


def apply_theme_message_box_button_style(
    message_box: QMessageBox | None,
    *,
    theme: str = "dark",
    role_overrides: dict | None = None,
    extras_overrides: dict | None = None,
) -> None:
    if message_box is None:
        return

    button_roles = {
        QMessageBox.StandardButton.Ok: BUTTON_ROLE_COMMIT,
        QMessageBox.StandardButton.Yes: BUTTON_ROLE_COMMIT,
        QMessageBox.StandardButton.Save: BUTTON_ROLE_COMMIT,
        QMessageBox.StandardButton.Apply: BUTTON_ROLE_COMMIT,
        QMessageBox.StandardButton.Open: BUTTON_ROLE_COMMIT,
        QMessageBox.StandardButton.Cancel: BUTTON_ROLE_STOP,
        QMessageBox.StandardButton.No: BUTTON_ROLE_STOP,
        QMessageBox.StandardButton.Close: BUTTON_ROLE_NEUTRAL,
    }
    button_extras = {}
    if role_overrides:
        button_roles.update(role_overrides)
    if extras_overrides:
        button_extras.update(extras_overrides)

    for standard_button, role in button_roles.items():
        button = message_box.button(standard_button)
        if button is None:
            continue
        apply_theme_button_style(
            button,
            role,
            _merge_button_extras(
                DIALOG_ACTION_BUTTON_EXTRAS,
                str(button_extras.get(standard_button, "") or ""),
            ),
            theme,
        )


def show_themed_message_box(
    parent: QWidget | None,
    *,
    icon,
    title: str,
    text: str,
    buttons,
    default_button=None,
    theme: str | None = None,
    role_overrides: dict | None = None,
    extras_overrides: dict | None = None,
    informative_text: str = "",
    detailed_text: str = "",
):
    message_box = QMessageBox(parent)
    message_box.setIcon(icon)
    message_box.setWindowTitle(title)
    message_box.setText(text)
    message_box.setStandardButtons(buttons)
    if default_button is not None:
        message_box.setDefaultButton(default_button)
    if informative_text:
        message_box.setInformativeText(informative_text)
    if detailed_text:
        message_box.setDetailedText(detailed_text)

    resolved_theme = str(theme or _resolve_widget_theme(parent))
    message_box.setStyleSheet(get_theme_stylesheet(resolved_theme))
    apply_theme_message_box_button_style(
        message_box,
        theme=resolved_theme,
        role_overrides=role_overrides,
        extras_overrides=extras_overrides,
    )
    message_box.exec()
    clicked_button = message_box.clickedButton()
    if clicked_button is None:
        return QMessageBox.StandardButton.NoButton
    return message_box.standardButton(clicked_button)


def themed_yes_no_question(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    confirm_role: str = BUTTON_ROLE_COMMIT,
    cancel_role: str = BUTTON_ROLE_STOP,
    default_button=QMessageBox.StandardButton.No,
    theme: str | None = None,
):
    return show_themed_message_box(
        parent,
        icon=QMessageBox.Icon.Question,
        title=title,
        text=text,
        buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        default_button=default_button,
        theme=theme,
        role_overrides={
            QMessageBox.StandardButton.Yes: confirm_role,
            QMessageBox.StandardButton.No: cancel_role,
        },
    )


def themed_ok_cancel_message(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    icon=QMessageBox.Icon.Information,
    ok_role: str = BUTTON_ROLE_COMMIT,
    cancel_role: str = BUTTON_ROLE_STOP,
    default_button=QMessageBox.StandardButton.Ok,
    theme: str | None = None,
):
    return show_themed_message_box(
        parent,
        icon=icon,
        title=title,
        text=text,
        buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        default_button=default_button,
        theme=theme,
        role_overrides={
            QMessageBox.StandardButton.Ok: ok_role,
            QMessageBox.StandardButton.Cancel: cancel_role,
        },
    )


def apply_surface_role(widget: QWidget | None, role: str, object_name: str | None = None) -> None:
    if widget is None:
        return

    if object_name:
        widget.setObjectName(object_name)
    widget.setProperty("surfaceRole", role)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


COMMON_BASE = """
QMainWindow, QDialog {
    background-color: %BG%;
    color: %TEXT%;
}

QWidget {
    background-color: %BG%;
    font-family: "Cambria", "Microsoft YaHei UI", "Microsoft YaHei", "Source Han Serif SC", "Noto Serif CJK SC", "Songti SC", "SimSun", sans-serif;
    font-size: 11pt;
    color: %TEXT%;
    outline: none;
}

QFrame {
    background-color: transparent;
    color: %TEXT%;
}

QAbstractScrollArea, QAbstractItemView {
    background-color: %SURFACE%;
    color: %TEXT%;
    border: 1px solid %BORDER%;
}

QWidget#workbenchCenterPanel,
QWidget#CenterPanel,
QWidget#startCenterPage {
    background-color: %SURFACE%;
    border: 1px solid %BORDER%;
    border-radius: 14px;
}

QWidget#ModelCard {
    background-color: %SURFACE_ALT%;
    border: 1px solid %BORDER%;
    border-radius: 12px;
}

QMenuBar {
    background-color: %SURFACE%;
    color: %TEXT%;
    border-bottom: 1px solid %BORDER%;
}

QMenuBar::item {
    background-color: transparent;
    padding: 5px 10px;
    color: %TEXT%;
}

QMenuBar::item:selected {
    background-color: %HOVER%;
    border-radius: 4px;
}

QMenu {
    background-color: %SURFACE%;
    border: 1px solid %BORDER_STRONG%;
    color: %TEXT%;
}

QMenu::item {
    padding: 5px 30px;
}

QMenu::item:selected {
    background-color: %SELECTION%;
    color: %ACCENT%;
}

QToolTip {
    background-color: %SURFACE_ALT%;
    color: %TEXT%;
    border: 1px solid %BORDER_STRONG%;
    padding: 4px 6px;
}

QStatusBar {
    background-color: %SURFACE%;
    color: %TEXT_SOFT%;
    border-top: 1px solid %BORDER%;
}

QLabel {
    color: %TEXT%;
    padding: 2px;
}

QLabel#HeaderLabel {
    color: %TEXT_SOFT%;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid %BORDER%;
    padding-bottom: 6px;
    margin-bottom: 8px;
}

QLabel#startCenterTitle {
    color: %TEXT%;
    font-size: 18pt;
    font-weight: 800;
}

QLabel#startWorkflowTitle {
    color: %TEXT%;
    font-size: 15pt;
    font-weight: 800;
}

QLabel#startProjectConsoleTitle {
    color: %TEXT_SOFT%;
    font-weight: 800;
    padding: 0 2px;
}

QLabel#SectionNote,
QLabel#BlinkFormLabel,
QLabel#mutedLabel {
    color: %TEXT_DIM%;
}

QLabel#StatusPill {
    background-color: %ACCENT_SOFT%;
    border: 1px solid %BORDER_STRONG%;
    border-radius: 8px;
    color: %TEXT_MAIN%;
    font-weight: 600;
    padding: 8px 10px;
}

QGroupBox {
    border: 1px solid %BORDER%;
    border-radius: 10px;
    margin-top: 1.3em;
    padding-top: 12px;
    font-weight: bold;
    background-color: %SURFACE%;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 10px;
    color: %ACCENT%;
    font-size: 10.5pt;
}

QWidget[surfaceRole="toolbar"],
QWidget[surfaceRole="panel"],
QWidget[surfaceRole="subtle"],
QWidget[surfaceRole="raised"],
QWidget[surfaceRole="canvas"],
QGroupBox[surfaceRole="panel"],
QGroupBox[surfaceRole="subtle"],
QGroupBox[surfaceRole="raised"] {
    background-color: %SURFACE%;
    border: 1px solid %BORDER%;
    border-radius: 12px;
}

QWidget[surfaceRole="toolbar"] {
    background-color: %PANEL%;
}

QWidget[surfaceRole="subtle"],
QGroupBox[surfaceRole="subtle"] {
    background-color: %SURFACE_ALT%;
}

QWidget[surfaceRole="raised"],
QGroupBox[surfaceRole="raised"] {
    background-color: %SURFACE%;
    border-color: %BORDER_STRONG%;
}

QWidget[surfaceRole="canvas"] {
    background-color: %BG%;
    border-color: %BORDER%;
    border-radius: 14px;
}

QListWidget, QTreeWidget, QTreeView, QTableWidget {
    background-color: %SURFACE%;
    border: 1px solid %BORDER%;
    border-radius: 10px;
    padding: 6px;
    outline: 0;
}

QListWidget::item, QTreeWidget::item, QTreeView::item {
    padding: 8px 12px;
    border-radius: 6px;
    margin: 2px 4px;
}

QListWidget::item:hover, QTreeWidget::item:hover, QTreeView::item:hover {
    background-color: %HOVER%;
}

QListWidget::item:selected, QTreeWidget::item:selected, QTreeView::item:selected {
    background-color: %SELECTION%;
    color: %ACCENT%;
    border-left: 3px solid %ACCENT%;
    font-weight: 700;
}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background-color: %INPUT_BG%;
    border: 1px solid %BORDER%;
    border-radius: 8px;
    padding: 6px 10px;
    color: %TEXT%;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid %ACCENT%;
}

QTextEdit#LinkedDescriptionBox,
QTextEdit#DescriptionBox {
    background-color: %INPUT_BG%;
    border: 1px solid %BORDER%;
    border-radius: 10px;
    color: %TEXT_SOFT%;
    padding: 8px 10px;
}

QTextEdit#MutedLogConsole,
QTextEdit#LogConsole,
QPlainTextEdit#MutedLogConsole {
    background-color: %INPUT_BG%;
    border: 1px solid %BORDER%;
    border-radius: 10px;
    color: %TEXT%;
    padding: 8px 10px;
    font-family: "Consolas", "Courier New", monospace;
}

QComboBox::drop-down,
QSpinBox::up-button,
QSpinBox::down-button {
    border: none;
    width: 18px;
    background: transparent;
}

QComboBox QAbstractItemView {
    background-color: %SURFACE%;
    border: 1px solid %BORDER_STRONG%;
    color: %TEXT%;
    selection-background-color: %SELECTION%;
    selection-color: %ACCENT%;
}

QRadioButton, QCheckBox {
    spacing: 10px;
    color: %TEXT_SOFT%;
    padding: 2px 0;
    min-height: 24px;
}

QRadioButton::indicator {
    width: 20px;
    height: 20px;
    border-radius: 9px;
    border: 2px solid %BORDER_STRONG%;
    background-color: %INPUT_BG%;
}

QRadioButton::indicator:hover {
    border-color: %ACCENT%;
    background-color: %ACCENT_SOFT%;
}

QRadioButton::indicator:checked {
    background-color: %ACCENT%;
    border: 2px solid %ACCENT%;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid %BORDER_STRONG%;
    background-color: %INPUT_BG%;
}

QCheckBox::indicator:hover {
    border-color: %ACCENT%;
    background-color: %ACCENT_SOFT%;
}

QCheckBox::indicator:checked {
    background-color: %ACCENT%;
    border: 2px solid %ACCENT%;
}

QRadioButton#toolChip, QRadioButton#scaleToolRadio {
    background-color: %SURFACE%;
    border: 1px solid %BORDER%;
    border-radius: 10px;
    padding: 8px 14px;
    spacing: 0px;
    font-weight: 600;
    color: %TEXT_SOFT%;
}

QRadioButton#toolChip::indicator, QRadioButton#scaleToolRadio::indicator {
    width: 0px;
    height: 0px;
    margin: 0px;
    padding: 0px;
    border: none;
    background: transparent;
}

QRadioButton#toolChip:hover, QRadioButton#scaleToolRadio:hover {
    background-color: %HOVER%;
    border-color: %BORDER_STRONG%;
    color: %TEXT%;
}

QRadioButton#toolChip:checked, QRadioButton#scaleToolRadio:checked {
    background-color: %ACCENT%;
    border-color: %ACCENT%;
    color: #FFFFFF;
}

QPushButton {
    border-radius: 8px;
}

QProgressBar {
    border: 1px solid %BORDER%;
    border-radius: 7px;
    text-align: center;
    background-color: %PANEL%;
    color: %TEXT_SOFT%;
}

QProgressBar::chunk {
    background-color: %ACCENT%;
    border-radius: 6px;
}

QSlider::groove:horizontal {
    background: %BORDER%;
    height: 6px;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: %ACCENT%;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: %SURFACE%;
    border: 2px solid %ACCENT%;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: %ACCENT_SOFT%;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollArea#workbenchInspectorScroll {
    border: none;
    background-color: transparent;
}

QWidget#workbenchInspectorPanel {
    background-color: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
}

QScrollBar::handle:vertical {
    background: %BORDER_STRONG%;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: %TEXT_DIM%;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
}

QScrollBar::handle:horizontal {
    background: %BORDER_STRONG%;
    border-radius: 4px;
}

QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
    border: none;
}

QHeaderView::section {
    background-color: %SURFACE_ALT%;
    color: %TEXT_SOFT%;
    padding: 6px;
    border: 1px solid %BORDER%;
}

QTableWidget {
    gridline-color: %BORDER%;
    alternate-background-color: %SURFACE_ALT%;
}

QTableWidget::item:selected {
    background-color: %SELECTION%;
    color: %TEXT%;
}

QTabWidget::pane {
    border: 1px solid %BORDER%;
    top: -1px;
    background-color: %BG%;
}

QTabBar::tab {
    background: %SURFACE_ALT%;
    color: %TEXT_DIM%;
    padding: 9px 18px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 6px;
    border: 1px solid transparent;
}

QTabBar::tab:hover {
    background: %HOVER%;
    color: %TEXT_SOFT%;
}

QTabBar::tab:selected {
    background: %SURFACE%;
    color: %ACCENT%;
    border: 1px solid %BORDER%;
    border-bottom: 3px solid %ACCENT%;
    font-weight: bold;
}

QSplitter::handle {
    background-color: %BG%;
}

QSplitter::handle:horizontal {
    width: 10px;
}

QSplitter::handle:vertical {
    height: 8px;
}

QSplitter::handle:hover {
    background-color: %BORDER_STRONG%;
}
"""


def get_theme_stylesheet(theme: str = "dark") -> str:
    theme = normalize_theme(theme)
    config = get_theme_config(theme)
    vars = {
        "%BG%": config["bg_main"],
        "%SURFACE%": config["bg_surface"],
        "%SURFACE_ALT%": config["bg_surface_alt"],
        "%PANEL%": config["bg_panel"],
        "%INPUT_BG%": config["bg_input"],
        "%HOVER%": config["bg_hover"],
        "%TEXT%": config["text_main"],
        "%TEXT_MAIN%": config["text_main"],
        "%TEXT_SOFT%": config["text_soft"],
        "%TEXT_DIM%": config["text_dim"],
        "%ACCENT%": config["accent"],
        "%ACCENT_SOFT%": config["accent_soft"],
        "%BORDER%": config["border"],
        "%BORDER_STRONG%": config["border_strong"],
        "%SELECTION%": config["selection"],
    }
    res = COMMON_BASE
    for k, v in vars.items():
        res = res.replace(k, v)
    return res


def build_theme_palette(theme: str = "dark") -> QPalette:
    c = get_theme_config(theme)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(c["bg_main"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(c["text_main"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(c["bg_surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c["bg_surface_alt"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["bg_surface_alt"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c["text_main"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(c["text_main"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(c["bg_surface"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(c["text_main"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Link, QColor(c["accent"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(c["selection"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(c["text_main"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c["text_dim"]))
    return palette


SCI_THEME = get_theme_stylesheet("dark")
LIGHT_THEME = get_theme_stylesheet("light")


def apply_theme_to_app(theme: str = "dark") -> None:
    theme = normalize_theme(theme)
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return

    app.setProperty("activeTheme", theme)
    app.setPalette(build_theme_palette(theme))
    app.setStyleSheet(get_theme_stylesheet(theme))

    for widget in app.allWidgets():
        theme_setter = getattr(widget, "set_theme", None)
        if callable(theme_setter):
            theme_setter(theme)
