# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

import os
import base64
import io
import json
import sys
import tempfile
import sqlite3
import csv
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

has_pyside6 = False


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(os.path.abspath(str(right)))


try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
        main_module = None
        PROJECT_TEMPLATE_GENERIC = "generic_taxonomy"
        PdfProcessingWidget = None
    else:
        raise
else:
    from PIL import Image, ImageDraw, ImageFont

    import AntSleap.main as main_module
    import AntSleap.ui.pdf_processing_widget as pdf_widget_module
    from AntSleap.core.project_templates import PROJECT_TEMPLATE_GENERIC
    from AntSleap.core.stl_project import StlRenderedProjectManager
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget, LLMConnectionTestWorker

    has_pyside6 = True


class SmokeConfigManager:
    def __init__(self):
        self.values = {
            "language": "en",
            "runtime_device": "cpu",
            "theme": "dark",
            "last_project_path": "",
        }

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        return None


class SmokePartsModel:
    ultralytics_sam = None


class SmokeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)
        return None

    def emit(self, *args, **kwargs):
        for callback in list(self.callbacks):
            callback(*args, **kwargs)


class SmokeThread:
    def __init__(self):
        self.started = SmokeSignal()
        self._running = False

    def start(self):
        self._running = True
        self.started.emit()

    def isRunning(self):
        return self._running

    def quit(self):
        self._running = False

    def wait(self, _timeout=None):
        return True


class SmokeSamWorker:
    created = 0

    def __init__(self, *args, **kwargs):
        type(self).created += 1
        self.model = None
        self.mask_generated = SmokeSignal()
        self.model_loaded = SmokeSignal()
        self.model_load_error = SmokeSignal()

    def moveToThread(self, thread):
        self.thread = thread

    def load_model(self):
        self.model = object()
        self.model_loaded.emit()


class SmokeCascadeManager:
    def list_available_experts(self):
        return []

    def get_route_block_reason(self, route):
        return "expert_unappointed"


class SmokeEngine:
    def __init__(self, *args, **kwargs):
        self.weights_dir = tempfile.mkdtemp()
        self.locator = None
        self.parts_model = None
        self.cascade_manager = SmokeCascadeManager()
        self.current_num_classes = int(kwargs.get("num_classes", 3) or 3)
        self.locator_resolution = (512, 512)
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False
        self.loaded_locator_timestamp = None
        self.device_preference = kwargs.get("device", "cpu")
        self.ensure_locator_loaded_calls = 0
        self.ensure_parts_model_loaded_calls = 0

    def set_device_preference(self, preference):
        self.device_preference = preference
        return False

    def rebuild_locator(self, num_classes, learning_rate, weight_decay):
        self.current_num_classes = int(num_classes)

    def update_hyperparameters(self, learning_rate, weight_decay):
        return None

    def ensure_locator_loaded(self):
        self.ensure_locator_loaded_calls += 1
        if self.locator is None:
            self.locator = object()
        return self.locator

    def ensure_parts_model_loaded(self):
        self.ensure_parts_model_loaded_calls += 1
        if self.parts_model is None:
            self.parts_model = SmokePartsModel()
        return self.parts_model

    def load_locator(self, timestamp):
        self.ensure_locator_loaded()
        self.loaded_locator_timestamp = timestamp
        return None

    def load_sam_decoder(self, timestamp):
        return None

    def reset_locator_to_base(self):
        self.ensure_locator_loaded()
        return None

    def reset_sam_to_base(self):
        return None


class SmokeDatabase:
    def query_trait_description(self, genus_name, part_name):
        return ""


