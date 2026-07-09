from __future__ import annotations

try:
    from AntSleap.ui.style import get_theme_config, normalize_theme
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from ui.style import get_theme_config, normalize_theme


def tif_canvas_background(theme="dark"):
    theme = normalize_theme(theme)
    return "#111A2B" if theme == "light" else "#07101D"


def tif_workbench_theme(theme="dark"):
    c = get_theme_config(theme)
    is_light = bool(c["is_light"])
    canvas_bg = tif_canvas_background(theme)
    return {
        "root": c["bg_main"],
        "panel": c["bg_surface"],
        "panel_alt": c["bg_surface_alt"],
        "section": c["bg_surface_alt"] if is_light else c["bg_panel"],
        "canvas_shell": "#DCE6F0" if is_light else "#0B1424",
        "canvas": canvas_bg,
        "input": c["bg_input"],
        "table_alt": "#EDF3F8" if is_light else "#122039",
        "button": "#F8FBFE" if is_light else "#17263C",
        "button_hover": "#EEF4FA" if is_light else "#213854",
        "button_pressed": "#E4EDF7" if is_light else "#101B2E",
        "button_disabled": c["bg_panel"],
        "primary": c["accent"],
        "primary_hover": c["accent_hover"],
        "primary_pressed": "#0369A1" if is_light else "#405F88",
        "secondary_checked": "#DCEFFA" if is_light else "#243D63",
        "danger": "#FDE8E8" if is_light else "#3B2528",
        "danger_hover": "#FBD5D5" if is_light else "#512D33",
        "danger_pressed": "#F8B4B4" if is_light else "#2D1C20",
        "danger_border": "#F87171" if is_light else "#8D4B55",
        "danger_text": "#991B1B" if is_light else "#FFE9EC",
        "text": c["text_main"],
        "text_soft": c["text_soft"],
        "text_dim": c["text_dim"],
        "canvas_text": "#C8D7EA",
        "border": c["border"],
        "border_strong": c["border_strong"],
        "glow_border": c["glow_border"],
        "scrollbar_track": "#EEF4FA" if is_light else "#0B1424",
        "scrollbar_thumb": c["border_strong"],
        "scrollbar_thumb_hover": "#9FB4C8" if is_light else c["text_dim"],
        "selection": c["selection"],
        "selection_text": c["text_main"],
        "accent": c["accent"],
        "success": c["success"],
        "warning": c["warning"],
        "error": c["error"],
    }


