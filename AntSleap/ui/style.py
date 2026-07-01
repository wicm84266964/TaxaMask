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

THEME_DARK: Final[str] = "dark"
THEME_LIGHT: Final[str] = "light"

NEON_BLUE: Final[str] = "#6F8FB8"
NEON_BLUE_HOVER: Final[str] = "#89A7CC"
NEON_PURPLE: Final[str] = "#75849D"
NEON_CYAN_GREEN: Final[str] = "#4F9C94"
NEON_GOLD: Final[str] = "#C89A43"

LIGHT_BLUE: Final[str] = "#0EA5E9"
LIGHT_BLUE_HOVER: Final[str] = "#0284C7"

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
    clean = str(theme or THEME_DARK).strip().lower()
    if clean in {"light", "lite", "bright"}:
        return THEME_LIGHT
    return THEME_DARK


class ThemeConfig(TypedDict):
    is_light: bool
    bg_main: str
    bg_main_gradient: str
    bg_surface: str
    bg_surface_gradient: str
    bg_surface_alt: str
    bg_surface_alt_gradient: str
    bg_panel: str
    bg_panel_gradient: str
    bg_input: str
    bg_input_gradient: str
    bg_hover: str
    bg_hover_gradient: str
    bg_pressed: str
    text_main: str
    text_soft: str
    text_dim: str
    accent: str
    accent_hover: str
    accent_soft: str
    accent_soft_gradient: str
    border: str
    border_strong: str
    glow_border: str
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
    is_light = theme == THEME_LIGHT
    return {
        "is_light": is_light,
        "bg_main": "#F5F8FC" if is_light else "#070D1A",
        "bg_main_gradient": (
            "#F5F8FC"
            if is_light
            else "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #17263B, stop:0.38 #101B2D, stop:0.54 rgba(156, 173, 198, 26), stop:0.68 #0D1829, stop:1 #070D1A)"
        ),
        "bg_surface": "#FFFFFF" if is_light else "#101A2B",
        "bg_surface_gradient": (
            "#FFFFFF"
            if is_light
            else "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #203350, stop:0.32 #182840, stop:0.54 rgba(166, 181, 204, 34), stop:0.66 #142238, stop:1 #0A1220)"
        ),
        "bg_surface_alt": "#F1F6FB" if is_light else "#15243A",
        "bg_surface_alt_gradient": (
            "#F1F6FB"
            if is_light
            else "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #253B5B, stop:0.36 #1B2C46, stop:0.56 rgba(158, 176, 202, 30), stop:0.70 #14233A, stop:1 #0D1627)"
        ),
        "bg_panel": "#EAF1F8" if is_light else "#0A1220",
        "bg_panel_gradient": (
            "#EAF1F8"
            if is_light
            else "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #17263C, stop:0.52 #0D182A, stop:0.70 rgba(124, 146, 178, 22), stop:1 #07101B)"
        ),
        "bg_input": "#FCFEFF" if is_light else "#101C2E",
        "bg_input_gradient": (
            "#FCFEFF"
            if is_light
            else "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1B2D47, stop:0.46 #132239, stop:0.76 rgba(126, 148, 180, 18), stop:1 #0B1424)"
        ),
        "bg_hover": "#E6F0F8" if is_light else "#1E314D",
        "bg_hover_gradient": (
            "#E6F0F8"
            if is_light
            else "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2B4568, stop:0.46 #1D334F, stop:0.66 rgba(165, 183, 208, 28), stop:1 #142238)"
        ),
        "bg_pressed": "#DCE9F4" if is_light else "#101A2C",
        "text_main": "#102033" if is_light else "#F4F8FF",
        "text_soft": "#30445F" if is_light else "#C8D7EA",
        "text_dim": "#677A92" if is_light else "#8496B3",
        "accent": LIGHT_BLUE if is_light else NEON_BLUE,
        "accent_hover": LIGHT_BLUE_HOVER if is_light else NEON_BLUE_HOVER,
        "accent_soft": "#E3F4FC" if is_light else "#142A45",
        "accent_soft_gradient": (
            "#E3F4FC"
            if is_light
            else "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(111, 143, 184, 42), stop:0.50 rgba(166, 181, 204, 22), stop:1 rgba(75, 96, 128, 24))"
        ),
        "border": "#D7E2EC" if is_light else "#2F4565",
        "border_strong": "#B9CADB" if is_light else "#5C7498",
        "glow_border": "#B9CADB" if is_light else NEON_BLUE,
        "selection": "#DCEFFA" if is_light else "#1A3153",
        "success": "#059669" if is_light else NEON_CYAN_GREEN,
        "warning": "#B7791F" if is_light else "#A88948",
        "error": "#DC2626" if is_light else "#F87171",
    }