@unittest.skipUnless(has_pyside6, "PySide6 is required for GUI smoke tests")
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)
        self._runtime_patchers = [
            patch.object(main_module, "SAMWorker", SmokeSamWorker),
            patch.object(main_module, "QThread", SmokeThread),
        ]
        for patcher in self._runtime_patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(getattr(self, "_runtime_patchers", [])):
            patcher.stop()
        self.temp_dir.cleanup()

    def _wait_until(self, predicate, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        self.app.processEvents()
        return predicate()

    def _make_window(self):
        with patch.object(main_module, "ConfigManager", SmokeConfigManager), \
             patch.object(main_module, "AntEngine", SmokeEngine), \
             patch.object(main_module, "MultiModalDB", SmokeDatabase), \
             patch.object(main_module.MainWindow, "_default_outputs_root", lambda _window: str(self.project_dir / "TaxaMask_outputs")), \
             patch.object(main_module, "SAMWorker", SmokeSamWorker), \
             patch.object(main_module, "QThread", SmokeThread), \
             patch.object(PdfProcessingWidget, "load_api_settings", lambda self: None), \
             patch.object(PdfProcessingWidget, "refresh_profile_list", lambda self: None), \
             patch.object(PdfProcessingWidget, "sync_runtime_controls_from_config", lambda self: None), \
             patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):
            window = main_module.MainWindow()
            window._default_outputs_root = lambda: str(self.project_dir / "TaxaMask_outputs")
            return window

    def _create_literature_db(self, db_path, image_path, *, pdf_id=3, figure_id=7, species="Aphaenogaster gamagumayaa"):
        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("CREATE TABLE pdf_files (id INTEGER PRIMARY KEY, file_path TEXT, file_name TEXT)")
            c.execute(
                """
                CREATE TABLE figure_records (
                    id INTEGER PRIMARY KEY,
                    pdf_file_id INTEGER,
                    page_number INTEGER,
                    figure_index INTEGER,
                    image_file_path TEXT,
                    image_file_name TEXT,
                    species_candidate TEXT
                )
                """
            )
            c.execute(
                """
                CREATE TABLE taxon_part_descriptions (
                    id INTEGER PRIMARY KEY,
                    pdf_file_id INTEGER,
                    file_name TEXT,
                    file_path TEXT,
                    file_hash TEXT,
                    taxon_name TEXT,
                    caste_or_stage TEXT,
                    part_key TEXT,
                    part_label TEXT,
                    description_text TEXT,
                    source_pages TEXT,
                    source_block_refs TEXT,
                    source_blocks TEXT,
                    model_used TEXT,
                    confidence REAL,
                    review_status TEXT,
                    created_at TEXT
                )
                """
            )
            c.execute("INSERT INTO pdf_files (id, file_path, file_name) VALUES (?, ?, 'paper.pdf')", (pdf_id, str(Path(db_path).parent / "paper.pdf")))
            c.execute(
                """
                INSERT INTO figure_records
                    (id, pdf_file_id, page_number, figure_index, image_file_path, image_file_name, species_candidate)
                VALUES (?, ?, 2, 1, ?, ?, ?)
                """,
                (figure_id, pdf_id, str(image_path), Path(image_path).name, species),
            )
            c.execute(
                """
                INSERT INTO taxon_part_descriptions
                    (id, pdf_file_id, file_name, file_path, file_hash, taxon_name, caste_or_stage,
                     part_key, part_label, description_text, source_pages, source_block_refs,
                     source_blocks, model_used, confidence, review_status, created_at)
                VALUES
                    (11, ?, 'paper.pdf', ?, 'hash', ?, 'worker',
                     'scape', '触角/柄节', 'Scapes elongate and slim.',
                     '[2]', '["p002_b0003"]', '[]', 'mock', 0.91, 'auto_extracted', 'now')
                """,
                (pdf_id, str(Path(db_path).parent / "paper.pdf"), species),
            )
            conn.commit()
        finally:
            conn.close()

    def test_main_window_constructs_offscreen_without_loading_sam(self):
        SmokeSamWorker.created = 0
        window = self._make_window()
        try:
            self.assertEqual(window.windowTitle(), "TaxaMask Workbench (EN)")
            self.assertEqual(window.runtime_device, "cpu")
            self.assertEqual((window.startup_size.width(), window.startup_size.height()), (1480, 920))
            self.assertEqual(window.active_project_kind, "start")
            self.assertEqual(window.tabs.count(), 1)
            self.assertEqual(window.tabs.currentWidget(), window.start_center_widget)
            self.assertEqual(window.tabs.tabText(0), "Start Center")
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)
            self.assertIsNone(window.engine.locator)
            self.assertIsNone(window.engine.parts_model)
            self.assertIsNone(window.parts_model_preload_thread)
            self.assertEqual(window.engine.ensure_locator_loaded_calls, 0)
            self.assertEqual(window.engine.ensure_parts_model_loaded_calls, 0)
            self.assertEqual(SmokeSamWorker.created, 0)
            startup_path = Path(window.project.current_project_path)
            self.assertEqual(
                startup_path,
                self.project_dir / "TaxaMask_outputs" / "2d_stl_projects" / "_startup" / "TaxaMask_Project.json",
            )
            self.assertTrue(startup_path.exists())
            self.assertNotIn("AntSleap", startup_path.parts)
            self.assertEqual(window.start_title.text(), "TaxaMask Agent Center")
            self.assertIsNotNone(window.findChild(main_module.QWidget, "start2DWorkflowCard"))
            self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))
            self.assertIsNotNone(window.findChild(main_module.QWidget, "startProjectConsole"))
            self.assertTrue(window.start_console_body.isHidden())
            self.assertEqual(window.btn_start_console_toggle.text(), "+")
            self.assertIn("Project Console", window.start_console_title.text())
            self.assertTrue(window.start_console_summary.text())
            rail_scroll = window.findChild(main_module.QScrollArea, "startWorkflowRailScroll")
            self.assertIsNotNone(rail_scroll)
            rail_layout = rail_scroll.widget().layout()
            self.assertEqual(rail_layout.itemAt(0).widget(), window.start_console_panel)
            self.assertEqual(rail_layout.itemAt(1).widget(), window.start_quick_panel)
            self.assertEqual(rail_scroll.horizontalScrollBarPolicy(), main_module.Qt.ScrollBarAlwaysOff)
            self.assertEqual(rail_scroll.verticalScrollBarPolicy(), main_module.Qt.ScrollBarAsNeeded)
            self.assertIsNotNone(window.findChild(main_module.QWidget, "taxamaskAgentPanel"))
            self.assertIn("PDF literature workflow ready", window.start_console_pdf_value.text())
            self.assertIn("STL", window.start_console_stl_note.text())
            self.assertIn("2D views", window.start_console_stl_note.text())
            self.assertNotIn("3D mesh annotation", window.start_console_stl_note.text())
            window.btn_start_console_toggle.click()
            self.assertTrue(window.start_console_expanded)
            self.assertFalse(window.start_console_body.isHidden())
            self.assertEqual(window.btn_start_console_toggle.text(), "−")
            self.assertEqual(window.btn_start_ant_code.text(), "Start Ant-Code")
            self.assertEqual(window.btn_stop_ant_code.text(), "Stop Ant-Code")
            self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentInlineStatus"))
            self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskStartAntCodeButton"))
            self.assertEqual(window.agent_panel.fallback_logo.text(), "TaxaMask")
            self.assertIsNotNone(window.agent_panel.fallback_mark.pixmap())
            self.assertFalse(window.agent_panel.fallback_detail.isVisible())
            menu_texts = [
                action.text()
                for menu_action in window.menuBar().actions()
                if menu_action.menu() is not None
                for action in menu_action.menu().actions()
            ]
            self.assertIn("Workflow", [action.text() for action in window.menuBar().actions()])
            self.assertIn("Start Center", menu_texts)
            self.assertIn("2D/STL Morphology Workflow", menu_texts)
            self.assertIn("2D/STL Model Settings", menu_texts)
            self.assertNotIn("Language", menu_texts)
            self.assertNotIn("Theme", menu_texts)
            self.assertNotIn("Dark Mode", menu_texts)
            self.assertIn("Check / Relocate Project Images", menu_texts)
            self.assertIn("Import STL Rendered Views to Labeling Workbench", menu_texts)
            self.assertIn("Open PDF Evidence Tools", menu_texts)
            self.assertNotIn("New STL Rendered-View Project", menu_texts)
            joined_menu_text = "\n".join(menu_texts)
            self.assertNotIn("T" + "IF", joined_menu_text)
            self.assertNotIn("AM" + "IRA", joined_menu_text)
        finally:
            window.deleteLater()

    def test_start_center_workflow_buttons_switch_visible_tabs(self):
        window = self._make_window()
        try:
            preload_events = []
            window.ensure_sam_preloaded = lambda: preload_events.append("preload")

            window.enter_image_workflow()
            self.assertEqual(window.active_project_kind, "image")
            self.assertEqual(window.tabs.count(), 1)
            self.assertEqual(window.tabs.tabText(0), "Labeling Workbench")
            self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchCanvasShell"))
            self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchLiteratureDescriptionButton"))
            self.assertEqual(window.btn_agent_from_workbench.text(), "Ask Agent")
            self.assertEqual(preload_events, ["preload"])
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)

            window._show_start_center()
            self.assertEqual(window.tabs.count(), 1)
            self.assertEqual(window.tabs.currentWidget(), window.start_center_widget)
            self.assertEqual(preload_events, ["preload"])
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)
            self.assertFalse(hasattr(window, "enter_" + "t" + "if" + "_workflow"))
            self.assertFalse(hasattr(window, "ti" + "f_workbench"))
        finally:
            window.deleteLater()

    def test_start_center_recent_project_uses_short_display_and_full_tooltip(self):
        window = self._make_window()
        try:
            long_dir = self.project_dir / ("very_long_taxamask_project_folder_name_" * 2)
            long_dir.mkdir(parents=True)
            long_project = long_dir / ("very_long_taxamask_project_file_name_" * 2 + ".json")
            long_project.write_text("{}", encoding="utf-8")
            window.config.set("last_project_path", str(long_project))

            window._update_start_center_texts()

            self.assertIn("Continue last project", window.start_recent_label.text())
            self.assertNotIn(str(long_project), window.start_recent_label.text())
            self.assertIn("...", window.start_recent_label.text())
            self.assertEqual(window.start_recent_label.toolTip(), os.path.abspath(long_project))
        finally:
            window.deleteLater()

    def test_enter_image_workflow_preloads_models_once_and_keeps_them_after_start_center(self):
        SmokeSamWorker.created = 0
        window = self._make_window()
        try:
            with patch.object(main_module, "SAMWorker", SmokeSamWorker), \
                 patch.object(main_module, "QThread", SmokeThread):
                self.assertTrue(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))
                self.assertFalse(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))
            self.assertEqual(SmokeSamWorker.created, 1)
            window.parts_model_preload_thread.join(timeout=1)
            self.assertIsNotNone(window.sam_worker)
            self.assertIsNotNone(window.sam_thread)
            self.assertIsNotNone(window.sam_worker.model)
            self.assertIsNotNone(window.engine.locator)
            self.assertIsNotNone(window.engine.parts_model)
            self.assertEqual(window.engine.ensure_locator_loaded_calls, 1)
            self.assertEqual(window.engine.ensure_parts_model_loaded_calls, 1)
            window._show_start_center()
            self.assertIsNotNone(window.sam_worker)
            self.assertIsNotNone(window.sam_thread)
            self.assertTrue(window.sam_thread.isRunning())
            self.assertIsNotNone(window.engine.locator)
            self.assertIsNotNone(window.engine.parts_model)
        finally:
            window.deleteLater()

    def test_agent_panel_embeds_ant_code_dashboard_controls(self):
        window = self._make_window()
        try:
            self.assertEqual(window.agent_panel.workspace_dir, str(PROJECT_ROOT))
            self.assertTrue(window.agent_panel.ant_code_root.endswith(os.path.join("vendor", "ant-code")))
            self.assertIsNotNone(window.agent_panel.node_executable)
            self.assertIsNotNone(window.agent_panel.ant_code_dashboard_entry)
            self.assertIn(
                os.path.basename(window.agent_panel.ant_code_dashboard_entry),
                {"dashboard.js", "index.js"},
            )
            self.assertTrue(window.agent_panel.ant_code_config_path.endswith(os.path.join("AntSleap", "config", "taxamask_ant_code.config.json")))
            command = window.agent_panel._dashboard_command()
            self.assertEqual(command[0], window.agent_panel.node_executable)
            self.assertEqual(command[1], window.agent_panel.ant_code_dashboard_entry)
            if window.agent_panel.ant_code_dashboard_entry.endswith("index.js"):
                self.assertEqual(command[2], "dashboard")
            self.assertIn("--project", command)
            self.assertIn(str(PROJECT_ROOT), command)
            env = window.agent_panel._dashboard_environment()
            self.assertEqual(env["LAB_AGENT_PACKAGE_ROOT"], window.agent_panel.ant_code_root)
            self.assertEqual(env["LAB_AGENT_CONFIG"], window.agent_panel.ant_code_config_path)
            self.assertIsNotNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentStack"))
            self.assertEqual(window.agent_panel.fallback_logo.text(), "TaxaMask")
            self.assertIsNotNone(window.agent_panel.fallback_mark.pixmap())
            self.assertFalse(window.agent_panel.fallback_detail.isVisible())
            self.assertFalse(window.agent_panel.is_running())
        finally:
            window.deleteLater()

    def test_agent_panel_uses_source_dashboard_not_distributed_exe(self):
        panel = main_module.TaxaMaskAgentPanel(
            "en",
            workspace_dir=str(PROJECT_ROOT),
            ant_code_executable=r"C:\legacy\ant-code.exe",
        )
        try:
            command = panel._dashboard_command()
            self.assertEqual(command[0], panel.node_executable)
            self.assertEqual(command[1], panel.ant_code_dashboard_entry)
            if panel.ant_code_dashboard_entry.endswith("index.js"):
                self.assertEqual(command[2], "dashboard")
            self.assertNotIn(r"C:\legacy\ant-code.exe", command)
        finally:
            panel.deleteLater()

    def test_agent_panel_can_launch_dashboard_through_wsl(self):
        with patch.dict(
            os.environ,
            {
                "TAXAMASK_ANTCODE_RUNTIME": "wsl",
                "TAXAMASK_WSL_DISTRO": "Ubuntu",
            },
            clear=False,
        ), patch("AntSleap.ui.taxamask_agent_panel.sys.platform", "win32"), \
             patch("AntSleap.ui.taxamask_agent_panel.shutil.which", return_value=r"C:\Windows\System32\wsl.exe"):
            panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))
        try:
            panel.port = 7410
            panel.ant_code_dashboard_entry = str(PROJECT_ROOT / "vendor" / "ant-code" / "src" / "cli" / "dashboard.js")
            with patch.object(panel, "_wslpath", side_effect=lambda value: "/mnt/c/" + str(value)[3:].replace("\\", "/")):
                command = panel._dashboard_command()

            self.assertEqual(command[:4], [r"C:\Windows\System32\wsl.exe", "-d", "Ubuntu", "--exec"])
            wsl_project = "/mnt/c/" + str(PROJECT_ROOT)[3:].replace("\\", "/")
            self.assertIn(f"LAB_AGENT_PACKAGE_ROOT={wsl_project}/vendor/ant-code", command)
            self.assertIn(f"LAB_AGENT_CONFIG={wsl_project}/AntSleap/config/taxamask_ant_code.config.json", command)
            self.assertIn(f"{wsl_project}/vendor/ant-code/src/cli/dashboard.js", command)
            project_index = command.index("--project")
            self.assertEqual(command[project_index + 1], wsl_project)
        finally:
            panel.deleteLater()

    def test_agent_panel_windows_path_fallback_converts_to_wsl_mount(self):
        with patch.dict(os.environ, {"TAXAMASK_ANTCODE_RUNTIME": "wsl"}, clear=False), \
             patch("AntSleap.ui.taxamask_agent_panel.sys.platform", "win32"), \
             patch("AntSleap.ui.taxamask_agent_panel.shutil.which", return_value=r"C:\Windows\System32\wsl.exe"):
            panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=r"D:\lab data\TaxaMask")
        try:
            self.assertEqual(
                panel._fallback_windows_to_wsl_path(r"D:\lab data\TaxaMask"),
                "/mnt/d/lab data/TaxaMask",
            )
            self.assertEqual(
                panel._fallback_windows_to_wsl_path(r"\\wsl.localhost\Ubuntu\home\lab\TaxaMask"),
                "/home/lab/TaxaMask",
            )
        finally:
            panel.deleteLater()

    def test_agent_panel_uses_browser_mode_on_linux(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("AntSleap.ui.taxamask_agent_panel.sys.platform", "linux"):
            panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))
        try:
            self.assertTrue(panel.browser_mode)
            self.assertIsNone(panel.web_view)
            self.assertIn("Browser mode is active", panel.fallback_detail.text())
        finally:
            panel.deleteLater()

    def test_agent_panel_ready_opens_browser_in_browser_mode(self):
        panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))
        try:
            opened = []
            panel.browser_mode = True
            panel.dashboard_url = "http://127.0.0.1:7410"
            panel._prepare_dashboard_load = lambda reset=False: None
            panel._open_dashboard_with_platform_browser = lambda: opened.append(panel.dashboard_url) or True

            panel._on_dashboard_ready()

            self.assertEqual(opened, ["http://127.0.0.1:7410"])
        finally:
            panel.deleteLater()

    def test_agent_panel_browser_mode_copies_context_to_clipboard(self):
        panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))
        try:
            opened = []
            panel.browser_mode = True
            panel.dashboard_url = "http://127.0.0.1:7410"
            panel.process = type("Process", (), {"poll": lambda self: None})()
            panel.open_dashboard_in_browser = lambda: opened.append(panel.dashboard_url)

            panel.set_context(
                {
                    "source_workbench": "Image workbench",
                    "active_image_path": "sample.png",
                    "suggested_agent_action": "Help inspect this image.",
                },
                announce=True,
            )

            copied = QApplication.clipboard().text()
            self.assertIn("Image workbench", copied)
            self.assertIn("sample.png", copied)
            self.assertEqual(opened, ["http://127.0.0.1:7410"])
            self.assertEqual(panel._pending_context_prompt, "")
            self.assertIn("clipboard", panel.status_text())
            self.assertIn("clipboard", panel.fallback_detail.text())
        finally:
            panel.deleteLater()

    def test_agent_panel_preflights_before_loading_webview(self):
        window = self._make_window()
        try:
            panel = window.agent_panel
            events = []
            panel.dashboard_url = "http://127.0.0.1:7410"
            panel.process = type("Process", (), {"poll": lambda self: None})()
            panel._preflight_dashboard = lambda report_error=False: events.append(("preflight", report_error)) or True
            panel._load_dashboard = lambda: events.append(("load", None))

            with patch("AntSleap.ui.taxamask_agent_panel.QTimer.singleShot", lambda _ms, callback: callback()):
                panel.start_dashboard()

            self.assertEqual(events, [("preflight", False), ("load", None)])
            self.assertEqual(panel._preflight_checks_remaining, 6)
        finally:
            window.deleteLater()

    def test_agent_panel_post_load_script_reconciles_embedded_trust(self):
        window = self._make_window()
        try:
            script = window.agent_panel._web_post_load_source()

            self.assertIn("button[data-action=\"trust\"]", script)
            self.assertIn("trustButton.click()", script)
            self.assertIn("postTrust", script)
            self.assertIn("__taxamaskAgentTrustReloaded", script)
            self.assertIn("sendText === '待信任'", script)
        finally:
            window.deleteLater()

    def test_agent_panel_embed_style_defers_to_dashboard_composer(self):
        window = self._make_window()
        try:
            script = window.agent_panel._web_bootstrap_source()

            self.assertIn('classList.add("taxamask-embed")', script)
            self.assertIn(".sidebar,", script)
            self.assertIn(".preview", script)
            self.assertNotIn("min-height: 74px", script)
            self.assertNotIn("#prompt-input {", script)
            self.assertNotIn("#send-button {", script)
            self.assertNotIn(".composer {", script)
        finally:
            window.deleteLater()

    def test_agent_panel_keeps_pending_prompt_until_insert_confirmed(self):
        window = self._make_window()
        try:
            panel = window.agent_panel
            starts = []

            class RetryTimer:
                def isActive(self):
                    return False

                def start(self, delay):
                    starts.append(delay)

            panel.prompt_retry_timer = RetryTimer()
            panel._pending_context_prompt = "现场信息 A"

            panel._queue_prompt_if_not_inserted("现场信息 A", False)

            self.assertEqual(panel._pending_context_prompt, "现场信息 A")
            self.assertEqual(panel._pending_prompt_attempts, 1)
            self.assertTrue(starts)

            panel._queue_prompt_if_not_inserted("现场信息 A", True)

            self.assertEqual(panel._pending_context_prompt, "")
            self.assertEqual(panel._pending_prompt_attempts, 0)
        finally:
            window.deleteLater()

    def test_agent_panel_ignores_stale_prompt_insert_callback(self):
        window = self._make_window()
        try:
            panel = window.agent_panel
            starts = []

            class RetryTimer:
                def isActive(self):
                    return False

                def start(self, delay):
                    starts.append(delay)

            panel.prompt_retry_timer = RetryTimer()
            panel._pending_context_prompt = "最新现场"

            panel._queue_prompt_if_not_inserted("旧现场", False)

            self.assertEqual(panel._pending_context_prompt, "最新现场")
            self.assertEqual(panel._pending_prompt_attempts, 0)
            self.assertEqual(starts, [])
        finally:
            window.deleteLater()

    def test_agent_panel_keeps_context_after_startup_json_warning(self):
        window = self._make_window()
        try:
            panel = window.agent_panel
            starts = []
            statuses = []

            class RetryTimer:
                def isActive(self):
                    return False

                def start(self, delay):
                    starts.append(delay)

            class RunningProcess:
                def poll(self):
                    return None

            panel.process = RunningProcess()
            panel.prompt_retry_timer = RetryTimer()
            panel._pending_context_prompt = "现场信息 B"
            panel._update_status_label = lambda text: statuses.append(text)

            panel._on_web_console_message(
                None,
                "Expected double-quoted property name in JSON at position 1048534 (line 21346 column 4)",
                21346,
                "qrc://embedded",
            )

            self.assertEqual(panel._pending_context_prompt, "现场信息 B")
            self.assertTrue(starts)
            self.assertIn("Starting Ant-Code Dashboard", statuses[-1])
            self.assertNotIn("Unable to start Ant-Code", statuses[-1])
        finally:
            window.deleteLater()

    def test_agent_panel_allows_extra_embed_ready_retries_for_pending_context(self):
        window = self._make_window()
        try:
            panel = window.agent_panel
            loads = []
            starts = []

            class RetryTimer:
                def isActive(self):
                    return False

                def start(self, delay):
                    starts.append(delay)

            class RunningProcess:
                def poll(self):
                    return None

            panel.process = RunningProcess()
            panel.web_view = object()
            panel.dashboard_url = "http://127.0.0.1:7410"
            panel.prompt_retry_timer = RetryTimer()
            panel._pending_context_prompt = "现场信息 C"
            panel._load_retries = 1
            panel._load_dashboard = lambda: loads.append("load")

            with patch.object(main_module.QTimer, "singleShot", lambda _ms, callback: callback()):
                panel._handle_embedded_page_ready(False)

            self.assertEqual(panel._pending_context_prompt, "现场信息 C")
            self.assertEqual(loads, ["load"])
            self.assertTrue(starts)
            self.assertEqual(panel._load_retries, 2)
        finally:
            window.deleteLater()

    def test_agent_panel_returns_to_fallback_when_embed_never_becomes_ready(self):
        window = self._make_window()
        try:
            panel = window.agent_panel
            statuses = []

            class RunningProcess:
                def poll(self):
                    return None

            panel.process = RunningProcess()
            fake_web_view = main_module.QWidget()
            panel.web_view = fake_web_view
            panel.dashboard_url = "http://127.0.0.1:7410"
            panel._load_retries = 4
            panel._pending_context_prompt = "现场信息 D"
            panel.stack.addWidget(fake_web_view)
            panel.stack.setCurrentWidget(fake_web_view)
            panel._update_status_label = lambda text: statuses.append(text)

            panel._handle_embedded_page_ready(False)

            self.assertEqual(panel.stack.currentWidget(), panel.fallback)
            self.assertIn("embedded page init failed", statuses[-1])
            self.assertIn("embedded page init failed", panel.fallback_detail.text())
        finally:
            window.deleteLater()

    def test_agent_panel_returns_to_fallback_when_web_load_fails(self):
        window = self._make_window()
        try:
            panel = window.agent_panel
            statuses = []
            fake_web_view = main_module.QWidget()
            panel.web_view = fake_web_view
            panel.stack.addWidget(fake_web_view)
            panel.stack.setCurrentWidget(fake_web_view)
            panel._update_status_label = lambda text: statuses.append(text)

            panel._on_web_load_finished(False)

            self.assertEqual(panel.stack.currentWidget(), panel.fallback)
            self.assertIn("embedded page load failed", statuses[-1])
            self.assertIn("embedded page load failed", panel.fallback_detail.text())
        finally:
            window.deleteLater()

    def test_agent_panel_stop_dashboard_terminates_process_tree(self):
        window = self._make_window()
        try:
            panel = window.agent_panel

            class RunningProcess:
                pid = 12345

                def poll(self):
                    return None

                def wait(self, timeout=None):
                    return 0

            panel.process = RunningProcess()
            panel._cleanup_owned_dashboard_processes = lambda: None

            with patch("AntSleap.ui.taxamask_agent_panel.sys.platform", "win32"), \
                 patch("AntSleap.ui.taxamask_agent_panel.subprocess.run") as run_mock:
                panel.stop_dashboard()

            run_mock.assert_called_once()
            self.assertEqual(run_mock.call_args.args[0][:4], ["taskkill", "/PID", "12345", "/T"])
            self.assertIn("/F", run_mock.call_args.args[0])
            self.assertIsNone(panel.process)
            self.assertFalse(panel.dashboard_url)
        finally:
            window.deleteLater()

    def test_agent_panel_owned_dashboard_matching_is_project_scoped(self):
        window = self._make_window()
        try:
            panel = window.agent_panel
            project = panel.workspace_dir
            dashboard = panel.ant_code_dashboard_entry
            self.assertTrue(panel._is_owned_dashboard_process(
                f'"C:\\Program Files\\nodejs\\node.exe" "{dashboard}" dashboard --project "{project}" --port 7410 --no-open',
                "node.exe",
            ))
            self.assertTrue(panel._is_owned_dashboard_process(
                f'C:\\tools\\ant-code.exe dashboard --project "{project}" --port 7411 --no-open',
                "ant-code.exe",
            ))
            self.assertFalse(panel._is_owned_dashboard_process(
                '"C:\\Program Files\\nodejs\\node.exe" C:\\other\\dashboard.js --project C:\\other --port 7410',
                "node.exe",
            ))
            self.assertFalse(panel._is_owned_dashboard_process(
                f'"C:\\Program Files\\nodejs\\node.exe" C:\\scripts\\server.js --project "{project}"',
                "node.exe",
            ))
        finally:
            window.deleteLater()

    def test_agent_panel_blocks_invalid_active_project_json(self):
        window = self._make_window()
        try:
            bad_project = self.project_dir / "active_project.json"
            bad_project.write_text('{"name": "broken", bad: true}', encoding="utf-8")
            panel = window.agent_panel
            panel._project_display = str(bad_project)

            error = panel._dashboard_json_health_error()

            self.assertIn("Active project JSON check failed", error)
            self.assertIn("active_project.json", error)
            self.assertIn("line 1", error)
        finally:
            window.deleteLater()

    def test_agent_panel_warns_but_does_not_block_unselected_workspace_json(self):
        window = self._make_window()
        try:
            valid_project = self.project_dir / "current_project.json"
            valid_project.write_text('{"name": "valid"}', encoding="utf-8")
            backup = self.project_dir / "old_backup.json"
            backup.write_text('{"name": "backup", bad: true}', encoding="utf-8")
            panel = window.agent_panel
            panel.workspace_dir = str(self.project_dir)
            panel._project_display = str(valid_project)
            panel._context = {}

            self.assertEqual(panel._dashboard_json_health_error(), "")
            warning = panel._dashboard_workspace_json_warning()

            self.assertIn("Workspace contains an invalid JSON file", warning)
            self.assertIn("old_backup.json", warning)
        finally:
            window.deleteLater()

    def test_start_center_entry_is_navigation_only(self):
        window = self._make_window()
        try:
            window.project.current_project_path = str(self.project_dir / "image_project.json")
            window.current_image = str(self.project_dir / "head.png")
            window.log("sample recent error")
            window.agent_panel._context = {"source_workbench": "previous"}
            window.enter_image_workflow()
            window.return_to_start_center_with_context()

            self.assertEqual(window.active_project_kind, "start")
            self.assertEqual(window.tabs.currentWidget(), window.start_center_widget)
            self.assertEqual(window.agent_panel._context, {"source_workbench": "previous"})
        finally:
            window.deleteLater()

    def test_ask_agent_carries_compact_context_only(self):
        window = self._make_window()
        try:
            window.project.current_project_path = str(self.project_dir / "image_project.json")
            window.current_image = str(self.project_dir / "head.png")
            window.log("x" * 1200)
            window.enter_image_workflow()
            window.open_agent_from_context(window._collect_image_workbench_agent_context())

            context = window.agent_panel._context
            self.assertEqual(context["source_workbench"], "labeling")
            self.assertIn("head.png", context["active_image_path"])
            self.assertIn("context_policy", context)
            self.assertEqual(context["diagnostic_route"], "labeling_workbench_context")
            self.assertIn("LLM_CONTEXT_DETAILED.md", context["llm_context_refs"])
            self.assertIn("MainWindow._collect_image_workbench_agent_context", context["source_code_refs"])
            self.assertIn("[truncated]", context["recent_log_excerpt"])
            self.assertLess(len(str(context)), 5000)
        finally:
            window.deleteLater()

    def test_ask_agent_auto_starts_ant_code_and_queues_context(self):
        window = self._make_window()
        try:
            events = []
            window.agent_panel.is_running = lambda: False
            window.agent_panel.start_dashboard = lambda: events.append("start")

            window.open_agent_from_context({"source_workbench": "general_settings", "project_type": "settings"})

            self.assertEqual(events, ["start"])
            self.assertIn("来源工作台: general_settings", window.agent_panel._pending_context_prompt)
            self.assertIn("诊断路线: general_settings_runtime", window.agent_panel._pending_context_prompt)
            self.assertIn("建议阅读的大模型对接位置:", window.agent_panel._pending_context_prompt)
        finally:
            window.deleteLater()

    def test_ask_agent_reuses_running_ant_code(self):
        window = self._make_window()
        try:
            events = []
            prompts = []
            window.agent_panel.is_running = lambda: True
            window.agent_panel.start_dashboard = lambda: events.append("start")
            window.agent_panel._send_context_prompt = lambda prompt: prompts.append(prompt)

            window.open_agent_from_context({"source_workbench": "general_settings", "project_type": "settings"})

            self.assertEqual(events, [])
            self.assertEqual(window.agent_panel._pending_context_prompt, "")
            self.assertEqual(len(prompts), 1)
            self.assertIn("项目类型: settings", prompts[0])
            self.assertIn("上下文策略:", prompts[0])
        finally:
            window.deleteLater()

    def test_language_switch_and_model_settings_are_lightweight(self):
        window = self._make_window()
        try:
            window.change_language("zh")
            self.assertEqual(window.current_lang, "zh")
            self.assertIn("TaxaMask Workbench", window.windowTitle())
            self.assertEqual(window.start_title.text(), "TaxaMask Agent 中心")
            self.assertEqual(window.btn_start_ant_code.text(), "启动 Ant-Code")
            self.assertEqual(window.btn_general_settings.text(), "通用设置")

            dialog = main_module.ModelSettingsDialog(
                {
                    "epochs": 1,
                    "batch": 1,
                    "lr": 1e-4,
                    "wd": 1e-4,
                    "conf": 0.1,
                    "adapt": 0.4,
                    "pad": 0.4,
                    "noise_floor": 0.15,
                    "poly_epsilon": 2.0,
                    "runtime_device": "cpu",
                    "taxonomy": ["Head", "Mesosoma"],
                    "locator_scope": ["Head"],
                },
                lang=window.current_lang,
                parent=window,
            )
            try:
                self.assertEqual(dialog.windowTitle(), "2D/STL 形态学模型设置")
                self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "modelSettingsAskAgentButton"))
                self.assertEqual(dialog.get_values()["runtime_device"], "cpu")
                runtime_group = dialog.findChild(main_module.QWidget, "modelSettingsRuntimeDevicePanel")
                self.assertIsNotNone(runtime_group)
                device_combo = runtime_group.findChild(main_module.QComboBox)
                self.assertIsNotNone(device_combo)
                device_values = {
                    device_combo.itemData(index)
                    for index in range(device_combo.count())
                }
                self.assertEqual(device_values, {"auto", "cpu", "cuda"})
                self.assertNotIn("mps", device_values)
            finally:
                dialog.deleteLater()
        finally:
            window.deleteLater()

    def test_vlm_preannotation_settings_live_in_inference_tab(self):
        dialog = main_module.ModelSettingsDialog(
            {
                "epochs": 1,
                "batch": 1,
                "lr": 1e-4,
                "wd": 1e-4,
                "conf": 0.1,
                "adapt": 0.4,
                "pad": 0.4,
                "noise_floor": 0.15,
                "poly_epsilon": 2.0,
                "runtime_device": "cpu",
                "taxonomy": ["Head", "Mesosoma", "Gaster"],
                "locator_scope": ["Head"],
                "vlm_preannotation": {
                    "target_parts": ["Mesosoma", "Gaster"],
                    "processing_scope": "image_group",
                    "image_group": "split",
                },
            },
            lang="en",
        )
        try:
            def has_ancestor(widget, ancestor):
                current = widget
                while current is not None:
                    if current is ancestor:
                        return True
                    current = current.parentWidget()
                return False

            parent_content = dialog.tabs.widget(dialog.parent_tab_index).widget()
            inference_content = dialog.tabs.widget(dialog.inference_tab_index).widget()
            vlm_panel = dialog.findChild(main_module.QWidget, "modelSettingsVlmPreannotationPanel")
            self.assertIsNotNone(vlm_panel)
            self.assertFalse(has_ancestor(vlm_panel, parent_content))
            self.assertTrue(has_ancestor(vlm_panel, inference_content))
            self.assertEqual(dialog.get_values()["vlm_preannotation"]["processing_scope"], "image_group")
            self.assertEqual(dialog.get_values()["vlm_preannotation"]["image_group"], "split")
            scope_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmBatchScopeCombo")
            self.assertIsNotNone(scope_combo)
            scope_values = {scope_combo.itemData(index) for index in range(scope_combo.count())}
            self.assertEqual(scope_values, {"all_images", "image_group"})
            group_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")
            self.assertIsNotNone(group_combo)
            self.assertGreaterEqual(group_combo.findData("hard_candidates"), 0)
            profile_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmPromptProfileCombo")
            self.assertIsNotNone(profile_combo)
            self.assertTrue(has_ancestor(profile_combo, inference_content))
            self.assertEqual(
                dialog.get_values()["vlm_preannotation"]["target_parts"],
                ["Mesosoma", "Gaster"],
            )
        finally:
            dialog.deleteLater()

    def test_model_settings_vlm_group_combo_accepts_custom_groups(self):
        dialog = main_module.ModelSettingsDialog(
            {
                "epochs": 1,
                "batch": 1,
                "lr": 1e-4,
                "wd": 1e-4,
                "conf": 0.1,
                "adapt": 0.4,
                "pad": 0.4,
                "noise_floor": 0.15,
                "poly_epsilon": 2.0,
                "runtime_device": "cpu",
                "taxonomy": ["Head"],
                "locator_scope": ["Head"],
                "vlm_preannotation": {
                    "target_parts": ["Head"],
                    "processing_scope": "image_group",
                    "image_group": "review_ready",
                },
                "vlm_image_group_definitions": [
                    ("review_ready", "Review Ready"),
                ],
            },
            lang="en",
        )
        try:
            combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")
            self.assertIsNotNone(combo)
            self.assertGreaterEqual(combo.findData("review_ready"), 0)
            self.assertEqual(combo.currentData(), "review_ready")
            values = dialog.get_values()
            self.assertEqual(values["vlm_preannotation"]["image_group"], "review_ready")
        finally:
            dialog.deleteLater()

    def test_model_settings_vlm_custom_prompt_profile_round_trips(self):
        dialog = main_module.ModelSettingsDialog(
            {
                "epochs": 1,
                "batch": 1,
                "lr": 1e-4,
                "wd": 1e-4,
                "conf": 0.1,
                "adapt": 0.4,
                "pad": 0.4,
                "noise_floor": 0.15,
                "poly_epsilon": 2.0,
                "runtime_device": "cpu",
                "taxonomy": ["Head", "Thorax", "Abdomen"],
                "locator_scope": ["Head"],
                "vlm_preannotation": {
                    "target_parts": ["Head", "Thorax"],
                    "processing_scope": "image_group",
                    "image_group": "split",
                    "prompt_profile_id": "project_custom",
                    "prompt_profile": {
                        "profile_id": "project_custom",
                        "display_name": "Dragonfly prompt",
                        "taxon_context": "蜻蜓图像",
                        "body_focus_rules": "不要把翅纳入胸部主体框。",
                        "part_anchor_rules": "Thorax 位于头和腹之间。",
                        "extra_instructions": "先看节段连接。",
                    },
                },
            },
            lang="zh",
        )
        try:
            values = dialog.get_values()["vlm_preannotation"]
            self.assertEqual(values["prompt_profile_id"], "project_custom")
            self.assertEqual(values["prompt_profile"]["display_name"], "Dragonfly prompt")
            self.assertIn("蜻蜓", values["prompt_profile"]["taxon_context"])
            self.assertIn("不要把翅", values["prompt_profile"]["body_focus_rules"])
        finally:
            dialog.deleteLater()

    def test_vlm_workbench_buttons_use_action_specific_labels(self):
        window = self._make_window()
        try:
            window.change_language("zh")
            self.assertEqual(window.btn_vlm_preannotate_current.text(), "VLM预标注")
            self.assertEqual(window.btn_vlm_preannotate_batch.text(), "VLM批量预标")
            window.change_language("en")
            self.assertEqual(window.btn_vlm_preannotate_current.text(), "VLM Pre-Label")
            self.assertEqual(window.btn_vlm_preannotate_batch.text(), "VLM Batch Pre-Label")
        finally:
            window.deleteLater()

    def test_general_settings_are_not_2d_stl_model_settings(self):
        dialog = main_module.GeneralSettingsDialog(
            {
                "language": "zh",
                "theme": "dark",
                "startup_behavior": "continue_last",
                "project_autosave_interval_sec": 5,
                "runtime_device": "cpu",
            },
            lang="zh",
        )
        try:
            self.assertEqual(dialog.windowTitle(), "软件通用设置")
            values = dialog.get_values()
            self.assertEqual(values["language"], "zh")
            self.assertEqual(values["startup_behavior"], "continue_last")
            self.assertEqual(values["project_autosave_interval_sec"], 5)
            self.assertEqual(values["runtime_device"], "cpu")
            self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "generalSettingsAskAgentButton"))
            context = dialog.get_agent_context()
            self.assertEqual(context["source_workbench"], "general_settings")
            self.assertEqual(context["settings_scope"], "general")
            self.assertEqual(context["runtime_device"], "cpu")
            self.assertIsNone(dialog.findChild(main_module.QWidget, "modelSettingsLocatorScopePanel"))
        finally:
            dialog.deleteLater()

    def test_settings_ask_agent_context_is_compact_and_command_safe(self):
        window = self._make_window()
        try:
            model_dialog = main_module.ModelSettingsDialog(
                {
                    "epochs": 1,
                    "batch": 1,
                    "lr": 1e-4,
                    "wd": 1e-4,
                    "conf": 0.1,
                    "adapt": 0.4,
                    "pad": 0.4,
                    "noise_floor": 0.15,
                    "poly_epsilon": 2.0,
                    "runtime_device": "cpu",
                    "model_backend": main_module.EXTERNAL_BACKEND_ID,
                    "external_backend": {
                        "backend_id": "custom_backend",
                        "display_name": "Custom Backend",
                        "python_executable": "python",
                        "prepare_dataset_command": "python prepare.py --contract {contract_json} --very-long-private-flag secret",
                        "train_command": "python train.py --missing-contract",
                        "predict_command": "",
                        "model_manifest": "{run_dir}/manifest.json",
                    },
                    "taxonomy": ["Head"],
                    "locator_scope": ["Head"],
                },
                lang="en",
                parent=window,
            )
            try:
                model_dialog.child_backend_combo.setCurrentIndex(
                    model_dialog.child_backend_combo.findData(main_module.CHILD_BACKEND_EXTERNAL)
                )
                model_dialog.external_blink_backend_id.setText("child_backend")
                model_dialog.external_blink_display_name.setText("Child Backend")
                model_dialog.external_blink_predict_command.setPlainText("python predict_child.py --contract {contract_json}")
                model_dialog.external_blink_train_command.setPlainText("python train_child.py --missing-contract")
                route_owner = type(
                    "RouteOwner",
                    (),
                    {
                        "project": type(
                            "RouteProject",
                            (),
                            {
                                "iter_cascade_routes": lambda _self: [
                                    {
                                        "parent": "Head",
                                        "child": "Mandible",
                                        "expert_backend": main_module.ROUTE_BACKEND_HEATMAP_BLINK,
                                    }
                                ]
                            },
                        )()
                    },
                )()
                model_dialog.route_panel = type("RoutePanel", (), {"owner": route_owner})()
                context = model_dialog.get_agent_context()
                self.assertEqual(context["settings_scope"], "2d_stl_model")
                self.assertEqual(context["advanced_extension_scope"], "2d_stl_model_profile")
                self.assertEqual(context["parent_model_source"], main_module.PARENT_BACKEND_EXTERNAL)
                self.assertEqual(context["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)
                self.assertEqual(context["default_child_route_backend"], main_module.ROUTE_BACKEND_EXTERNAL_BLINK)
                self.assertEqual(context["route_specific_backend_count"], "1")
                self.assertIn("Head->Mandible:heatmap_blink", context["route_specific_backend_summary"])
                self.assertEqual(context["prepare_command_present"], "yes")
                self.assertEqual(context["prepare_command_has_contract"], "yes")
                self.assertEqual(context["train_command_present"], "yes")
                self.assertEqual(context["train_command_has_contract"], "no")
                self.assertEqual(context["child_predict_command_present"], "yes")
                self.assertEqual(context["child_predict_command_has_contract"], "yes")
                self.assertEqual(context["child_train_command_present"], "yes")
                self.assertEqual(context["child_train_command_has_contract"], "no")
                self.assertNotIn("very-long-private-flag", str(context))

                compact = window._compact_agent_context(context)
                self.assertEqual(compact["source_workbench"], "stl_model_settings")
                self.assertEqual(compact["external_backend_id"], "custom_backend")
                self.assertEqual(compact["child_extension_id"], "child_backend")
                self.assertEqual(compact["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)
                self.assertIn("Head->Mandible:heatmap_blink", compact["route_specific_backend_summary"])
                self.assertIn("validation_errors", compact)
                self.assertIn("contract_placeholder_missing", compact["diagnostic_route"])
                self.assertIn("docs/contracts/external_backend_contract_v1.md", compact["source_code_refs"])
                self.assertIn("docs/contracts/external_blink_backend_contract_v1.md", compact["source_code_refs"])
                self.assertIn("AntSleap/core/model_profiles.py", compact["source_code_refs"])
                self.assertIn("Advanced Extensions for 2D/STL model profiles", compact["diagnostic_focus"])
                self.assertIn("Advanced Extensions configuration task", compact["suggested_agent_action"])
                self.assertIn("contract_placeholder=missing", compact["health_check_summary"])
                self.assertLess(len(str(compact)), 5000)
            finally:
                model_dialog.deleteLater()

        finally:
            window.deleteLater()

    def test_project_create_and_open_lightweight_path(self):
        window = self._make_window()
        try:
            preload_events = []
            window.ensure_sam_preloaded = lambda: preload_events.append("preload")
            window.project.create_project("smoke_project", str(self.project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            created_path = self.project_dir / "smoke_project.json"
            self.assertTrue(created_path.exists())

            window.open_project_path(str(created_path))
            self.assertEqual(window.project.project_data["name"], "smoke_project")
            self.assertEqual(window.project.get_locator_scope(), ["Object"])
            self.assertEqual(window.active_project_kind, "image")
            self.assertEqual(window.tabs.currentWidget(), window.workbench_widget)
            self.assertTrue(self._wait_until(lambda: preload_events == ["preload"]))
            self.assertEqual(preload_events, ["preload"])
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)
        finally:
            window.deleteLater()

    def test_continue_last_large_project_opens_with_collapsed_image_groups(self):
        window = self._make_window()
        try:
            image_paths = [str(self.project_dir / f"large_plate_{index:04d}.png") for index in range(1200)]
            labels = {
                image_path: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
                for image_path in image_paths
            }
            project_path = self.project_dir / "large_continue_project.json"
            project_payload = {
                "name": "large_continue_project",
                "project_template": PROJECT_TEMPLATE_GENERIC,
                "taxonomy": ["Object"],
                "locator_scope": ["Object"],
                "images": image_paths,
                "labels": labels,
                "image_provenance": {},
            }
            project_path.write_text(json.dumps(project_payload), encoding="utf-8")
            window.config.set("last_project_path", str(project_path))

            window.open_last_project()

            self.assertEqual(window.active_project_kind, "image")
            self.assertEqual(window.tabs.currentWidget(), window.workbench_widget)
            self.assertTrue(window.image_list_group_collapsed.get("original"))
            self.assertIsNone(window.current_image)
            self.assertEqual(window.file_list.count(), 1)
            header = window.file_list.item(0)
            self.assertEqual(header.data(main_module.Qt.UserRole + 1), "original")
            self.assertIn("1200", header.text())
            self.assertIsNone(window.file_list.currentItem())
            self.assertEqual(window.engine.ensure_locator_loaded_calls, 0)
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)
        finally:
            window.deleteLater()

    def test_open_small_project_after_large_project_restores_expanded_image_list(self):
        window = self._make_window()
        try:
            large_paths = [str(self.project_dir / f"large_plate_{index:04d}.png") for index in range(600)]
            large_path = self.project_dir / "large_project.json"
            large_path.write_text(
                json.dumps(
                    {
                        "name": "large_project",
                        "project_template": PROJECT_TEMPLATE_GENERIC,
                        "taxonomy": ["Object"],
                        "locator_scope": ["Object"],
                        "images": large_paths,
                        "labels": {path: {"parts": {}, "status": "unlabeled"} for path in large_paths},
                    }
                ),
                encoding="utf-8",
            )
            window.open_project_path(str(large_path))
            self.assertTrue(window.image_list_group_collapsed.get("original"))
            self.assertEqual(window.file_list.count(), 1)

            preload_events = []
            window.ensure_sam_preloaded = lambda: preload_events.append("preload")
            small_paths = [str(self.project_dir / f"small_plate_{index}.png") for index in range(2)]
            small_path = self.project_dir / "small_project.json"
            small_path.write_text(
                json.dumps(
                    {
                        "name": "small_project",
                        "project_template": PROJECT_TEMPLATE_GENERIC,
                        "taxonomy": ["Object"],
                        "locator_scope": ["Object"],
                        "images": small_paths,
                        "labels": {path: {"parts": {}, "status": "unlabeled"} for path in small_paths},
                    }
                ),
                encoding="utf-8",
            )

            window.open_project_path(str(small_path))

            self.assertFalse(window.image_list_group_collapsed.get("original"))
            self.assertEqual(window.file_list.count(), 2)
            self.assertEqual(window.current_image, small_paths[0])
            self.assertTrue(self._wait_until(lambda: preload_events == ["preload"]))
        finally:
            window.deleteLater()

    def test_new_project_dialogs_default_to_output_roots(self):
        window = self._make_window()
        try:
            preload_events = []
            window.ensure_2d_stl_models_preloaded = lambda: preload_events.append("preload")
            image_root = self.project_dir / "TaxaMask_outputs" / "2d_stl_projects"
            created_image_dir = image_root / "review_run"
            calls = []

            def fake_get_existing_directory(_parent, title, start_dir=""):
                calls.append((title, Path(start_dir)))
                created_image_dir.mkdir(parents=True, exist_ok=True)
                return str(created_image_dir)

            with patch.object(main_module.QFileDialog, "getExistingDirectory", fake_get_existing_directory), \
                 patch.object(main_module.QInputDialog, "getText", return_value=("review", True)), \
                 patch.object(window, "_choose_project_template", return_value={"template_id": PROJECT_TEMPLATE_GENERIC}):
                window.new_project()

            self.assertEqual(calls[0][1], image_root)
            self.assertEqual(len(calls), 1)
            self.assertEqual(Path(window.project.current_project_path), created_image_dir / "review.json")
            self.assertTrue((created_image_dir / "review.json").exists())
            self.assertEqual(preload_events, ["preload"])
            self.assertFalse(hasattr(window, "new_ti" + "f_project"))
        finally:
            window.deleteLater()

    def test_open_and_export_defaults_stay_out_of_program_package(self):
        window = self._make_window()
        try:
            ant_project_dir = Path(main_module.PACKAGE_DIR)
            window.config.set("last_project_path", str(ant_project_dir / "TaxaMask_Project.json"))
            self.assertEqual(Path(window._default_open_project_dir()), self.project_dir / "TaxaMask_outputs")

            project_dir = self.project_dir / "TaxaMask_outputs" / "2d_stl_projects" / "review"
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            self.assertEqual(Path(window._default_2d_export_dir()), project_dir / "exports")
            self.assertEqual(Path(window._vlm_preannotation_artifacts_dir()), project_dir / "vlm_preannotation")

            dialog = main_module.ExportDialog(window, "en", default_dir=window._default_2d_export_dir())
            try:
                self.assertEqual(Path(dialog.path_edit.text()), project_dir / "exports")
            finally:
                dialog.deleteLater()
        finally:
            window.deleteLater()

    def test_vlm_preannotation_progress_ui_tracks_steps(self):
        window = self._make_window()
        try:
            long_name = "specimen_" + ("verylongname_" * 8) + "001.png"
            window.vlm_preannotation_run_active = True
            window.vlm_preannotation_total_images = 2
            window.vlm_preannotation_completed_images = 0
            window.vlm_preannotation_total_steps = 12
            window.vlm_preannotation_completed_steps = 0
            window.vlm_preannotation_current_image = str(self.project_dir / long_name)
            window._create_vlm_progress_dialog()

            window._advance_vlm_progress("prepare")

            progress = window.vlm_preannotation_progress_dialog
            self.assertIsNotNone(progress)
            self.assertEqual(progress.windowModality(), main_module.Qt.NonModal)
            progress_bar = window.vlm_preannotation_progress_bar
            progress_label = window.vlm_preannotation_progress_label
            progress_path_label = window.vlm_preannotation_progress_path_label
            self.assertEqual(progress_bar.value(), 8)
            self.assertIn("8%", progress_label.text())
            self.assertIn("0/2", progress_label.text())
            self.assertIn("prepare", progress_label.text())
            self.assertIn("...", progress_path_label.text())
            self.assertLessEqual(len(progress_path_label.text()), 92)
            self.assertEqual(progress_path_label.toolTip(), str(self.project_dir / long_name))
            self.assertGreaterEqual(progress.minimumWidth(), 560)
            self.assertLessEqual(progress.maximumWidth(), 560)

            window._mark_current_vlm_image_done("done")

            self.assertIn("1/2", progress_label.text())
        finally:
            if getattr(window, "vlm_preannotation_progress_dialog", None) is not None:
                window.vlm_preannotation_progress_dialog.close()
                window.vlm_preannotation_progress_dialog.deleteLater()
                window.vlm_preannotation_progress_dialog = None
            window.deleteLater()

    def test_vlm_result_refreshes_current_canvas_with_project_relative_path(self):
        window = self._make_window()
        try:
            project_dir = self.project_dir / "review_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            image_path = project_dir / "specimen.png"
            Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            window.project.add_images([str(image_path)])

            relative_current = os.path.relpath(str(image_path), str(project_dir))
            window.current_image = relative_current
            window.canvas.load_image(str(image_path))
            window.vlm_preannotation_total_images = 1
            window.vlm_preannotation_completed_images = 0
            window.vlm_preannotation_total_steps = 6
            window.vlm_preannotation_completed_steps = 3
            window.vlm_preannotation_current_image_steps_completed = 3
            window.vlm_preannotation_current_image = str(image_path)
            window.vlm_preannotation_records = []
            window.vlm_preannotation_saved_total = 0
            refresh_calls = []
            original_refresh = window._refresh_vlm_canvas_if_current
            window._refresh_vlm_canvas_if_current = lambda path: (refresh_calls.append(path), original_refresh(path))

            window.engine.predict_base_sam_polygon = lambda *_args, **_kwargs: None
            window._on_vlm_preannotation_image_result(
                {
                    "status": "passed",
                    "image_path": str(image_path),
                    "candidates": [
                        {
                            "part": "Head",
                            "box_xyxy": [10.0, 12.0, 50.0, 44.0],
                            "confidence": 0.8,
                            "reason": "visible head",
                        },
                        {
                            "part": "Mesosoma",
                            "box_xyxy": [40.0, 18.0, 90.0, 55.0],
                            "confidence": 0.75,
                            "reason": "visible mesosoma",
                        }
                    ],
                    "report_path": str(project_dir / "vlm_report.json"),
                }
            )

            project_image_key = window.project.project_data["images"][0]
            self.assertEqual(window.project.get_auto_boxes(project_image_key)["Head"], [10.0, 12.0, 50.0, 44.0])
            self.assertEqual(window.canvas.vlm_boxes["Head"], [10.0, 12.0, 50.0, 44.0])
            self.assertEqual(window.canvas.vlm_boxes["Mesosoma"], [40.0, 18.0, 90.0, 55.0])
            self.assertGreaterEqual(len(refresh_calls), 1)
        finally:
            window.deleteLater()

    def test_vlm_result_logs_requested_returned_and_missing_parts(self):
        window = self._make_window()
        try:
            project_dir = self.project_dir / "coverage_log_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            image_path = project_dir / "specimen.png"
            Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            window.project.add_images([str(image_path)])
            image_key = window.project.project_data["images"][0]
            window.current_image = image_key
            window.canvas.load_image(str(image_path))
            window.vlm_preannotation_total_images = 1
            window.vlm_preannotation_completed_images = 0
            window.vlm_preannotation_total_steps = 6
            window.vlm_preannotation_completed_steps = 3
            window.vlm_preannotation_current_image_steps_completed = 3
            window.vlm_preannotation_current_image = str(image_path)
            window.vlm_preannotation_target_parts = ["Head", "Eye", "Mandible"]
            window.vlm_preannotation_records = []
            window.vlm_preannotation_saved_total = 0
            log_lines = []
            window.log = lambda message: log_lines.append(str(message))

            window.engine.predict_base_sam_polygon = lambda *_args, **_kwargs: None
            window._on_vlm_preannotation_image_result(
                {
                    "status": "passed",
                    "image_path": str(image_path),
                    "target_parts": ["Head", "Eye", "Mandible"],
                    "candidates": [
                        {
                            "part": "Head",
                            "box_xyxy": [10.0, 12.0, 50.0, 44.0],
                            "confidence": 0.8,
                            "reason": "visible head",
                        }
                    ],
                    "report_path": str(project_dir / "vlm_report.json"),
                }
            )

            coverage_lines = [line for line in log_lines if "VLM part coverage" in line]
            self.assertEqual(len(coverage_lines), 1)
            self.assertIn("requested [Head, Eye, Mandible]", coverage_lines[0])
            self.assertIn("returned [Head]", coverage_lines[0])
            self.assertIn("missing [Eye, Mandible]", coverage_lines[0])
        finally:
            window.deleteLater()

    def test_vlm_no_candidate_result_logs_all_requested_parts_missing(self):
        window = self._make_window()
        try:
            image_path = self.project_dir / "specimen.png"
            Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)
            window.project.add_images([str(image_path)])
            window.current_image = str(image_path)
            window.vlm_preannotation_total_images = 1
            window.vlm_preannotation_completed_images = 0
            window.vlm_preannotation_total_steps = 6
            window.vlm_preannotation_completed_steps = 3
            window.vlm_preannotation_current_image_steps_completed = 3
            window.vlm_preannotation_current_image = str(image_path)
            window.vlm_preannotation_target_parts = ["Head", "Eye"]
            window.vlm_preannotation_records = []
            window.vlm_preannotation_saved_total = 0
            log_lines = []
            window.log = lambda message: log_lines.append(str(message))

            window._on_vlm_preannotation_image_result(
                {
                    "status": "passed",
                    "image_path": str(image_path),
                    "target_parts": ["Head", "Eye"],
                    "candidates": [],
                    "report_path": str(self.project_dir / "vlm_report.json"),
                }
            )

            coverage_lines = [line for line in log_lines if "VLM part coverage" in line]
            self.assertEqual(len(coverage_lines), 1)
            self.assertIn("requested [Head, Eye]", coverage_lines[0])
            self.assertIn("returned [none]", coverage_lines[0])
            self.assertIn("missing [Head, Eye]", coverage_lines[0])
        finally:
            window.deleteLater()

    def test_vlm_result_repaints_canvas_while_progress_dialog_is_open(self):
        window = self._make_window()
        try:
            project_dir = self.project_dir / "visible_refresh_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            image_path = project_dir / "specimen.png"
            Image.new("RGB", (120, 80), color=(36, 38, 40)).save(image_path)
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            window.project.add_images([str(image_path)])
            image_key = window.project.project_data["images"][0]
            window.current_image = image_key
            window.canvas.resize(360, 240)
            window.canvas.load_image(str(image_path))
            window.refresh_file_list()
            window.vlm_preannotation_total_images = 1
            window.vlm_preannotation_completed_images = 0
            window.vlm_preannotation_total_steps = 6
            window.vlm_preannotation_completed_steps = 3
            window.vlm_preannotation_current_image_steps_completed = 3
            window.vlm_preannotation_current_image = str(image_path)
            window.vlm_preannotation_records = []
            window.vlm_preannotation_saved_total = 0
            window._create_vlm_progress_dialog()

            window.engine.predict_base_sam_polygon = lambda *_args, **_kwargs: [
                [20, 20],
                [80, 20],
                [80, 60],
                [20, 60],
            ]
            window._on_vlm_preannotation_image_result(
                {
                    "status": "passed",
                    "image_path": str(image_path),
                    "candidates": [
                        {
                            "part": "Head",
                            "box_xyxy": [20.0, 20.0, 80.0, 60.0],
                            "confidence": 0.8,
                            "reason": "visible head",
                        }
                    ],
                    "report_path": str(project_dir / "vlm_report.json"),
                }
            )

            self.assertEqual(window.canvas.vlm_boxes["Head"], [20.0, 20.0, 80.0, 60.0])
            self.assertEqual(len(window.canvas.polygons["Head"]), 4)
            pixmap = window.canvas.grab()
            image = pixmap.toImage()
            colored_pixels = 0
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    if color.red() > 170 and color.blue() > 200 and 45 <= color.green() <= 140:
                        colored_pixels += 1
            self.assertGreater(colored_pixels, 20)
        finally:
            if getattr(window, "vlm_preannotation_progress_dialog", None) is not None:
                window.vlm_preannotation_progress_dialog.close()
                window.vlm_preannotation_progress_dialog.deleteLater()
                window.vlm_preannotation_progress_dialog = None
            window.deleteLater()

    def test_vlm_preannotation_scope_can_target_split_crop_group(self):
        window = self._make_window()
        try:
            original_image = self.project_dir / "plate.png"
            crop_image = self.project_dir / "plate__crop_001.jpg"
            manual_image = self.project_dir / "manual_plate.png"
            for path in [original_image, crop_image, manual_image]:
                Image.new("RGB", (32, 32), "white").save(path)
            window.project.add_images([str(original_image), str(crop_image), str(manual_image)])
            window.project.set_image_provenance(
                str(crop_image),
                {
                    "source_type": "image_crop",
                    "derived_from": {"image_path": str(original_image), "crop_index": 1},
                },
                save=False,
            )
            window._set_panel_split_review(str(manual_image), "manual_required", reason="hard_seam_panel_split")
            window.project.set_vlm_preannotation_settings(
                {
                    "target_parts": ["Head"],
                    "processing_scope": "image_group",
                    "image_group": "split",
                },
                save=False,
            )
            window.current_image = str(original_image)

            batch_paths = window._vlm_image_paths_for_scope(window._current_vlm_batch_scope())
            self.assertEqual(len(batch_paths), 1)
            self.assertTrue(_same_path(batch_paths[0], crop_image))
            current_paths = window._vlm_image_paths_for_scope("current_image")
            self.assertEqual(len(current_paths), 1)
            self.assertTrue(_same_path(current_paths[0], original_image))
            self.assertEqual(window.btn_vlm_preannotate_current.objectName(), "workbenchVlmPreannotateCurrentButton")
            self.assertEqual(window.btn_vlm_preannotate_batch.objectName(), "workbenchVlmPreannotateBatchButton")
            groups = window._project_image_groups()
            self.assertEqual([Path(path).name for path in groups["original"]], [original_image.name])
            self.assertEqual([Path(path).name for path in groups["split"]], [crop_image.name])
            self.assertEqual([Path(path).name for path in groups["manual"]], [manual_image.name])
        finally:
            window.deleteLater()

    def test_vlm_result_updates_workbench_without_file_list_rebuild(self):
        window = self._make_window()
        try:
            project_dir = self.project_dir / "blocked_selection_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            image_path = project_dir / "specimen.png"
            Image.new("RGB", (120, 80), color=(36, 38, 40)).save(image_path)
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            window.project.add_images([str(image_path)])
            image_key = window.project.project_data["images"][0]
            window.current_image = image_key
            window.canvas.resize(360, 240)
            window.canvas.load_image(str(image_path))
            window.refresh_file_list()
            window.vlm_preannotation_total_images = 1
            window.vlm_preannotation_completed_images = 0
            window.vlm_preannotation_total_steps = 6
            window.vlm_preannotation_completed_steps = 3
            window.vlm_preannotation_current_image_steps_completed = 3
            window.vlm_preannotation_current_image = str(image_path)
            window.vlm_preannotation_records = []
            window.vlm_preannotation_saved_total = 0

            window.engine.predict_base_sam_polygon = lambda *_args, **_kwargs: [
                [20, 20],
                [80, 20],
                [80, 60],
                [20, 60],
            ]

            with patch.object(window, "refresh_file_list", wraps=window.refresh_file_list) as full_refresh:
                window._on_vlm_preannotation_image_result(
                    {
                        "status": "passed",
                        "image_path": str(image_path),
                        "candidates": [
                            {
                                "part": "Head",
                                "box_xyxy": [20.0, 20.0, 80.0, 60.0],
                                "confidence": 0.8,
                                "reason": "visible head",
                            }
                        ],
                        "report_path": str(project_dir / "vlm_report.json"),
                    }
                )
                full_refresh.assert_not_called()

            self.assertEqual(window.canvas.vlm_boxes["Head"], [20.0, 20.0, 80.0, 60.0])
            self.assertEqual(len(window.canvas.polygons["Head"]), 4)
        finally:
            window.deleteLater()

    def test_vlm_auto_box_is_painted_after_refresh(self):
        window = self._make_window()
        try:
            project_dir = self.project_dir / "paint_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            image_path = project_dir / "specimen.png"
            Image.new("RGB", (120, 80), color=(40, 42, 44)).save(image_path)
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            window.project.add_images([str(image_path)])
            image_key = window.project.project_data["images"][0]
            window.current_image = image_key
            window.canvas.resize(360, 240)
            window.canvas.load_image(str(image_path))
            window.project.update_auto_box(
                image_key,
                "Head",
                [20, 20, 80, 60],
                source_meta={"source": "vlm_first_mile", "review_status": "draft"},
                save=False,
            )

            window._refresh_vlm_canvas_if_current(image_key)

            self.assertEqual(window.canvas.vlm_boxes["Head"], [20.0, 20.0, 80.0, 60.0])
            pixmap = window.canvas.grab()
            image = pixmap.toImage()
            vlm_pixels = 0
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    if color.red() > 170 and color.blue() > 200 and 45 <= color.green() <= 140:
                        vlm_pixels += 1
            self.assertGreater(vlm_pixels, 20)
        finally:
            window.deleteLater()

    def test_vlm_candidate_writes_box_and_polygon_without_progress_dialog_reentry(self):
        window = self._make_window()
        try:
            image_path = self.project_dir / "specimen.png"
            Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)
            window.project.add_images([str(image_path)])
            image_key = window.project.project_data["images"][0]

            def fake_sam(*_args, **_kwargs):
                return [[10, 12], [50, 12], [50, 44], [10, 44]]

            window.engine.predict_base_sam_polygon = fake_sam
            ok, mode = window._apply_vlm_candidate(
                image_key,
                None,
                {
                    "part": "Head",
                    "box_xyxy": [10.0, 12.0, 50.0, 44.0],
                    "confidence": 0.8,
                    "reason": "visible head",
                },
                {"report_path": str(self.project_dir / "vlm_report.json")},
            )

            self.assertTrue(ok)
            self.assertEqual(mode, "polygon")
            self.assertEqual(window.project.get_auto_boxes(image_key)["Head"], [10.0, 12.0, 50.0, 44.0])
            self.assertEqual(len(window.project.get_labels(image_key)["Head"]), 4)
        finally:
            window.deleteLater()

    def test_vlm_grid_box_is_mapped_before_sam_prompt(self):
        from AntSleap.core.vlm_preannotation import parse_vlm_response

        window = self._make_window()
        try:
            image_path = self.project_dir / "large_specimen.png"
            Image.new("RGB", (1200, 800), color=(140, 150, 160)).save(image_path)
            window.project.add_images([str(image_path)])
            image_key = window.project.project_data["images"][0]
            raw_response = json.dumps(
                {
                    "detections": [
                        {
                            "part": "Head",
                            "bbox_grid_xyxy": [1, 2, 4, 5],
                            "confidence": 0.82,
                        }
                    ]
                }
            )
            candidates, _rejected, _parsed = parse_vlm_response(
                raw_response,
                ["Head"],
                image_size=(1200, 800),
                overlay_size=(600, 400),
                grid_cols=8,
                grid_rows=8,
                min_confidence=0.25,
                default_coordinate_space="grid",
            )
            captured_boxes = []

            def fake_sam(_image_rgb, prompt_box, **_kwargs):
                captured_boxes.append(list(prompt_box))
                return [[150, 200], [600, 200], [600, 500], [150, 500]]

            window.engine.predict_base_sam_polygon = fake_sam
            ok, mode = window._apply_vlm_candidate(
                image_key,
                None,
                candidates[0],
                {"report_path": str(self.project_dir / "vlm_report.json")},
            )

            self.assertTrue(ok)
            self.assertEqual(mode, "polygon")
            self.assertEqual(captured_boxes, [[150.0, 200.0, 600.0, 500.0]])
            self.assertEqual(window.project.get_auto_boxes(image_key)["Head"], [150.0, 200.0, 600.0, 500.0])
            mapping = candidates[0]["coordinate_mapping"]
            self.assertEqual(mapping["source_box"], [1.0, 2.0, 4.0, 5.0])
            self.assertEqual(mapping["coordinate_space"], "grid")
            self.assertEqual(mapping["grid_cols"], 8)
            self.assertEqual(mapping["grid_rows"], 8)
        finally:
            window.deleteLater()

    def test_refresh_file_list_restores_selection_with_project_relative_path(self):
        window = self._make_window()
        try:
            project_dir = self.project_dir / "relative_selection_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            image_path = project_dir / "specimen.png"
            Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            window.project.add_images([str(image_path)])

            window.current_image = os.path.relpath(str(image_path), str(project_dir))
            window.refresh_file_list()

            self.assertIsNotNone(window.file_list.currentItem())
            self.assertTrue(
                window._same_project_image_path(
                    window.file_list.currentItem().data(main_module.Qt.UserRole),
                    str(image_path.resolve()),
                )
            )
        finally:
            window.deleteLater()

    def test_bulk_image_import_uses_background_progress_thread(self):
        window = self._make_window()
        try:
            project_dir = self.project_dir / "bulk_import_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            image_paths = []
            for index in range(main_module.BACKGROUND_IMAGE_IMPORT_THRESHOLD):
                image_path = project_dir / f"specimen_{index:03d}.png"
                Image.new("RGB", (16, 16), color=(index, 90, 120)).save(image_path)
                image_paths.append(str(image_path))

            starts = []

            class FakeImportThread:
                def __init__(self, project, paths):
                    self.project = project
                    self.paths = list(paths)
                    self.progress_signal = SmokeSignal()
                    self.success_signal = SmokeSignal()
                    self.error_signal = SmokeSignal()
                    self.finished_signal = SmokeSignal()
                    self.deleted = False
                    starts.append(self)

                def isRunning(self):
                    return False

                def start(self):
                    added = self.project.add_images(
                        self.paths,
                        progress_callback=lambda done, total, label: self.progress_signal.emit(done, total, label),
                    )
                    self.success_signal.emit(added, len(self.paths))
                    self.finished_signal.emit()

                def deleteLater(self):
                    self.deleted = True

            with patch.object(main_module, "ImageImportThread", FakeImportThread):
                started = window._start_image_import(image_paths)

            self.assertTrue(started)
            self.assertEqual(len(starts), 1)
            self.assertEqual(starts[0].paths, image_paths)
            self.assertTrue(starts[0].deleted)
            self.assertIsNone(window.image_import_thread)
            self.assertIsNone(window.image_import_progress_dialog)
            self.assertEqual(len(window.project.project_data["images"]), len(image_paths))
            self.assertEqual(window.label_project_images.text(), f"PROJECT IMAGES (0/{len(image_paths)})")
        finally:
            window.deleteLater()

    def test_external_batch_inference_uses_background_thread_and_single_save(self):
        window = self._make_window()
        try:
            project_dir = self.project_dir / "external_batch_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            window.project.project_data["taxonomy"] = ["Head"]
            image_paths = []
            for index in range(3):
                image_path = project_dir / f"specimen_{index:03d}.png"
                Image.new("RGB", (16, 16), color=(index, 90, 120)).save(image_path)
                image_paths.append(str(image_path))
            window.project.add_images(image_paths, save=False)
            window.model_backend = main_module.EXTERNAL_BACKEND_ID

            starts = []
            saved_before = window.project.current_project_path
            save_calls = []
            original_save = window.project.save_project

            def counted_save():
                save_calls.append("save")
                return original_save()

            window.project.save_project = counted_save

            class FakeExternalBatchThread:
                def __init__(self, project, backend_config, paths, model_manifest="", lang="en"):
                    self.project = project
                    self.backend_config = dict(backend_config)
                    self.paths = list(paths)
                    self.model_manifest = model_manifest
                    self.lang = lang
                    self.log_signal = SmokeSignal()
                    self.progress_signal = SmokeSignal()
                    self.result_signal = SmokeSignal()
                    self.error_signal = SmokeSignal()
                    self.finished_signal = SmokeSignal()
                    self.deleted = False
                    self._running = False
                    starts.append(self)

                def isRunning(self):
                    return self._running

                def start(self):
                    self._running = True
                    for index, path in enumerate(self.paths, start=1):
                        self.progress_signal.emit(index - 1, len(self.paths), path)
                        self.result_signal.emit(
                            path,
                            {
                                "payload": {
                                    "polygons": {"Head": [[1, 1], [8, 1], [8, 8]]},
                                    "auto_boxes": {"Head": [1, 1, 8, 8]},
                                }
                            },
                        )
                        self.progress_signal.emit(index, len(self.paths), path)
                    self._running = False
                    self.finished_signal.emit()

                def deleteLater(self):
                    self.deleted = True

            with patch.object(main_module, "_runtime_parent_backend", lambda *_args, **_kwargs: main_module.EXTERNAL_BACKEND_ID), \
                 patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes), \
                 patch.object(main_module, "ExternalBatchInferenceThread", FakeExternalBatchThread):
                window.run_batch_inference()

            self.assertEqual(window.project.current_project_path, saved_before)
            self.assertEqual(len(starts), 1)
            self.assertEqual(starts[0].paths, image_paths)
            self.assertTrue(starts[0].deleted)
            self.assertIsNone(window.external_batch_inference_thread)
            self.assertIsNone(window.external_batch_inference_progress_dialog)
            self.assertEqual(save_calls, ["save"])
            for image_path in image_paths:
                self.assertIn("Head", window.project.get_labels(image_path))
                self.assertEqual(window.project.project_data["labels"][image_path]["descriptions"]["Head"], "Auto-Annotated")
        finally:
            window.deleteLater()

    def test_remove_selected_images_uses_batch_project_remove(self):
        window = self._make_window()
        try:
            project_dir = self.project_dir / "batch_remove_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            image_paths = []
            for index in range(4):
                image_path = project_dir / f"candidate_{index:03d}.png"
                Image.new("RGB", (16, 16), color=(index, 90, 120)).save(image_path)
                image_paths.append(str(image_path))
            window.project.add_images(image_paths, save=False)
            window.current_image = image_paths[0]
            window.refresh_file_list()

            for index in range(window.file_list.count()):
                item = window.file_list.item(index)
                path = item.data(main_module.Qt.UserRole)
                if path in image_paths[:3]:
                    item.setSelected(True)

            save_calls = []
            original_save = window.project.save_project

            def counted_save():
                save_calls.append("save")
                return original_save()

            window.project.save_project = counted_save

            with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):
                window.remove_selected_images()

            self.assertEqual(save_calls, [])
            self.assertTrue(window.project_save_pending)
            self.assertEqual(window.project.project_data["images"], [image_paths[3]])
            self.assertNotIn(image_paths[0], window.project.project_data["labels"])
            self.assertEqual(window.current_image, image_paths[3])
        finally:
            window.deleteLater()

    def test_external_training_uses_background_thread(self):
        window = self._make_window()
        try:
            project_dir = self.project_dir / "external_training_project"
            project_dir.mkdir(parents=True, exist_ok=True)
            window.project.create_project("review", str(project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            starts = []

            class FakeExternalTrainingThread:
                def __init__(self, project, backend_config):
                    self.project = project
                    self.backend_config = dict(backend_config)
                    self.log_signal = SmokeSignal()
                    self.success_signal = SmokeSignal()
                    self.error_signal = SmokeSignal()
                    self.finished_signal = SmokeSignal()
                    self.deleted = False
                    self._running = False
                    starts.append(self)

                def isRunning(self):
                    return self._running

                def start(self):
                    self._running = True
                    self.log_signal.emit("External backend training started.")
                    self.success_signal.emit(
                        {
                            "contract_json": str(project_dir / "external_runs" / "contract.json"),
                            "model_manifest": str(project_dir / "external_runs" / "model_manifest.json"),
                        }
                    )
                    self._running = False
                    self.finished_signal.emit()

                def deleteLater(self):
                    self.deleted = True

            with patch.object(main_module, "ExternalTrainingThread", FakeExternalTrainingThread):
                window.run_external_training()

            self.assertEqual(len(starts), 1)
            self.assertTrue(starts[0].deleted)
            self.assertIsNone(window.external_training_thread)
            self.assertTrue(window.btn_train.isEnabled())
            self.assertFalse(window.btn_stop_training.isEnabled())
            self.assertEqual(window.progress.value(), 100)
        finally:
            window.deleteLater()

    def test_pdf_evidence_tools_open_on_demand(self):
        window = self._make_window()
        try:
            window.enter_image_workflow()
            self.assertEqual(window.tabs.count(), 1)
            window.open_pdf_evidence_tools()
            self.assertEqual(window.tabs.currentWidget(), window.pdf_widget)
            self.assertEqual(window.tabs.tabText(window.tabs.currentIndex()), "PDF Evidence Tools")
            self.assertEqual(window.tabs.count(), 2)
            self.assertEqual(window.pdf_widget.btn_start_center.text(), "Start Center")
            self.assertEqual(window.pdf_widget.btn_ask_agent.text(), "Ask Agent")
            self.assertIsNotNone(getattr(main_module, "LiteratureDescriptionDialog", None))
            self.assertEqual(window.pdf_widget.lbl_ext_db.text(), "Result Folder:")
            self.assertEqual(window.pdf_widget.btn_db.text(), "Choose Result Folder")
            self.assertIn("_v2_artifacts", window.pdf_widget.edit_db_path.toolTip())
            self.assertEqual(window.pdf_widget.lbl_ext_db_name.text(), "Database File:")
            self.assertEqual(window.pdf_widget.edit_db_name.text(), "taxamask_literature.db")
            self.assertEqual(window.pdf_widget.btn_browse_db.text(), "Open Database File")
            result_dir = self.project_dir / "pdf_results"
            result_dir.mkdir()
            window.pdf_widget.edit_out_folder.setText(str(result_dir))
            self.assertEqual(
                Path(window.pdf_widget._resolve_extract_db_path("")),
                result_dir / "taxamask_literature.db",
            )
            self.assertEqual(
                Path(window.pdf_widget._resolve_extract_db_path(str(result_dir))),
                result_dir / "taxamask_literature.db",
            )
            self.assertEqual(
                Path(window.pdf_widget._resolve_extract_db_path(str(result_dir / "custom.db"))),
                result_dir / "custom.db",
            )
            window.pdf_widget.edit_db_name.setText("named_run")
            self.assertEqual(
                Path(window.pdf_widget._resolve_extract_db_path(str(result_dir))),
                result_dir / "named_run.db",
            )
            selected_db = result_dir / "selected_review.db"
            selected_db.write_bytes(b"")
            opened = []

            class DummyDatabaseViewer:
                def __init__(self, db_path, *_args, **_kwargs):
                    opened.append(Path(db_path))

                def exec(self):
                    return None

            with patch.object(pdf_widget_module.QFileDialog, "getOpenFileName", return_value=(str(selected_db), "SQLite DB (*.db)")), \
                 patch.object(pdf_widget_module, "DatabaseViewerDialog", DummyDatabaseViewer):
                window.pdf_widget.browse_database()

            self.assertEqual(opened, [selected_db])
            self.assertEqual(Path(window.pdf_widget.edit_db_path.text()), result_dir)
            self.assertEqual(window.pdf_widget.edit_db_name.text(), "selected_review.db")
            window.pdf_widget.edit_out_folder.clear()
            window.pdf_widget.edit_ext_src.clear()
            window.pdf_widget.edit_db_path.clear()
            window.pdf_widget.edit_db_name.setText("taxamask_literature.db")
            self.assertEqual(
                Path(window.pdf_widget._resolve_extract_db_path("")),
                PROJECT_ROOT / "TaxaMask_outputs" / "pdf_extraction" / "taxamask_literature.db",
            )
            context = window.pdf_widget.get_agent_context()
            self.assertEqual(
                context["settings_question_focus"],
                "stage_1_confirm_pdf_keys_models_with_short_requirement_questions_only",
            )
            self.assertEqual(context["text_llm_key_configured"], "no")
            self.assertEqual(context["text_llm_model"], "gpt-5.4")
            self.assertEqual(context["extract_db_name"], "taxamask_literature.db")
            self.assertEqual(
                Path(context["extract_db_path"]),
                PROJECT_ROOT / "TaxaMask_outputs" / "pdf_extraction" / "taxamask_literature.db",
            )
            window.pdf_widget.edit_api_key.setText("secret-not-sent")
            window.pdf_widget.edit_mllm_api_key.setText("vision-secret-not-sent")
            context = window.pdf_widget.get_agent_context()
            self.assertEqual(context["text_llm_key_configured"], "yes")
            self.assertEqual(context["multimodal_llm_key_configured"], "yes")
            self.assertNotIn("secret-not-sent", str(context))
            self.assertNotIn("vision-secret-not-sent", str(context))
            self.assertEqual(
                context["settings_question_focus"],
                "stage_1_confirm_pdf_keys_models_with_short_requirement_questions_only",
            )
            prompt = window._pdf_agent_prompt()
            self.assertIn("key、base URL、model", prompt)
            self.assertIn("四个阶段", prompt)
            self.assertIn("每轮只处理当前阶段", prompt)
            self.assertIn("最多问 3 个问题", prompt)
            self.assertIn("需求确认式交互", prompt)
            self.assertNotIn("规划时请覆盖这些点", prompt)
        finally:
            window.deleteLater()

    def test_pdf_database_viewer_paginates_figure_records(self):
        db_path = self.project_dir / "paged_figures.db"
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE figure_records (
                    id INTEGER PRIMARY KEY,
                    image_file_name TEXT,
                    image_file_path TEXT,
                    final_confidence REAL,
                    accepted INTEGER,
                    page_number INTEGER,
                    species_candidate TEXT
                )
                """
            )
            for idx in range(1, 8):
                (self.project_dir / f"fig_{idx}.png").write_bytes(f"image-{idx}".encode("utf-8"))
                cur.execute(
                    """
                    INSERT INTO figure_records
                        (id, image_file_name, image_file_path, final_confidence, accepted, page_number, species_candidate)
                    VALUES (?, ?, ?, 0.9, 1, ?, ?)
                    """,
                    (idx, f"fig_{idx}.png", str(self.project_dir / f"fig_{idx}.png"), idx, f"Species {idx}"),
                )
            conn.commit()
        finally:
            conn.close()

        dialog = pdf_widget_module.DatabaseViewerDialog(str(db_path), lang="en")
        try:
            dialog.page_size_edit.setText("3")
            dialog.apply_page_controls()
            self.assertEqual(dialog.total_rows, 7)
            self.assertEqual(dialog.total_pages, 3)
            self.assertEqual(dialog.table.rowCount(), 3)
            self.assertEqual(dialog.table.item(0, 0).text(), "7")
            self.assertIn("Showing 1-3 of 7 | Page 1/3", dialog.page_status.text())

            dialog.goto_page(2)
            self.assertEqual(dialog.table.item(0, 0).text(), "4")
            self.assertIn("Showing 4-6 of 7 | Page 2/3", dialog.page_status.text())

            dialog.goto_page(3)
            self.assertEqual(dialog.table.rowCount(), 1)
            self.assertEqual(dialog.table.item(0, 0).text(), "1")
            self.assertFalse(dialog.btn_next.isEnabled())
            self.assertTrue(dialog.btn_prev.isEnabled())

            dialog.search_edit.setText("Species 6")
            dialog.apply_filters()
            self.assertEqual(dialog.total_rows, 1)
            self.assertEqual(dialog.table.item(0, 0).text(), "6")

            dialog.table.selectRow(0)
            dialog.human_status_buttons["human_rejected"].setChecked(True)
            dialog.review_note_edit.setText("good dorsal plate")
            dialog.save_current_review()

            def saved_review_row():
                conn = sqlite3.connect(db_path)
                try:
                    return conn.execute(
                        "SELECT human_status, review_note FROM figure_human_reviews WHERE source_table='figure_records' AND record_id=6"
                    ).fetchone()
                finally:
                    conn.close()

            self.assertTrue(self._wait_until(lambda: saved_review_row() == ("human_rejected", "good dorsal plate")))
            row = saved_review_row()
            self.assertEqual(row, ("human_rejected", "good dorsal plate"))

            dialog.search_edit.clear()
            dialog.apply_filters()
            with patch.object(pdf_widget_module, "themed_yes_no_question", return_value=pdf_widget_module.QMessageBox.Yes), \
                 patch.object(pdf_widget_module.QMessageBox, "information"):
                dialog.mark_filtered_import_ready()
            conn = sqlite3.connect(db_path)
            try:
                statuses = dict(
                    conn.execute(
                        "SELECT record_id, human_status FROM figure_human_reviews WHERE source_table='figure_records'"
                    ).fetchall()
                )
                rejected_note = conn.execute(
                    "SELECT review_note FROM figure_human_reviews WHERE source_table='figure_records' AND record_id=6"
                ).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(statuses[6], "human_rejected")
            self.assertEqual(rejected_note, "good dorsal plate")
            self.assertEqual(
                {record_id: status for record_id, status in statuses.items() if record_id != 6},
                {1: "import_ready", 2: "import_ready", 3: "import_ready", 4: "import_ready", 5: "import_ready", 7: "import_ready"},
            )

            dialog.search_edit.setText("Species 6")
            with patch.object(pdf_widget_module, "themed_yes_no_question", return_value=pdf_widget_module.QMessageBox.No):
                dialog.clear_filters()
            self.assertEqual(dialog.search_edit.text(), "Species 6")
            with patch.object(pdf_widget_module, "themed_yes_no_question", return_value=pdf_widget_module.QMessageBox.Yes):
                dialog.clear_filters()
            self.assertEqual(dialog.search_edit.text(), "")

            dialog.search_edit.setText("Species 6")
            dialog.apply_filters()
            export_path = self.project_dir / "filtered.csv"
            with patch.object(pdf_widget_module.QFileDialog, "getSaveFileName", return_value=(str(export_path), "CSV (*.csv)")), \
                 patch.object(pdf_widget_module.QMessageBox, "information"):
                dialog.export_filtered_csv()
            self.assertIn("Species 6", export_path.read_text(encoding="utf-8-sig"))

            copy_dir = self.project_dir / "copied"
            copy_dir.mkdir()
            with patch.object(pdf_widget_module.QFileDialog, "getExistingDirectory", return_value=str(copy_dir)), \
                 patch.object(pdf_widget_module.QMessageBox, "information"):
                dialog.copy_filtered_images()
            self.assertTrue((copy_dir / "fig_6.png").exists())
        finally:
            dialog.deleteLater()

    def test_pdf_candidate_crop_inherits_parent_provenance(self):
        window = self._make_window()
        try:
            parent_image = self.project_dir / "paper__accepted_000007__figure.jpg"
            crop_image = self.project_dir / "paper__accepted_000007__figure__crop_001.jpg"
            parent_image.write_bytes(b"parent")
            crop_image.write_bytes(b"crop")
            window.project.add_images([str(parent_image), str(crop_image)])
            parent_provenance = {
                "source_type": "pdf_candidate",
                "source_db": str(self.project_dir / "literature.db"),
                "source_ref": {"table": "figure_records", "row_id": 7},
                "pdf_id": 3,
                "pdf_file": "paper.pdf",
                "species_candidate": "Aphaenogaster gamagumayaa",
            }
            window.project.set_image_provenance(str(parent_image), parent_provenance, save=False)

            window._inherit_crop_provenance(
                [
                    {
                        "path": str(crop_image),
                        "source_image": str(parent_image),
                        "crop_index": 1,
                        "crop_box": [10, 20, 80, 100],
                        "source_size": [160, 120],
                    }
                ]
            )

            crop_provenance = window.project.get_image_provenance(str(crop_image))
            self.assertEqual(crop_provenance["source_type"], "pdf_candidate_crop")
            self.assertEqual(crop_provenance["source_ref"]["row_id"], 7)
            self.assertEqual(crop_provenance["species_candidate"], "Aphaenogaster gamagumayaa")
            self.assertEqual(crop_provenance["derived_from"]["crop_box"], [10, 20, 80, 100])
            self.assertTrue(window._is_pdf_candidate_provenance(crop_provenance))
            self.assertEqual(
                window.project.get_image_provenance(str(parent_image))["panel_split_review"]["status"],
                "manual_done",
            )
        finally:
            window.deleteLater()

    def test_plain_image_crop_gets_traceable_provenance_for_grouping(self):
        window = self._make_window()
        try:
            parent_image = self.project_dir / "plain_plate.png"
            crop_image = self.project_dir / "plain_plate__panel_001.jpg"
            parent_image.write_bytes(b"parent")
            crop_image.write_bytes(b"crop")
            window.project.add_images([str(parent_image), str(crop_image)])

            window._inherit_crop_provenance(
                [
                    {
                        "path": str(crop_image),
                        "source_image": str(parent_image),
                        "crop_index": 1,
                        "crop_box": [0, 0, 50, 50],
                        "source_size": [100, 100],
                        "crop_source": "white_separator_panel_split",
                    }
                ]
            )

            crop_provenance = window.project.get_image_provenance(str(crop_image))
            self.assertEqual(crop_provenance["source_type"], "image_crop")
            self.assertTrue(_same_path(crop_provenance["derived_from"]["image_path"], parent_image))
            self.assertEqual(crop_provenance["derived_from"]["crop_source"], "white_separator_panel_split")
            self.assertTrue(window._is_split_crop_image(str(crop_image)))
        finally:
            window.deleteLater()

    def test_crop_from_manual_required_parent_leaves_manual_queue(self):
        window = self._make_window()
        try:
            parent_image = self.project_dir / "manual_plate.png"
            crop_image = self.project_dir / "manual_plate__crop_001.jpg"
            parent_image.write_bytes(b"parent")
            crop_image.write_bytes(b"crop")
            window.project.add_images([str(parent_image), str(crop_image)])
            window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")

            window._inherit_crop_provenance(
                [
                    {
                        "path": str(crop_image),
                        "source_image": str(parent_image),
                        "crop_index": 1,
                        "crop_box": [0, 0, 50, 50],
                        "source_size": [100, 100],
                        "crop_source": "hard_seam_panel_split",
                    }
                ]
            )

            parent_review = window.project.get_image_provenance(str(parent_image))["panel_split_review"]
            crop_provenance = window.project.get_image_provenance(str(crop_image))
            self.assertEqual(parent_review["status"], "manual_done")
            self.assertNotIn("panel_split_review", crop_provenance)
            self.assertFalse(window._needs_manual_panel_split(str(parent_image)))
            self.assertFalse(window._needs_manual_panel_split(str(crop_image)))

            window.refresh_file_list()
            list_texts = [window.file_list.item(index).text().strip() for index in range(window.file_list.count())]
            self.assertFalse(any("Manual Split Needed" in text for text in list_texts))
            self.assertTrue(any("Hard-joined Candidates" in text for text in list_texts))
        finally:
            window.deleteLater()

    def test_existing_crop_from_manual_required_parent_is_not_manual_queue(self):
        window = self._make_window()
        try:
            parent_image = self.project_dir / "legacy_manual_plate.png"
            crop_image = self.project_dir / "legacy_manual_plate__crop_001.jpg"
            parent_image.write_bytes(b"parent")
            crop_image.write_bytes(b"crop")
            window.project.add_images([str(parent_image), str(crop_image)])
            window.project.set_image_provenance(
                str(crop_image),
                {
                    "source_type": "image_crop",
                    "derived_from": {"image_path": str(parent_image), "crop_index": 1},
                },
                save=False,
            )
            window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")

            self.assertTrue(window._has_split_crops_from_image(str(parent_image)))
            self.assertFalse(window._needs_manual_panel_split(str(parent_image)))
            self.assertFalse(window._needs_manual_panel_split(str(crop_image)))

            window.refresh_file_list()
            list_texts = [window.file_list.item(index).text().strip() for index in range(window.file_list.count())]
            self.assertFalse(any("Manual Split Needed" in text for text in list_texts))
            self.assertTrue(any("Split Crops" in text for text in list_texts))
            self.assertIn(crop_image.name, list_texts)
        finally:
            window.deleteLater()

    def test_user_can_adjust_panel_split_status_from_image_list(self):
        window = self._make_window()
        try:
            image_path = self.project_dir / "status_plate.png"
            image_path.write_bytes(b"image")
            window.project.add_images([str(image_path)])
            window.refresh_file_list()
            for index in range(window.file_list.count()):
                item = window.file_list.item(index)
                if _same_path(item.data(256), image_path):
                    window.file_list.setCurrentItem(item)
                    break

            window.mark_selected_manual_split_needed()
            self.assertTrue(window._needs_manual_panel_split(str(image_path)))
            window.refresh_file_list()
            list_texts = [window.file_list.item(index).text().strip() for index in range(window.file_list.count())]
            self.assertTrue(any("Manual Split Needed" in text for text in list_texts))

            window.mark_selected_manual_split_done()
            self.assertFalse(window._needs_manual_panel_split(str(image_path)))
            self.assertEqual(
                window.project.get_image_provenance(str(image_path))["panel_split_review"]["status"],
                "manual_done",
            )
            window.refresh_file_list()
            list_texts = [window.file_list.item(index).text().strip() for index in range(window.file_list.count())]
            self.assertFalse(any("Manual Split Needed" in text for text in list_texts))
            self.assertTrue(any("Manual Split Done" in text for text in list_texts))

            window.clear_selected_split_status()
            self.assertNotIn("panel_split_review", window.project.get_image_provenance(str(image_path)))
        finally:
            window.deleteLater()

    def test_multi_selected_manual_split_done_moves_to_done_group(self):
        window = self._make_window()
        try:
            image_a = self.project_dir / "manual_a.png"
            image_b = self.project_dir / "manual_b.png"
            image_a.write_bytes(b"a")
            image_b.write_bytes(b"b")
            window.project.add_images([str(image_a), str(image_b)])
            window._set_panel_split_review(str(image_a), "manual_required", reason="hard_seam_panel_split")
            window._set_panel_split_review(str(image_b), "manual_required", reason="hard_seam_panel_split")
            window.refresh_file_list()

            for index in range(window.file_list.count()):
                item = window.file_list.item(index)
                if _same_path(item.data(256), image_a) or _same_path(item.data(256), image_b):
                    item.setSelected(True)

            window.mark_selected_manual_split_done()

            groups = window._project_image_groups()
            self.assertEqual(
                {Path(path).name for path in groups["manual_done"]},
                {image_a.name, image_b.name},
            )
            self.assertEqual(groups["manual"], [])
            list_texts = [window.file_list.item(index).text().strip() for index in range(window.file_list.count())]
            self.assertTrue(any("Manual Split Done" in text for text in list_texts))
            self.assertFalse(any("Manual Split Needed" in text for text in list_texts))
        finally:
            window.deleteLater()

    def test_manual_done_images_can_be_moved_into_split_group(self):
        window = self._make_window()
        try:
            image_path = self.project_dir / "manual_done_plate.png"
            image_path.write_bytes(b"image")
            window.project.add_images([str(image_path)])
            window._set_panel_split_review(str(image_path), "manual_done", reason="user_marked_done")

            self.assertEqual([Path(path).name for path in window._project_image_groups()["manual_done"]], [image_path.name])

            window.move_images_to_group([str(image_path)], "split")
            groups = window._project_image_groups()
            self.assertEqual([Path(path).name for path in groups["split"]], [image_path.name])
            self.assertEqual(groups["manual_done"], [])
            self.assertEqual(
                window.project.get_image_provenance(str(image_path))["manual_image_group"],
                "split",
            )
        finally:
            window.deleteLater()

    def test_custom_image_group_can_collect_images_and_feed_vlm_scope(self):
        window = self._make_window()
        try:
            image_a = self.project_dir / "review_a.png"
            image_b = self.project_dir / "review_b.png"
            image_a.write_bytes(b"a")
            image_b.write_bytes(b"b")
            window.project.add_images([str(image_a), str(image_b)])
            window.project.project_data["image_groups"] = {
                "custom_groups": [{"id": "review_ready", "name": "Review Ready"}]
            }

            window.move_images_to_group([str(image_b)], "review_ready")

            groups = window._project_image_groups()
            self.assertEqual([Path(path).name for path in groups["review_ready"]], [image_b.name])
            self.assertEqual([Path(path).name for path in groups["original"]], [image_a.name])
            self.assertEqual(window._vlm_image_group_label("review_ready"), "Review Ready")

            window.project.set_vlm_preannotation_settings(
                {
                    "target_parts": ["Head"],
                    "processing_scope": "image_group",
                    "image_group": "review_ready",
                },
                save=False,
            )
            self.assertEqual(window._current_vlm_image_group(), "review_ready")
            paths = window._vlm_image_paths_for_scope("image_group")
            self.assertEqual(len(paths), 1)
            self.assertTrue(_same_path(paths[0], image_b))
        finally:
            window.deleteLater()

    def test_labeled_images_sort_to_top_within_custom_image_group(self):
        window = self._make_window()
        try:
            image_a = self.project_dir / "review_unlabeled_a.png"
            image_b = self.project_dir / "review_labeled_b.png"
            image_c = self.project_dir / "review_unlabeled_c.png"
            image_a.write_bytes(b"a")
            image_b.write_bytes(b"b")
            image_c.write_bytes(b"c")
            window.project.add_images([str(image_a), str(image_b), str(image_c)])
            window.project.project_data["image_groups"] = {
                "custom_groups": [{"id": "review_ready", "name": "Review Ready"}]
            }
            window.move_images_to_group([str(image_a), str(image_b), str(image_c)], "review_ready")
            window.project.update_label(
                str(image_b),
                "Head",
                [[1, 1], [4, 1], [4, 4]],
                "reviewed",
                save=False,
            )

            groups = window._project_image_groups()

            self.assertEqual(
                [Path(path).name for path in groups["review_ready"]],
                [image_b.name, image_a.name, image_c.name],
            )
        finally:
            window.deleteLater()

    def test_empty_custom_image_group_is_removed_from_move_targets(self):
        window = self._make_window()
        try:
            image_a = self.project_dir / "review_a.png"
            image_b = self.project_dir / "review_b.png"
            image_a.write_bytes(b"a")
            image_b.write_bytes(b"b")
            window.project.add_images([str(image_a), str(image_b)])
            window.project.project_data["image_groups"] = {
                "custom_groups": [{"id": "review_ready", "name": "Review Ready"}]
            }
            window.project.project_data["vlm_preannotation"] = {
                "target_parts": [],
                "processing_scope": "image_group",
                "image_group": "review_ready",
            }

            window.move_images_to_group([str(image_b)], "review_ready")
            self.assertIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})

            window.move_images_to_group([str(image_b)], "original")

            self.assertEqual(window._custom_image_group_definitions(), [])
            self.assertEqual(window.project.project_data["image_groups"]["custom_groups"], [])
            self.assertNotIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})
            self.assertEqual(window.project.get_vlm_preannotation_settings()["image_group"], "split")
        finally:
            window.deleteLater()

    def test_file_list_context_menu_shows_new_group_at_top_level_only(self):
        window = self._make_window()
        try:
            image_a = self.project_dir / "menu_a.png"
            image_b = self.project_dir / "menu_b.png"
            Image.new("RGB", (16, 16), color=(120, 80, 40)).save(image_a)
            Image.new("RGB", (16, 16), color=(40, 120, 80)).save(image_b)
            window.project.add_images([str(image_a), str(image_b)])
            window.project.project_data["image_groups"] = {
                "custom_groups": [
                    {"id": "filled_group", "name": "Filled Group"},
                    {"id": "empty_group", "name": "Empty Group"},
                ]
            }
            window.move_images_to_group([str(image_b)], "filled_group")
            window.refresh_file_list()
            for index in range(window.file_list.count()):
                item = window.file_list.item(index)
                if item.data(main_module.Qt.UserRole) and _same_path(item.data(main_module.Qt.UserRole), image_a):
                    window.file_list.setCurrentItem(item)
                    break

            captured_menus = []

            class FakeMenu:
                def __init__(self, *args, **kwargs):
                    self.title = ""
                    self.entries = []
                    captured_menus.append(self)

                def addAction(self, text, *args, **kwargs):
                    self.entries.append(("action", str(text), None))
                    return None

                def addSeparator(self):
                    self.entries.append(("separator", "", None))
                    return None

                def addMenu(self, text):
                    menu = FakeMenu()
                    menu.title = str(text)
                    self.entries.append(("menu", str(text), menu))
                    return menu

                def exec(self, *args, **kwargs):
                    return None

            with patch.object(main_module, "QMenu", FakeMenu):
                window.show_file_list_context_menu(window.file_list.rect().center())

            root_menu = captured_menus[0]
            top_level_actions = [text for kind, text, _menu in root_menu.entries if kind == "action"]
            self.assertIn("New Image Group", top_level_actions)
            move_menu = next(menu for kind, text, menu in root_menu.entries if kind == "menu" and text == "Move to Image Group")
            move_actions = [text for kind, text, _menu in move_menu.entries if kind == "action"]
            self.assertNotIn("New Image Group", move_actions)
            self.assertIn("Filled Group", move_actions)
            self.assertNotIn("Empty Group", move_actions)
        finally:
            window.deleteLater()

    def test_legacy_panel_crop_filename_is_grouped_as_split_crop(self):
        window = self._make_window()
        try:
            parent_image = self.project_dir / "legacy_plate.png"
            crop_image = self.project_dir / "legacy_plate__panel_001.jpg"
            unrelated_crop = self.project_dir / "orphan_plate__panel_001.jpg"
            parent_image.write_bytes(b"parent")
            crop_image.write_bytes(b"crop")
            unrelated_crop.write_bytes(b"orphan")
            window.project.add_images([str(parent_image), str(crop_image), str(unrelated_crop)])

            self.assertTrue(window._is_split_crop_image(str(crop_image)))
            self.assertFalse(window._is_split_crop_image(str(unrelated_crop)))

            window.refresh_file_list()
            list_texts = [window.file_list.item(index).text().strip() for index in range(window.file_list.count())]
            self.assertTrue(any("Split Crops" in text for text in list_texts))
            split_index = next(index for index, text in enumerate(list_texts) if "Split Crops" in text)
            self.assertGreater(list_texts.index(crop_image.name), split_index)
        finally:
            window.deleteLater()

    def test_batch_panel_split_adds_white_and_hard_seam_candidate_crops(self):
        window = self._make_window()
        try:
            parent_image = self.project_dir / "paper__accepted_000008__figure.jpg"
            image = Image.new("RGB", (420, 260), "white")
            image.paste((118, 92, 70), (0, 0, 200, 260))
            image.paste((188, 194, 184), (220, 0, 420, 260))
            image.save(parent_image)

            hard_seam_image = self.project_dir / "paper__accepted_000009__figure.jpg"
            hard_image = Image.new("RGB", (420, 260), (118, 92, 70))
            hard_image.paste((188, 194, 184), (210, 0, 420, 260))
            hard_image.save(hard_seam_image)

            existing_crop = self.project_dir / "paper__accepted_000008__figure__crop_999.jpg"
            Image.new("RGB", (64, 64), (120, 120, 120)).save(existing_crop)
            window.project.add_images([str(parent_image), str(hard_seam_image), str(existing_crop)])
            window.project.set_image_provenance(
                str(parent_image),
                {
                    "source_type": "pdf_candidate",
                    "source_ref": {"table": "figure_records", "row_id": 8},
                    "species_candidate": "Aphaenogaster test",
                },
                save=False,
            )
            window.project.set_image_provenance(
                str(existing_crop),
                {
                    "source_type": "pdf_candidate_crop",
                    "derived_from": {"image_path": str(parent_image), "crop_index": 999},
                },
                save=False,
            )

            with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):
                with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):
                    window.batch_split_panel_images()

            images = list(window.project.project_data["images"])
            self.assertTrue(_same_path(images[0], parent_image))
            self.assertTrue(_same_path(images[1], hard_seam_image))
            self.assertTrue(_same_path(images[2], existing_crop))
            generated_paths = images[3:]
            self.assertGreaterEqual(len(generated_paths), 3)
            white_generated = [
                generated
                for generated in generated_paths
                if Path(generated).name.startswith("paper__accepted_000008__figure__panel_")
            ]
            hard_generated = [
                generated
                for generated in generated_paths
                if Path(generated).name.startswith("paper__accepted_000009__figure__panel_")
            ]
            self.assertGreaterEqual(len(white_generated), 1)
            self.assertEqual(len(hard_generated), 2)
            for generated in white_generated:
                self.assertTrue(Path(generated).name.startswith("paper__accepted_000008__figure__panel_"))
                provenance = window.project.get_image_provenance(generated)
                self.assertEqual(provenance["source_type"], "pdf_candidate_crop")
                self.assertEqual(provenance["derived_from"]["crop_source"], "white_separator_panel_split")
                self.assertTrue(window._is_split_crop_image(generated))
                self.assertFalse(window._needs_manual_panel_split(generated))
            for generated in hard_generated:
                provenance = window.project.get_image_provenance(generated)
                self.assertEqual(provenance["source_type"], "image_crop")
                self.assertEqual(provenance["derived_from"]["crop_source"], "hard_seam_panel_split")
                self.assertTrue(window._is_split_crop_image(generated))
                self.assertFalse(window._needs_manual_panel_split(generated))
            hard_review = window.project.get_image_provenance(str(hard_seam_image))["panel_split_review"]
            self.assertEqual(hard_review["status"], "candidate_split")
            self.assertEqual(hard_review["reason"], "hard_seam_panel_split_candidate")

            groups = window._project_image_groups()
            self.assertEqual({Path(path).name for path in groups["hard_candidates"]}, {Path(path).name for path in hard_generated})
            self.assertFalse(any(Path(path).name in {Path(item).name for item in hard_generated} for path in groups["split"]))

            list_texts = [window.file_list.item(index).text().strip() for index in range(window.file_list.count())]
            original_index = next(index for index, text in enumerate(list_texts) if "Original Images" in text)
            split_index = next(index for index, text in enumerate(list_texts) if "Split Crops" in text)
            hard_index = next(index for index, text in enumerate(list_texts) if "Hard-joined Candidates" in text)
            self.assertLess(original_index, split_index)
            self.assertLess(split_index, hard_index)
            for generated in white_generated:
                self.assertGreater(list_texts.index(Path(generated).name), split_index)
                self.assertLess(list_texts.index(Path(generated).name), hard_index)
            for generated in hard_generated:
                self.assertGreater(list_texts.index(Path(generated).name), hard_index)
            self.assertFalse(any("Manual Split Needed" in text for text in list_texts))
        finally:
            window.deleteLater()

    def test_batch_panel_split_does_not_force_equal_grid_from_labels(self):
        window = self._make_window()
        try:
            source_image = self.project_dir / "letter_guided_plate.jpg"
            image = Image.new("RGB", (520, 420), (152, 168, 145))
            draw = ImageDraw.Draw(image)
            try:
                font = ImageFont.truetype("arial.ttf", 34)
            except Exception:
                font = ImageFont.load_default(size=34)
            fills = [
                (126, 104, 78),
                (185, 172, 132),
                (92, 118, 96),
                (164, 150, 112),
            ]
            for row in range(2):
                for col in range(2):
                    x0 = col * 260
                    y0 = row * 210
                    draw.rectangle((x0, y0, x0 + 259, y0 + 209), fill=fills[row * 2 + col])
                    draw.ellipse((x0 + 80, y0 + 55, x0 + 205, y0 + 160), fill=(80 + row * 30, 68 + col * 28, 48))
            for letter, pos in zip("ABCD", [(12, 10), (272, 10), (12, 220), (272, 220)]):
                draw.text(pos, letter, fill=(255, 255, 255), font=font)
            image.save(source_image)
            window.project.add_images([str(source_image)])

            with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):
                with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):
                    window.batch_split_panel_images()

            generated_paths = list(window.project.project_data["images"])[1:]
            self.assertEqual(generated_paths, [])
            source_review = window.project.get_image_provenance(str(source_image))["panel_split_review"]
            self.assertEqual(source_review["status"], "skipped")
            self.assertEqual(source_review["reason"], "no_split_detected")
            groups = window._project_image_groups()
            self.assertEqual(groups["hard_candidates"], [])
        finally:
            window.deleteLater()

    def test_literature_context_prefers_image_artifact_db_over_current_pdf_widget_db(self):
        window = self._make_window()
        try:
            right_db = self.project_dir / "right_run.db"
            wrong_db = self.project_dir / "wrong_run.db"
            source_image = self.project_dir / "right_run_v2_artifacts" / "figure_images" / "paper_source.png"
            exported_image = self.project_dir / "right_run_v2_artifacts" / "accepted_figures" / "paper__accepted_000007__paper_source.png"
            source_image.parent.mkdir(parents=True)
            exported_image.parent.mkdir(parents=True)
            source_image.write_bytes(b"source")
            exported_image.write_bytes(b"exported")

            self._create_literature_db(right_db, source_image, pdf_id=3, figure_id=7)
            stats_dir = self.project_dir / "right_run_v2_artifacts" / "stats"
            stats_dir.mkdir(parents=True)
            with open(stats_dir / "paper_import_ready_figures.csv", "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "pdf_file_id",
                        "figure_id",
                        "status",
                        "pdf_name",
                        "page_number",
                        "species_candidate",
                        "final_confidence",
                        "category",
                        "review_status",
                        "source_image_path",
                        "exported_image_path",
                        "exported_image_name",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "pdf_file_id": 3,
                        "figure_id": 7,
                        "status": "accepted",
                        "pdf_name": "paper.pdf",
                        "page_number": 2,
                        "species_candidate": "Aphaenogaster gamagumayaa",
                        "final_confidence": 0.91,
                        "category": "taxonomic",
                        "review_status": "accepted",
                        "source_image_path": str(source_image),
                        "exported_image_path": str(exported_image),
                        "exported_image_name": exported_image.name,
                    }
                )

            wrong_image = self.project_dir / "wrong_run_v2_artifacts" / "accepted_figures" / exported_image.name
            wrong_image.parent.mkdir(parents=True)
            wrong_image.write_bytes(b"wrong")
            self._create_literature_db(wrong_db, wrong_image, pdf_id=9, figure_id=7, species="Wrong species")

            window.project.add_images([str(exported_image)])
            window.current_image = str(exported_image)
            window.pdf_widget.edit_db_path.setText(str(wrong_db))

            db_path, context, reason = window._resolve_current_literature_context()

            self.assertEqual(Path(db_path), right_db)
            self.assertEqual(reason, "")
            self.assertTrue(context["available"])
            self.assertEqual(context["pdf_file_id"], 3)
            self.assertEqual(context["species_candidate"], "Aphaenogaster gamagumayaa")
        finally:
            window.deleteLater()

    def test_manual_image_can_reference_same_taxon_literature_db(self):
        window = self._make_window()
        try:
            output_db = self.project_dir / "TaxaMask_outputs" / "pdf_extraction" / "taxamask_literature.db"
            output_db.parent.mkdir(parents=True, exist_ok=True)
            literature_image = self.project_dir / "paper_source.jpg"
            manual_image = self.project_dir / "manual_camera_image.jpg"
            literature_image.write_bytes(b"literature")
            manual_image.write_bytes(b"manual")
            self._create_literature_db(output_db, literature_image)
            window.pdf_widget.edit_db_path.setText(str(output_db))

            window.project.project_data["images"] = [str(manual_image)]
            window.project.project_data["labels"] = {
                str(manual_image): {
                    "parts": {},
                    "descriptions": {},
                    "taxon": "Aphaenogaster gamagumayaa",
                    "genus": "Aphaenogaster gamagumayaa",
                }
            }
            window.current_image = str(manual_image)
            window.genus_combo.addItem("Aphaenogaster gamagumayaa")
            window.genus_combo.setCurrentText("Aphaenogaster gamagumayaa")

            db_path, context, reason = window._resolve_current_literature_context()

            self.assertEqual(Path(db_path), output_db)
            self.assertEqual(reason, "")
            self.assertTrue(context["available"])
            self.assertEqual(context["species_candidate"], "Aphaenogaster gamagumayaa")
            self.assertEqual(context["link_mode"], "taxon_match_not_image_provenance")
            self.assertIsNone(context["figure_id"])
        finally:
            window.deleteLater()

    def test_manual_image_finds_literature_db_from_other_project_pdf_image(self):
        window = self._make_window()
        try:
            literature_db = self.project_dir / "pdf_results" / "custom_literature.db"
            literature_db.parent.mkdir(parents=True, exist_ok=True)
            literature_image = self.project_dir / "paper_source.jpg"
            manual_image = self.project_dir / "manual_camera_image.jpg"
            literature_image.write_bytes(b"literature")
            manual_image.write_bytes(b"manual")
            self._create_literature_db(literature_db, literature_image)

            window.pdf_widget.edit_db_path.clear()
            window.pdf_widget.edit_db_name.setText("taxamask_literature.db")
            window.project.project_data["images"] = [str(literature_image), str(manual_image)]
            window.project.project_data["labels"] = {
                str(literature_image): {"parts": {}, "descriptions": {}},
                str(manual_image): {
                    "parts": {},
                    "descriptions": {},
                    "taxon": "Aphaenogaster gamagumayaa",
                    "genus": "Aphaenogaster gamagumayaa",
                },
            }
            window.project.set_image_provenance(
                str(literature_image),
                {
                    "source_type": "pdf_candidate",
                    "source_db": str(literature_db),
                    "source_ref": {"table": "figure_records", "row_id": 7},
                    "species_candidate": "Aphaenogaster gamagumayaa",
                },
                save=False,
            )
            window.current_image = str(manual_image)
            window.genus_combo.addItem("Aphaenogaster gamagumayaa")
            window.genus_combo.setCurrentText("Aphaenogaster gamagumayaa")

            db_path, context, reason = window._resolve_current_literature_context()

            self.assertEqual(Path(db_path), literature_db)
            self.assertEqual(reason, "")
            self.assertTrue(context["available"])
            self.assertEqual(context["link_mode"], "taxon_match_not_image_provenance")
        finally:
            window.deleteLater()

    def test_manual_image_can_choose_literature_db_when_auto_paths_are_missing(self):
        window = self._make_window()
        try:
            literature_db = self.project_dir / "external_pdf_results" / "chosen_literature.db"
            literature_db.parent.mkdir(parents=True, exist_ok=True)
            literature_image = self.project_dir / "paper_source.jpg"
            manual_image = self.project_dir / "manual_camera_image.jpg"
            literature_image.write_bytes(b"literature")
            manual_image.write_bytes(b"manual")
            self._create_literature_db(literature_db, literature_image)

            window.pdf_widget.edit_db_path.clear()
            window.pdf_widget.edit_db_name.setText("taxamask_literature.db")
            window.project.project_data["images"] = [str(manual_image)]
            window.project.project_data["labels"] = {
                str(manual_image): {
                    "parts": {},
                    "descriptions": {},
                    "taxon": "Aphaenogaster gamagumayaa",
                    "genus": "Aphaenogaster gamagumayaa",
                },
            }
            window.current_image = str(manual_image)
            window.genus_combo.addItem("Aphaenogaster gamagumayaa")
            window.genus_combo.setCurrentText("Aphaenogaster gamagumayaa")

            with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(str(literature_db), "SQLite Database (*.db)")):
                db_path, context, reason = window._choose_literature_db_for_current_taxon()

            self.assertEqual(Path(db_path), literature_db)
            self.assertEqual(reason, "")
            self.assertTrue(context["available"])
            self.assertEqual(context["link_mode"], "taxon_match_not_image_provenance")
            self.assertEqual(Path(window.pdf_widget.edit_db_path.text()), literature_db.parent)
            self.assertEqual(window.pdf_widget.edit_db_name.text(), literature_db.name)
        finally:
            window.deleteLater()

    def test_literature_dialog_exposes_structured_and_raw_text_layers(self):
        context = {
            "source_db": str(self.project_dir / "literature.db"),
            "pdf_file_id": 3,
            "pdf_file": "paper.pdf",
            "species_candidate": "Aphaenogaster gamagumayaa",
        }
        structured = [
            {
                "taxon_name": "Aphaenogaster gamagumayaa",
                "caste_or_stage": "worker",
                "part_label": "触角/柄节",
                "part_key": "antenna_scape",
                "source_pages": [4],
                "source_block_refs": ["p004_b0009"],
                "confidence": 0.91,
                "review_status": "auto_extracted",
                "description_text": "Scapes elongate and slim.",
            }
        ]
        raw = [
            {
                "file_name": "paper.pdf",
                "page_number": 4,
                "block_ref": "p004_b0009",
                "llm_taxon_name": "Aphaenogaster gamagumayaa",
                "llm_role": "morphological_description",
                "llm_confidence": 0.82,
                "text_content": "Scape is remarkably elongate in workers.",
            }
        ]

        with patch.object(main_module, "query_literature_part_descriptions", return_value=structured), \
             patch.object(main_module, "query_literature_text_blocks", return_value=raw):
            dialog = main_module.LiteratureDescriptionDialog(
                db_path=str(self.project_dir / "literature.db"),
                context=context,
                image_path=str(self.project_dir / "image.jpg"),
                current_part="scape",
                taxon_hint="Aphaenogaster gamagumayaa",
                parent=None,
                lang="en",
            )
        try:
            self.assertEqual(dialog.result_tabs.tabText(0), "Structured Descriptions")
            self.assertEqual(dialog.result_tabs.tabText(1), "Raw Text Blocks")
            self.assertEqual(dialog.raw_scope_combo.itemText(0), "Current Taxon First")
            self.assertEqual(dialog.btn_replace.text(), "Replace Current Description")
            self.assertEqual(dialog.btn_append.text(), "Append to Current Description")
            self.assertEqual(dialog.table.rowCount(), 1)
            self.assertEqual(dialog.raw_table.rowCount(), 1)
            dialog.result_tabs.setCurrentWidget(dialog.raw_table)
            self.assertIn("remarkably elongate", dialog.selected_description_text())
            self.assertEqual(dialog.selected_source()["source"], "pdf_text_block")
        finally:
            dialog.deleteLater()

    def test_literature_dialog_chinese_action_buttons_are_explicit(self):
        context = {
            "source_db": str(self.project_dir / "literature.db"),
            "pdf_file_id": 3,
            "pdf_file": "paper.pdf",
            "species_candidate": "Aphaenogaster gamagumayaa",
        }
        with patch.object(main_module, "query_literature_part_descriptions", return_value=[]), \
             patch.object(main_module, "query_literature_text_blocks", return_value=[]):
            dialog = main_module.LiteratureDescriptionDialog(
                db_path=str(self.project_dir / "literature.db"),
                context=context,
                image_path=str(self.project_dir / "image.jpg"),
                current_part="scape",
                taxon_hint="Aphaenogaster gamagumayaa",
                parent=None,
                lang="zh",
            )
        try:
            self.assertEqual(dialog.btn_replace.text(), "替换当前描述")
            self.assertEqual(dialog.btn_append.text(), "追加到当前描述末尾")
        finally:
            dialog.deleteLater()

    def test_pdf_multimodal_same_as_text_shows_effective_text_settings(self):
        window = self._make_window()
        try:
            window.open_pdf_evidence_tools()
            widget = window.pdf_widget
            widget.edit_api_key.setText("text-key")
            widget.edit_base_url.setText("https://example.test/v1")
            widget.edit_model.setText("gpt-5.4")
            responses_index = widget.combo_api_protocol.findData("responses")
            widget.combo_api_protocol.setCurrentIndex(responses_index)
            widget.chk_remember_api_key.setChecked(True)
            widget.check_mllm_same_as_text.setChecked(False)
            widget.edit_mllm_api_key.setText("old-vision-key")
            widget.edit_mllm_base_url.setText("https://old-vision.test/v1")
            widget.edit_mllm_model.setText("old-vision-model")

            widget.check_mllm_same_as_text.setChecked(True)
            self.app.processEvents()

            self.assertEqual(widget.edit_mllm_api_key.text(), "text-key")
            self.assertEqual(widget.edit_mllm_base_url.text(), "https://example.test/v1")
            self.assertEqual(widget.edit_mllm_model.text(), "gpt-5.4")
            self.assertEqual(widget.combo_mllm_api_protocol.currentData(), "responses")
            self.assertTrue(widget.chk_remember_mllm_api_key.isChecked())
            config = widget._current_multimodal_api_settings()
            self.assertEqual(config["api_key"], "text-key")
            self.assertEqual(config["base_url"], "https://example.test/v1")
            self.assertEqual(config["model"], "gpt-5.4")
            context = widget.get_agent_context()
            self.assertEqual(context["multimodal_llm_uses_text_provider"], "yes")
            self.assertEqual(context["multimodal_llm_model"], "gpt-5.4")
            self.assertEqual(context["multimodal_llm_api_protocol"], "responses")
        finally:
            window.deleteLater()

    def test_multimodal_connection_test_uses_nontrivial_generated_png(self):
        worker = LLMConnectionTestWorker(
            "multimodal",
            {"api_key": "k", "base_url": "https://example.test/v1", "model": "vision"},
        )
        prefix = "data:image/png;base64,"
        self.assertTrue(worker.test_image_data_url.startswith(prefix))
        png = base64.b64decode(worker.test_image_data_url[len(prefix):])
        image = Image.open(io.BytesIO(png))
        self.assertEqual(image.size, (128, 96))
        self.assertGreater(len(png), 200)
        self.assertGreaterEqual(worker.TEST_MAX_OUTPUT_TOKENS, 256)
        self.assertNotIn("JSON", str(worker._vision_content_chat()))

    def test_connection_test_accepts_reasoning_content_when_chat_content_is_empty(self):
        worker = LLMConnectionTestWorker(
            "multimodal",
            {"api_key": "k", "base_url": "https://example.test/v1", "model": "vision"},
        )
        text, finish_reason = worker._extract_chat_completions_text(
            {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "content": "",
                            "reasoning_content": "The image shows a red square and a blue circle.",
                        },
                    }
                ]
            }
        )

        self.assertEqual(finish_reason, "length")
        self.assertIn("red square", text)
        self.assertGreaterEqual(worker.TEST_MAX_OUTPUT_TOKENS, 1024)

    def test_stl_project_open_path_registers_views_into_labeling_workbench(self):
        window = self._make_window()
        try:
            preload_events = []
            window.ensure_sam_preloaded = lambda: preload_events.append("preload")
            source = self.project_dir / "stl_source"
            source.mkdir()
            Image.new("RGB", (32, 24), "red").save(source / "01_0101_02_dorsal.png")

            stl_project = StlRenderedProjectManager()
            stl_path = stl_project.create_project("stl_smoke", self.project_dir / "stl_smoke")
            stl_project.import_rendered_view_directory(source, copy_files=True, known_views=["dorsal"])
            (self.project_dir / "review").mkdir()
            window.project.create_project("review", str(self.project_dir / "review"), template_id=PROJECT_TEMPLATE_GENERIC)

            self.assertTrue(window._is_stl_project_file(stl_path))
            with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(stl_path, "JSON (*.json)")):
                window.open_project()

            self.assertEqual(window.active_project_kind, "image")
            self.assertEqual(window.tabs.currentWidget(), window.workbench_widget)
            self.assertEqual(window.tabs.count(), 1)
            self.assertEqual(len(window.project.project_data["images"]), 1)
            image_path = window.project.project_data["images"][0]
            provenance = window.project.get_image_provenance(image_path)
            self.assertEqual(provenance["source_type"], "stl_rendered_view")
            self.assertEqual(window.project.project_data["labels"][image_path]["review_mode"], "stl_rendered_view")
            self.assertEqual(window._active_recent_project_path(), os.path.abspath(stl_path))
            self.assertEqual(window.config.values["last_project_path"], os.path.abspath(stl_path))
            context = window._collect_image_workbench_agent_context()
            self.assertEqual(context["project_source_kind"], "stl")
            self.assertEqual(context["project_path"], os.path.abspath(stl_path))
            self.assertEqual(context["review_project_path"], window.project.current_project_path)
            self.assertIn("STL rendered-view project", window._start_console_project_summary()[0])
            self.assertIn("1 STL rendered 2D view", window._start_console_image_summary()[0])
            self.assertEqual(preload_events, ["preload"])
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)
        finally:
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
