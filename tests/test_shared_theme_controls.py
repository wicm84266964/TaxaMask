import os
import unittest
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QSpinBox, QDoubleSpinBox, QPushButton, QMenu, QToolButton, QComboBox
from PySide6.QtSvg import QSvgRenderer
from AntSleap.ui.style import (apply_theme_to_app, get_theme_config, normalize_theme, arrow_asset,
                              register_windows_scholarly_ui_fonts, apply_semantic_button_style, BUTTON_ROLE_NEUTRAL)
from AntSleap.ui.settings_dialogs import GeneralSettingsDialog
from AntSleap.ui.tif_workbench_style import tif_workbench_theme


class SharedThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        register_windows_scholarly_ui_fonts()

    def test_classic_selection_roundtrip_and_tif_palette(self):
        self.assertEqual(normalize_theme("classic_dark"), "classic_dark")
        self.assertEqual(normalize_theme("dark"), "dark")
        config = get_theme_config("classic_dark")
        self.assertEqual(config["bg_main"], "#0a0a0a")
        self.assertEqual(config["accent"], "#e8c547")
        self.assertFalse(any("gradient(" in str(v) for v in config.values()))
        self.assertEqual(tif_workbench_theme("classic_dark")["button"], config["bg_surface_alt"])
        dialog = GeneralSettingsDialog({"theme": "classic_dark"}, "zh")
        try:
            self.assertEqual(dialog.theme_combo.currentData(), "classic_dark")
            self.assertEqual(dialog.get_agent_context()["theme"], "classic_dark")
        finally:
            dialog.close()

    def test_first_launch_defaults_to_black_gold_and_remembers_saved_theme(self):
        import tempfile
        from AntSleap.core.config import ConfigManager
        root = Path(__file__).resolve().parents[1] / ".tmp_validation"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            path = Path(folder) / "config.json"
            legacy = Path(folder) / "absent-legacy.json"
            config = ConfigManager(path, legacy)
            self.assertEqual(config.get("theme"), "classic_dark")
            dialog = GeneralSettingsDialog({}, "zh")
            try:
                self.assertEqual(dialog.theme_combo.currentData(), "classic_dark")
                for theme in ("light", "dark", "classic_dark"):
                    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData(theme))
                    config.set("theme", dialog.get_values()["theme"])
                    config.save()
                    self.assertEqual(ConfigManager(path, legacy).get("theme"), theme)
            finally:
                dialog.close()

    def test_black_gold_agent_and_action_buttons_do_not_reuse_blue(self):
        from types import SimpleNamespace
        from AntSleap.ui.taxamask_agent_panel import TaxaMaskAgentPanel
        from AntSleap.ui.style import get_button_style_for_theme, BUTTON_ROLE_RUN
        import re
        css = TaxaMaskAgentPanel._web_embed_style_source(SimpleNamespace(current_theme="classic_dark"))
        self.assertEqual(css, "")
        self.assertEqual(TaxaMaskAgentPanel._embed_theme_name(SimpleNamespace(current_theme="classic_dark")), "native")
        for color in ("#405F88", "#1E314D", "#101C2F", "#8FAED4", "#2B4568"):
            self.assertNotIn(color.lower(), css.lower())
        self.assertNotIn("linear-gradient", css)
        button = get_button_style_for_theme(BUTTON_ROLE_RUN, theme="classic_dark")
        self.assertIn("color: #0a0a0a", button)
        self.assertIn("#e8c547", button)
        dashboard = (Path(__file__).resolve().parents[1] / "vendor/ant-code/src/dashboard/public/styles.css").read_text(encoding="utf-8")
        for token, key in (("bg", "bg_main"), ("panel", "bg_surface"), ("accent", "accent"), ("text", "text_main")):
            self.assertEqual(re.search(r"--" + token + r":\s*(#[0-9a-f]+)", dashboard)[1], get_theme_config("classic_dark")[key])
        neon = TaxaMaskAgentPanel._web_embed_style_source(SimpleNamespace(current_theme="dark"))
        self.assertIn("linear-gradient", neon)

    def test_numeric_text_fits_and_keyboard_editing_in_all_themes(self):
        window = QWidget(); layout = QHBoxLayout(window)
        spin = QSpinBox(); spin.setRange(5, 90); spin.setSuffix("%")
        decimal = QDoubleSpinBox(); decimal.setRange(-100, 100); decimal.setDecimals(2)
        layout.addWidget(spin); layout.addWidget(decimal)
        try:
            for theme in ("dark", "classic_dark", "light"):
                apply_theme_to_app(theme)
                window.show(); self.app.processEvents()
                for control, values in ((spin, [5, 35, 90]), (decimal, [-100, -12.34, 100])):
                    for value in values:
                        control.setValue(value); self.app.processEvents()
                        edit = control.lineEdit()
                        self.assertGreaterEqual(edit.contentsRect().width(), edit.fontMetrics().horizontalAdvance(control.text()) + 2, (theme, control.text()))
                spin.setFocus(); spin.selectAll(); QTest.keyClicks(spin, "35"); QTest.keyClick(spin, Qt.Key_Return)
                self.assertEqual(spin.value(), 35)
                QTest.keyClick(spin, Qt.Key_Up); self.assertEqual(spin.value(), 36)
        finally:
            window.close()

    def test_menu_and_combo_chevrons_are_valid_for_all_workbenches(self):
        window = QWidget(); layout = QHBoxLayout(window)
        buttons = []
        for cls in (QPushButton, QToolButton):
            button = cls(); button.setText("More actions")
            if isinstance(button, QToolButton):
                button.setPopupMode(QToolButton.InstantPopup)
            menu = QMenu(button); menu.addAction("Action"); button.setMenu(menu)
            apply_semantic_button_style(button, BUTTON_ROLE_NEUTRAL)
            layout.addWidget(button); buttons.append(button)
        combo = QComboBox(); combo.addItems(["A", "B"]); layout.addWidget(combo)
        try:
            for theme in ("dark", "classic_dark", "light"):
                apply_theme_to_app(theme); window.show(); self.app.processEvents()
                for direction in ("up", "down"):
                    path = arrow_asset(theme, direction)
                    self.assertTrue(Path(path).is_file())
                    self.assertTrue(QSvgRenderer(path).isValid())
                for button in buttons:
                    self.assertIn(arrow_asset(theme), button.styleSheet())
                combo.setCurrentIndex(1); self.assertEqual(combo.currentText(), "B")
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