def get_button_style_for_theme(role: str, extras: str = "", theme: str = "dark") -> str:
    theme = normalize_theme(theme)
    c = get_theme_config(theme)
    is_light = theme == THEME_LIGHT

    bg = "#FDFEFF" if is_light else c["bg_surface_alt_gradient"]
    bg_property = "background-color" if is_light else "background"
    border = "#D4DFEA" if is_light else c["border"]
    text = c["text_soft"] if is_light else c["text_main"]
    hover_bg = "#F2F7FB" if is_light else c["bg_hover_gradient"]
    hover_bg_property = "background-color" if is_light else "background"
    pressed_bg = "#E8F0F8" if is_light else c["bg_pressed"]
    pressed_bg_property = "background-color"
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
            bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6F8FB8, stop:0.42 #405F88, stop:1 #223B64)"
            bg_property = "background"
            border = "#7898BE"
            hover_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #89A7CC, stop:0.48 #4F709A, stop:1 #2A4775)"
            hover_bg_property = "background"
            pressed_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #344F78, stop:0.55 #243C63, stop:1 #1B2E4E)"
            pressed_bg_property = "background"
            hover_border = NEON_BLUE_HOVER
            pressed_border = NEON_PURPLE
    elif role == BUTTON_ROLE_DESTRUCTIVE:
        bg = c["error"]
        bg_property = "background-color"
        border = c["error"]
        text = "#FFFFFF"
        hover_bg = "#DC2626"
        hover_bg_property = "background-color"
        pressed_bg = "#B91C1C"
        pressed_bg_property = "background-color"
        hover_border = "#DC2626"
        pressed_border = "#B91C1C"
    elif role == BUTTON_ROLE_STOP:
        bg = "#F8FBFE" if is_light else c["bg_panel_gradient"]
        bg_property = "background-color" if is_light else "background"
        border = "#CBD8E5" if is_light else c["border_strong"]
        text = c["text_main"]
        hover_bg = "#EEF4FA" if is_light else c["bg_hover_gradient"]
        hover_bg_property = "background-color" if is_light else "background"
        pressed_bg = "#E4EDF7" if is_light else c["bg_pressed"]
        pressed_bg_property = "background-color"
        hover_border = border
        pressed_border = border

    disabled_bg = c["bg_panel"]
    disabled_color = c["text_dim"]
    extra_block = f"\n        {extras.strip()}" if extras and extras.strip() else ""

    return f"""
    QPushButton {{
        {bg_property}: {bg};
        border: 1px solid {border};
        color: {text};
        border-radius: 8px;
        padding: 7px 16px;
        font-weight: 600;{extra_block}
    }}
    QPushButton:hover {{
        {hover_bg_property}: {hover_bg};
        border-color: {hover_border};
    }}
    QPushButton:pressed {{
        {pressed_bg_property}: {pressed_bg};
        border-color: {pressed_border};
    }}
    QPushButton:disabled {{
        background-color: {disabled_bg};
        color: {disabled_color};
        border: 1px solid {disabled_bg};
    }}
    """


def semantic_button_style(role: str, extras: str = "") -> str:
    return get_button_style_for_theme(role, extras, _resolve_widget_theme(None))


def _merge_button_extras(base_extras: str = "", extras: str = "") -> str:
    base_clean = str(base_extras or "").strip()
    extras_clean = str(extras or "").strip()
    if base_clean and extras_clean:
        return f"{base_clean} {extras_clean}"
    return base_clean or extras_clean


def apply_theme_button_style(button: QPushButton | None, role: str, extras: str = "", theme: str = "dark") -> None:
    if button is not None:
        button.setProperty("themeButtonRole", role)
        button.setProperty("themeButtonExtras", str(extras or ""))
        button.setStyleSheet(get_button_style_for_theme(role, extras, theme))


def apply_semantic_button_style(button: QPushButton | None, role: str, extras: str = "") -> None:
    if button is not None:
        apply_theme_button_style(button, role, extras, _resolve_widget_theme(button))


def refresh_themed_buttons(root: QWidget | QApplication | None = None, theme: str = "dark") -> None:
    theme = normalize_theme(theme)
    if root is None:
        root = QApplication.instance()
    if root is None:
        return
    if isinstance(root, QApplication):
        buttons = root.allWidgets()
    else:
        buttons = [root, *root.findChildren(QWidget)]
    for widget in buttons:
        if not isinstance(widget, QPushButton):
            continue
        role = widget.property("themeButtonRole")
        if not isinstance(role, str) or not role:
            continue
        extras = widget.property("themeButtonExtras")
        apply_theme_button_style(widget, role, str(extras or ""), theme)


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
    background: %BG_GRADIENT%;
    color: %TEXT%;
}

QWidget#startCenterPage,
QWidget#startCenterAgentMain,
QWidget#startCenterWorkflowRail,
QWidget#workbenchPage,
QWidget#pdfEvidencePage,
QWidget#blinkLabPage {
    background: %BG_GRADIENT%;
    color: %TEXT%;
}

QWidget {
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
    background: %BG_GRADIENT%;
    border: 1px solid %BORDER%;
    border-radius: 14px;
}

QWidget#ModelCard {
    background: %SURFACE_ALT_GRADIENT%;
    border: 1px solid %BORDER_STRONG%;
    border-radius: 12px;
}