TIF_WORKBENCH_STYLESHEET_TEMPLATE = """
            QWidget#tifWorkbenchRoot {
                background: {t['root']};
            }
            QFrame#tifSpecimenPanel,
            QFrame#tifVolumePanel,
            QFrame#tifControlPanel,
            QFrame#tifWorkbenchTopBar {
                background: {t['panel']};
                border: 1px solid {t['border']};
                border-radius: 12px;
            }
            QLabel#tifTopContextLabel {
                color: {t['text']};
                font-weight: 700;
                border: none;
            }
            QFrame#tifImportSection,
            QFrame#tifPartExtractionSection,
            QFrame#tifSliceDisplaySection,
            QFrame#tifVolumeRenderSection,
            QFrame#tifLocalAxisVolumeSection,
            QFrame#tifOperationStatusSection,
            QFrame#tifAnnotationSection,
            QFrame#tifMaterialSection,
            QFrame#tifLabelSchemaSection,
            QFrame#tifTrainingSection,
            QFrame#tifPartUserTagsSection,
            QFrame#tifTrainingResultSection,
            QFrame#tifBackendSection,
            QFrame#tifStatusSection,
            QFrame#tifLogSection {
                background: {t['section']};
                border: 1px solid {t['border']};
                border-radius: 12px;
            }
            QWidget#tifInspectorBody {
                background: transparent;
            }
            QScrollArea#tifInspectorScroll {
                background: transparent;
                border: none;
            }
            QScrollArea#tifInspectorScroll QScrollBar:vertical,
            QTextEdit#tifLogConsole QScrollBar:vertical {
                background: {t['scrollbar_track']};
                border: none;
                border-radius: 5px;
                margin: 0px;
                width: 10px;
            }
            QScrollArea#tifInspectorScroll QScrollBar::handle:vertical,
            QTextEdit#tifLogConsole QScrollBar::handle:vertical {
                background: {t['scrollbar_thumb']};
                border: 2px solid {t['scrollbar_track']};
                border-radius: 5px;
                min-height: 22px;
            }
            QScrollArea#tifInspectorScroll QScrollBar::handle:vertical:hover,
            QTextEdit#tifLogConsole QScrollBar::handle:vertical:hover {
                background: {t['scrollbar_thumb_hover']};
            }
            QScrollArea#tifInspectorScroll QScrollBar:horizontal,
            QTextEdit#tifLogConsole QScrollBar:horizontal {
                background: {t['scrollbar_track']};
                border: none;
                border-radius: 5px;
                height: 10px;
                margin: 0px;
            }
            QScrollArea#tifInspectorScroll QScrollBar::handle:horizontal,
            QTextEdit#tifLogConsole QScrollBar::handle:horizontal {
                background: {t['scrollbar_thumb']};
                border: 2px solid {t['scrollbar_track']};
                border-radius: 5px;
                min-width: 22px;
            }
            QScrollArea#tifInspectorScroll QScrollBar::handle:horizontal:hover,
            QTextEdit#tifLogConsole QScrollBar::handle:horizontal:hover {
                background: {t['scrollbar_thumb_hover']};
            }
            QScrollArea#tifInspectorScroll QScrollBar::add-line,
            QScrollArea#tifInspectorScroll QScrollBar::sub-line,
            QScrollArea#tifInspectorScroll QScrollBar::add-page,
            QScrollArea#tifInspectorScroll QScrollBar::sub-page,
            QTextEdit#tifLogConsole QScrollBar::add-line,
            QTextEdit#tifLogConsole QScrollBar::sub-line,
            QTextEdit#tifLogConsole QScrollBar::add-page,
            QTextEdit#tifLogConsole QScrollBar::sub-page {
                background: transparent;
                border: none;
            }
            QLabel#tifPanelTitle {
                color: {t['text']};
                font-weight: 700;
                padding-bottom: 4px;
                border: none;
            }
            QLabel#tifSectionTitle {
                color: {t['text_soft']};
                font-weight: 700;
                margin-top: 8px;
                border: none;
            }
            QFrame#tifCanvasShell {
                background: {t['canvas_shell']};
                border: 1px solid {t['border_strong']};
                border-radius: 12px;
            }
            QLabel#tifSliceCanvas {
                background: {t['canvas']};
                color: {t['canvas_text']};
                border: none;
                border-radius: 10px;
            }
            #tifVolumeCanvas {
                background: {t['canvas']};
                color: {t['canvas_text']};
                border: none;
                border-radius: 10px;
            }
            QLabel#tifVolumeRenderStatus {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QLabel#tifLocalAxisStatusText {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QLabel#tifOperationStatusText {
                background: {t['input']};
                color: {t['text']};
                border: 1px solid {t['border_strong']};
                border-radius: 8px;
                padding: 7px 9px;
            }
            QFrame#tifSliceBar {
                background: {t['panel_alt']};
                border: 1px solid {t['border']};
                border-radius: 12px;
            }
            QTreeWidget#tifSpecimenList,
            QTableWidget#tifMaterialTable,
            QTableWidget#tifPredictTargetsTable,
            QTableWidget#tifTrainingResultMetricsTable,
            QTableWidget#tifTrainingResultArtifactTable {
                background: {t['input']};
                alternate-background-color: {t['table_alt']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                padding: 2px;
                selection-background-color: {t['selection']};
                selection-color: {t['selection_text']};
            }
            QTableWidget#tifMaterialTable::item,
            QTableWidget#tifPredictTargetsTable::item,
            QTableWidget#tifTrainingResultMetricsTable::item,
            QTableWidget#tifTrainingResultArtifactTable::item,
            QTreeWidget#tifSpecimenList::item {
                min-height: 24px;
                padding: 4px;
                border: none;
            }
            QTableWidget#tifMaterialTable QHeaderView::section,
            QTableWidget#tifPredictTargetsTable QHeaderView::section,
            QTableWidget#tifTrainingResultMetricsTable QHeaderView::section,
            QTableWidget#tifTrainingResultArtifactTable QHeaderView::section {
                background: {t['panel_alt']};
                color: {t['text_soft']};
                border: none;
                border-right: 1px solid {t['border']};
                padding: 5px 6px;
                font-weight: 700;
            }
            QLineEdit {
                background: {t['input']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 4px 6px;
                selection-background-color: {t['selection']};
            }
            QPushButton {
                background: {t['button']};
                color: {t['text']};
                border: 1px solid {t['border_strong']};
                border-radius: 10px;
                padding: 8px 12px;
                font-weight: 700;
                min-height: 18px;
            }
            QPushButton:hover {
                background: {t['button_hover']};
                border-color: {t['glow_border']};
            }
            QPushButton:pressed {
                background: {t['button_pressed']};
                border-color: {t['glow_border']};
                padding-top: 9px;
                padding-bottom: 7px;
            }
            QPushButton:disabled {
                background: {t['button_disabled']};
                color: {t['text_dim']};
                border-color: {t['border']};
            }
            QPushButton[tifRole="primary"] {
                background: {t['primary']};
                border: 1px solid {t['glow_border']};
                color: #FFFFFF;
            }
            QPushButton[tifRole="primary"]:hover {
                background: {t['primary_hover']};
                border-color: {t['glow_border']};
            }
            QPushButton[tifRole="primary"]:pressed {
                background: {t['primary_pressed']};
                border-color: {t['glow_border']};
            }
            QPushButton[tifRole="secondary"] {
                background: {t['button']};
                border: 1px solid {t['border_strong']};
                color: {t['text_soft']};
            }
            QPushButton[tifRole="secondary"]:hover {
                background: {t['button_hover']};
                border-color: {t['glow_border']};
            }
            QPushButton[tifRole="secondary"]:checked {
                background: {t['secondary_checked']};
                border: 2px solid {t['glow_border']};
                color: {t['text']};
            }
            QPushButton[tifRole="danger"] {
                background: {t['danger']};
                border: 1px solid {t['danger_border']};
                color: {t['danger_text']};
            }
            QPushButton[tifRole="danger"]:hover {
                background: {t['danger_hover']};
                border-color: {t['danger_border']};
            }
            QPushButton[tifRole="danger"]:pressed {
                background: {t['danger_pressed']};
                border-color: {t['danger_border']};
            }
            QTextEdit#tifLogConsole {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                padding: 6px;
            }
            QScrollArea#tifTrainingResultPreviewScroll {
                background: {t['input']};
                border: 1px solid {t['border']};
                border-radius: 10px;
            }
            QLabel#tifTrainingResultSummaryText {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel#tifPredictTargetsSummaryText {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel#tifLayerHelpText {
                color: {t['text_soft']};
                background: {t['input']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel#tifCurrentMaterialText {
                color: {t['text']};
                border: none;
                font-weight: 700;
            }
            QLabel#tifAutoSaveHintText {
                color: {t['text_dim']};
                border: none;
                font-size: 11px;
            }
            QLabel#tifSaveStatusText {
                background: {t['input']};
                color: {t['success']};
                border: 1px solid {t['success']};
                border-radius: 8px;
                padding: 5px 8px;
                font-weight: 700;
            }
            QLabel#tifSaveStatusText[tifSaveState="dirty"] {
                color: {t['warning']};
                border-color: {t['warning']};
            }
            QLabel#tifSaveStatusText[tifSaveState="saving"] {
                color: {t['accent']};
                border-color: {t['glow_border']};
            }
            QLabel#tifSaveStatusText[tifSaveState="failed"] {
                color: {t['error']};
                border-color: {t['error']};
            }
            QLabel#tifVolumeRenderStatus {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                padding: 4px 8px;
            }
            QLabel#tifStatusText,
            QLabel#tifMetadataText,
            QLabel#tifLocalAxisSummaryText,
            QLabel#tifTrainingStatusText {
                color: {t['text_soft']};
                border: none;
            }
            QPushButton#tifExportTrainingButton,
            QPushButton#tifPrepareDatasetButton,
            QPushButton#tifTrainBackendButton,
            QPushButton#tifImportPredictionButton,
            QPushButton#tifImportStackButton,
            QPushButton#tifImportAmiraButton {
                font-weight: 700;
            }
            """


def build_tif_workbench_stylesheet(theme="dark"):
    colors = tif_workbench_theme(theme)
    stylesheet = TIF_WORKBENCH_STYLESHEET_TEMPLATE
    for key, value in colors.items():
        stylesheet = stylesheet.replace("{t['" + key + "']}", str(value))
    return stylesheet
