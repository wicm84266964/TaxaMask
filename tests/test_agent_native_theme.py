"""Render the actual bundled Dashboard stylesheet, including its !important rules."""
import json
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from AntSleap.ui.taxamask_agent_panel import TaxaMaskAgentPanel


class AgentNativeThemeTests(unittest.TestCase):
    def test_settings_buttons_and_theme_switch_use_native_css(self):
        app = QApplication.instance() or QApplication([])
        view = QWebEngineView()
        view.resize(900, 700)
        view.show()
        css = (Path(__file__).resolve().parents[1] / "vendor/ant-code/src/dashboard/public/styles.css").read_text(encoding="utf-8")
        loaded = []
        view.loadFinished.connect(loaded.append)
        view.setHtml('<html class="taxamask-embed taxamask-embed-dark"><head><style>' + css +
                     '</style><style id="taxamask-agent-embed-style"></style></head><body>'
                     '<nav class="settings-rail"><button id="rail">Privacy</button></nav>'
                     '<div class="settings-row-actions"><button id="edit">Edit</button></div>'
                     '<button class="settings-primary-action" id="add">Add source</button>'
                     '<aside class="sidebar">Hidden sidebar</aside></body></html>')

        def wait_for(values):
            deadline = time.monotonic() + 20
            while not values and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.01)
            self.assertTrue(values, "WebEngine did not respond")

        def evaluate(script):
            values = []
            view.page().runJavaScript(script, values.append)
            wait_for(values)
            return values[0]

        try:
            wait_for(loaded)
            self.assertTrue(loaded[0])
            sample = 'JSON.stringify(["rail","edit","add"].map(id=>getComputedStyle(document.getElementById(id)).backgroundColor))'
            blue = json.loads(evaluate(sample))
            self.assertIn("rgb(30, 49, 77)", blue)
            for theme in ("classic_dark", "light", "classic_dark"):
                owner = SimpleNamespace(current_theme=theme)
                owner._embed_theme_name = lambda: TaxaMaskAgentPanel._embed_theme_name(owner)
                owner._web_embed_style_source = lambda: TaxaMaskAgentPanel._web_embed_style_source(owner)
                # Exercise the actual live-switch JS rather than a duplicate implementation.
                owner.web_view = view
                owner._apply_web_view_background_color = lambda: None
                TaxaMaskAgentPanel._sync_web_embed_theme(owner)
                # WebEngine renders asynchronously; macOS can still expose the
                # previous frame when the first JavaScript sample completes.
                expected_class = "taxamask-embed-" + owner._embed_theme_name()
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    active = evaluate('document.documentElement.classList.contains(' + json.dumps(expected_class) + ')')
                    colors = json.loads(evaluate(sample))
                    if active and (theme != "classic_dark" or
                                   not any(color in colors for color in ("rgb(30, 49, 77)", "rgb(64, 95, 136)"))):
                        break
                    app.processEvents()
                    time.sleep(.02)
                self.assertTrue(active, "Browser did not apply the requested theme")
                colors = json.loads(evaluate(sample))
                if theme == "classic_dark":
                    self.assertNotIn("rgb(30, 49, 77)", colors)
                    self.assertNotIn("rgb(64, 95, 136)", colors)
                    self.assertEqual(evaluate('getComputedStyle(document.documentElement).getPropertyValue("--accent").trim()'), "#e8c547")
                    self.assertEqual(evaluate('document.querySelector("#taxamask-agent-embed-style").textContent'), "")
                    self.assertEqual(evaluate('getComputedStyle(document.querySelector(".sidebar")).display'), "none")
                    self.assertFalse(evaluate('document.documentElement.classList.contains("taxamask-embed-dark")'))
        finally:
            view.close()
            view.deleteLater()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()