QMenuBar {
    background: %SURFACE_GRADIENT%;
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
    background: %SURFACE_GRADIENT%;
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
    background: %SURFACE_ALT_GRADIENT%;
    color: %TEXT%;
    border: 1px solid %BORDER_STRONG%;
    padding: 4px 6px;
}

QStatusBar {
    background: %SURFACE_GRADIENT%;
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
    background: %ACCENT_SOFT_GRADIENT%;
    border: 1px solid %GLOW_BORDER%;
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
    background: %SURFACE_GRADIENT%;
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
    background: %SURFACE_GRADIENT%;
    border: 1px solid %BORDER%;
    border-radius: 12px;
}

QWidget[surfaceRole="panel"],
QGroupBox[surfaceRole="panel"] {
    background: %SURFACE_GRADIENT%;
    border-color: %BORDER_STRONG%;
}

QWidget[surfaceRole="toolbar"] {
    background: %PANEL_GRADIENT%;
}

QWidget[surfaceRole="subtle"],
QGroupBox[surfaceRole="subtle"] {
    background: %SURFACE_ALT_GRADIENT%;
}

QWidget[surfaceRole="raised"],
QGroupBox[surfaceRole="raised"] {
    background: %SURFACE_GRADIENT%;
    border-color: %GLOW_BORDER%;
}

QWidget[surfaceRole="canvas"] {
    background: %BG_GRADIENT%;
    border-color: %BORDER%;
    border-radius: 14px;
}

QListWidget, QTreeWidget, QTreeView, QTableWidget {
    background: %SURFACE_GRADIENT%;
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
    background: %HOVER_GRADIENT%;
}

QListWidget::item:selected, QTreeWidget::item:selected, QTreeView::item:selected {
    background: %ACCENT_SOFT_GRADIENT%;
    color: %ACCENT%;
    border-left: 3px solid %ACCENT%;
    font-weight: 700;
}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: %INPUT_GRADIENT%;
    border: 1px solid %BORDER%;
    border-radius: 8px;
    padding: 6px 10px;
    color: %TEXT%;
    selection-background-color: %SELECTION%;
    selection-color: %TEXT%;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid %ACCENT%;
}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background-color: %PANEL%;
    border: 1px solid %BORDER%;
    color: %TEXT_DIM%;
}

QTextEdit#LinkedDescriptionBox,
QTextEdit#DescriptionBox {
    background: %INPUT_GRADIENT%;
    border: 1px solid %BORDER%;
    border-radius: 10px;
    color: %TEXT_SOFT%;
    padding: 8px 10px;
}

QTextEdit#MutedLogConsole,
QTextEdit#LogConsole,
QPlainTextEdit#MutedLogConsole {
    background: %INPUT_GRADIENT%;
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
    background: %SURFACE_GRADIENT%;
    border: 1px solid %BORDER_STRONG%;
    color: %TEXT%;
    selection-background-color: %SELECTION%;
    selection-color: %ACCENT%;
}

QComboBox::item:selected {
    background-color: %SELECTION%;
    color: %ACCENT%;
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
    background: %SURFACE_GRADIENT%;
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
    background: %HOVER_GRADIENT%;
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
    background: %PANEL_GRADIENT%;
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
    background: %SURFACE_ALT_GRADIENT%;
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
    background: %BG_GRADIENT%;
}

QTabBar::tab {
    background: %SURFACE_ALT_GRADIENT%;
    color: %TEXT_DIM%;
    padding: 9px 18px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 6px;
    border: 1px solid transparent;
}

QTabBar::tab:hover {
    background: %HOVER_GRADIENT%;
    color: %TEXT_SOFT%;
}

QTabBar::tab:selected {
    background: %SURFACE_GRADIENT%;
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
        "%BG_GRADIENT%": config["bg_main_gradient"],
        "%SURFACE%": config["bg_surface"],
        "%SURFACE_GRADIENT%": config["bg_surface_gradient"],
        "%SURFACE_ALT%": config["bg_surface_alt"],
        "%SURFACE_ALT_GRADIENT%": config["bg_surface_alt_gradient"],
        "%PANEL%": config["bg_panel"],
        "%PANEL_GRADIENT%": config["bg_panel_gradient"],
        "%INPUT_BG%": config["bg_input"],
        "%INPUT_GRADIENT%": config["bg_input_gradient"],
        "%HOVER%": config["bg_hover"],
        "%HOVER_GRADIENT%": config["bg_hover_gradient"],
        "%TEXT%": config["text_main"],
        "%TEXT_MAIN%": config["text_main"],
        "%TEXT_SOFT%": config["text_soft"],
        "%TEXT_DIM%": config["text_dim"],
        "%ACCENT%": config["accent"],
        "%ACCENT_SOFT%": config["accent_soft"],
        "%ACCENT_SOFT_GRADIENT%": config["accent_soft_gradient"],
        "%BORDER%": config["border"],
        "%BORDER_STRONG%": config["border_strong"],
        "%GLOW_BORDER%": config["glow_border"],
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
    refresh_themed_buttons(app, theme)
