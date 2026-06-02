# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

import os
import base64
import io
import sys
import tempfile
import sqlite3
import csv
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

has_pyside6 = False

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
    from PIL import Image

    import AntSleap.main as main_module
    import AntSleap.ui.pdf_processing_widget as pdf_widget_module
    from AntSleap.core.project_templates import PROJECT_TEMPLATE_GENERIC
    from AntSleap.core.stl_project import StlRenderedProjectManager
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget, LLMConnectionTestWorker

    has_pyside6 = True


class SmokeConfigManager:
    def __init__(self):
        self.values = {
            "language": "en",
            "runtime_device": "cpu",
            "theme": "dark",
            "last_project_path": "",
            "tif_backend": {
                "backend_id": "custom_tif_backend",
                "display_name": "TIF Volume Backend",
                "python_executable": "python",
                "prepare_dataset_command": "",
                "train_command": "",
                "predict_command": "",
                "model_manifest": "",
                "export_formats": "ome_tiff,nrrd,mha,nifti",
            },
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
            self.assertIsNotNone(window.findChild(main_module.QWidget, "startTifWorkflowCard"))
            self.assertIsNotNone(window.findChild(main_module.QWidget, "startProjectConsole"))
            rail_scroll = window.findChild(main_module.QScrollArea, "startWorkflowRailScroll")
            self.assertIsNotNone(rail_scroll)
            self.assertEqual(rail_scroll.horizontalScrollBarPolicy(), main_module.Qt.ScrollBarAlwaysOff)
            self.assertEqual(rail_scroll.verticalScrollBarPolicy(), main_module.Qt.ScrollBarAsNeeded)
            self.assertIsNotNone(window.findChild(main_module.QWidget, "taxamaskAgentPanel"))
            self.assertIn("PDF evidence skill ready", window.start_console_pdf_value.text())
            self.assertIn("STL", window.start_console_stl_note.text())
            self.assertIn("2D views", window.start_console_stl_note.text())
            self.assertNotIn("3D mesh annotation", window.start_console_stl_note.text())
            self.assertEqual(window.btn_start_ant_code.text(), "Start Ant-Code")
            self.assertEqual(window.btn_stop_ant_code.text(), "Stop Ant-Code")
            self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentInlineStatus"))
            self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskStartAntCodeButton"))
            self.assertIn("Workspace permission", window.agent_panel.fallback.toPlainText())
            menu_texts = [
                action.text()
                for menu_action in window.menuBar().actions()
                if menu_action.menu() is not None
                for action in menu_action.menu().actions()
            ]
            self.assertIn("Workflow", [action.text() for action in window.menuBar().actions()])
            self.assertIn("Start Center", menu_texts)
            self.assertIn("2D/STL Morphology Workflow", menu_texts)
            self.assertIn("TIF Volume Workflow", menu_texts)
            self.assertIn("2D/STL Model Settings", menu_texts)
            self.assertIn("TIF Volume Model Settings", menu_texts)
            self.assertNotIn("Language", menu_texts)
            self.assertNotIn("Theme", menu_texts)
            self.assertNotIn("Dark Mode", menu_texts)
            self.assertIn("Check / Relocate Project Images", menu_texts)
            self.assertIn("New TIF Volume Project", menu_texts)
            self.assertNotIn("Import TIF Stack", menu_texts)
            self.assertNotIn("Import AMIRA Directory", menu_texts)
            self.assertIn("Import STL Rendered Views to Labeling Workbench", menu_texts)
            self.assertIn("Open PDF Evidence Tools", menu_texts)
            self.assertNotIn("New STL Rendered-View Project", menu_texts)
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

            window.enter_tif_workflow()
            self.assertEqual(window.active_project_kind, "tif")
            self.assertEqual(window.tabs.count(), 1)
            self.assertEqual(window.tabs.currentWidget(), window.tif_workbench)
            self.assertEqual(window.tabs.tabText(0), "TIF Volume Workbench")
            self.assertEqual(window.tif_workbench.btn_ask_agent.text(), "Ask Agent")
            self.assertEqual(preload_events, ["preload"])
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)
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
            self.assertTrue(window.agent_panel.ant_code_dashboard_entry.endswith(os.path.join("src", "cli", "dashboard.js")))
            self.assertTrue(window.agent_panel.ant_code_config_path.endswith(os.path.join("AntSleap", "config", "taxamask_ant_code.config.json")))
            command = window.agent_panel._dashboard_command()
            self.assertEqual(command[0], window.agent_panel.node_executable)
            self.assertEqual(command[1], window.agent_panel.ant_code_dashboard_entry)
            env = window.agent_panel._dashboard_environment()
            self.assertEqual(env["LAB_AGENT_PACKAGE_ROOT"], window.agent_panel.ant_code_root)
            self.assertEqual(env["LAB_AGENT_CONFIG"], window.agent_panel.ant_code_config_path)
            self.assertIsNotNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentStack"))
            self.assertIn("Ant-Code embedded", window.agent_panel.fallback.toPlainText())
            self.assertIn("TaxaMask source guard", window.agent_panel.fallback.toPlainText())
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
            self.assertNotIn(r"C:\legacy\ant-code.exe", command)
            self.assertNotIn("dashboard", command[:2])
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
                f'"C:\\Program Files\\nodejs\\node.exe" "{dashboard}" --project "{project}" --port 7410 --no-open',
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

    def test_tif_start_center_entry_is_navigation_only(self):
        window = self._make_window()
        try:
            window.tif_project.current_project_path = str(self.project_dir / "tif_project.json")
            window.agent_panel._context = {"source_workbench": "previous"}
            window.enter_tif_workflow()
            window.tif_workbench.current_specimen_id = "ANT_001"
            window.tif_workbench.log("missing manual_truth")
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

    def test_tif_ask_agent_compact_context_keeps_volume_and_reslice_fields(self):
        window = self._make_window()
        try:
            compact = window._compact_agent_context(
                {
                    "source_workbench": "tif_volume",
                    "project_type": "tif_volume",
                    "active_specimen_id": "ANT_001",
                    "display_mode": "volume",
                    "active_slice_axis": "y",
                    "active_slice_position": "3/120",
                    "active_volume_shape_zyx": "300/800/900",
                    "active_volume_spacing_zyx": "2.0/0.5/0.5",
                    "volume_renderer": "gpu",
                    "volume_renderer_label": "GPU ray march [RTX 3090]",
                    "volume_texture_target_dim": "2048",
                    "volume_ray_samples": "2048",
                    "volume_clarity_mode": "on",
                    "volume_inside_depth": "65%",
                    "volume_front_cut": "30%",
                    "volume_yaw_pitch": "yaw=12.0, pitch=18.0",
                    "tif_next_requirement": "brain_orientation_reslice",
                    "tif_requirement_doc": "docs/ant3d_workbench/TIF脑部统一朝向重切片需求_zh.md",
                }
            )

            self.assertEqual(compact["diagnostic_route"], "tif_volume_workbench_context")
            self.assertEqual(compact["display_mode"], "volume")
            self.assertEqual(compact["active_slice_axis"], "y")
            self.assertEqual(compact["volume_renderer"], "gpu")
            self.assertEqual(compact["volume_clarity_mode"], "on")
            self.assertIn("brain_orientation_reslice", compact["tif_next_requirement"])
            self.assertIn("TIF脑部统一朝向重切片需求_zh.md", compact["tif_requirement_doc"])
            self.assertIn("GPU preview", compact["diagnostic_focus"])
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
            self.assertEqual(window.tif_workbench.btn_import_tif.text(), "导入 TIF stack")
            self.assertEqual(window.start_title.text(), "TaxaMask Agent 中心")
            self.assertEqual(window.btn_start_ant_code.text(), "启动 Ant-Code")

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
                    "processing_scope": "all_images",
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

            training_content = dialog.tabs.widget(0).widget()
            inference_content = dialog.tabs.widget(1).widget()
            vlm_panel = dialog.findChild(main_module.QWidget, "modelSettingsVlmPreannotationPanel")
            self.assertIsNotNone(vlm_panel)
            self.assertFalse(has_ancestor(vlm_panel, training_content))
            self.assertTrue(has_ancestor(vlm_panel, inference_content))
            self.assertEqual(dialog.get_values()["vlm_preannotation"]["processing_scope"], "all_images")
            self.assertEqual(
                dialog.get_values()["vlm_preannotation"]["target_parts"],
                ["Mesosoma", "Gaster"],
            )
        finally:
            dialog.deleteLater()

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

    def test_tif_model_settings_match_volume_backend_contract(self):
        dialog = main_module.TifModelSettingsDialog(
            {
                "backend_id": "tif_unet",
                "display_name": "TIF U-Net",
                "python_executable": "C:/Users/admin/anaconda3/envs/antsleap/python.exe",
                "export_formats": "nrrd,mha",
                "prepare_dataset_command": "{python} prepare.py --contract {contract_json}",
                "train_command": "{python} train.py --contract {contract_json}",
                "predict_command": "",
                "model_manifest": "{run_dir}/outputs/model_manifest.json",
            },
            lang="zh",
        )
        try:
            self.assertEqual(dialog.windowTitle(), "TIF 体数据训练设置")
            safety_panel = dialog.findChild(main_module.QWidget, "tifModelSettingsSafetyPanel")
            self.assertIsNotNone(safety_panel)
            self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "tifModelSettingsAskAgentButton"))
            self.assertEqual(dialog._validation_errors(), [])
            values = dialog.get_values()
            self.assertEqual(values["backend_id"], "tif_unet")
            self.assertEqual(values["export_formats"], "nrrd,mha")
            self.assertIn("{contract_json}", values["train_command"])

            dialog.export_formats_edit.setText("nrrd,bad_format")
            self.assertIn("不支持的 TIF 导出格式", "\n".join(dialog._validation_errors()))
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
                context = model_dialog.get_agent_context()
                self.assertEqual(context["settings_scope"], "2d_stl_model")
                self.assertEqual(context["prepare_command_present"], "yes")
                self.assertEqual(context["prepare_command_has_contract"], "yes")
                self.assertEqual(context["train_command_present"], "yes")
                self.assertEqual(context["train_command_has_contract"], "no")
                self.assertNotIn("very-long-private-flag", str(context))

                compact = window._compact_agent_context(context)
                self.assertEqual(compact["source_workbench"], "stl_model_settings")
                self.assertEqual(compact["external_backend_id"], "custom_backend")
                self.assertIn("validation_errors", compact)
                self.assertIn("contract_placeholder_missing", compact["diagnostic_route"])
                self.assertIn("docs/contracts/external_backend_contract_v1.md", compact["source_code_refs"])
                self.assertIn("contract_placeholder=missing", compact["health_check_summary"])
                self.assertLess(len(str(compact)), 5000)
            finally:
                model_dialog.deleteLater()

            tif_dialog = main_module.TifModelSettingsDialog(
                {
                    "backend_id": "nnunet",
                    "display_name": "nnU-Net",
                    "python_executable": "python",
                    "export_formats": "nrrd,mha",
                    "prepare_dataset_command": "python prepare.py --contract {contract_json} --large-config secret",
                    "train_command": "",
                    "predict_command": "python predict.py --contract {contract}",
                    "model_manifest": "",
                },
                lang="en",
                parent=window,
            )
            try:
                context = tif_dialog.get_agent_context()
                self.assertEqual(context["settings_scope"], "tif_volume_backend")
                self.assertEqual(context["backend_id"], "nnunet")
                self.assertEqual(context["predict_command_has_contract"], "yes")
                self.assertNotIn("large-config", str(context))
                self.assertNotIn("predict.py", str(context))
                compact = window._compact_agent_context(context)
                self.assertEqual(compact["diagnostic_route"], "tif_volume_backend_settings")
                self.assertIn("TIF后端契约", compact["source_code_refs"])
                self.assertIn("model_draft", compact["safety_notes"])
            finally:
                tif_dialog.deleteLater()
        finally:
            window.deleteLater()

    def test_tif_model_settings_save_syncs_workbench_defaults(self):
        window = self._make_window()
        try:
            dialog = main_module.TifModelSettingsDialog(window.config.get("tif_backend", {}), lang="en", parent=window)
            try:
                dialog.backend_id_edit.setText("volume_backend")
                dialog.display_name_edit.setText("Volume Backend")
                dialog.python_edit.setText("C:/Python/python.exe")
                dialog.export_formats_edit.setText("nrrd,mha")
                dialog.prepare_command_edit.setPlainText("{python} prepare.py --contract {contract}")
                dialog.train_command_edit.setPlainText("")
                dialog.predict_command_edit.setPlainText("")
                backend_config = dialog.get_values()
            finally:
                dialog.deleteLater()

            window.config.set("tif_backend", dict(backend_config))
            window.tif_workbench.set_config_manager(window.config)

            self.assertEqual(window.config.values["tif_backend"]["backend_id"], "volume_backend")
            self.assertEqual(window.tif_workbench.backend_id_edit.text(), "volume_backend")
            self.assertEqual(window.tif_workbench.backend_formats_edit.text(), "nrrd,mha")
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
            self.assertEqual(preload_events, ["preload"])
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)
        finally:
            window.deleteLater()

    def test_new_project_dialogs_default_to_output_roots(self):
        window = self._make_window()
        try:
            preload_events = []
            window.ensure_2d_stl_models_preloaded = lambda: preload_events.append("preload")
            image_root = self.project_dir / "TaxaMask_outputs" / "2d_stl_projects"
            tif_root = self.project_dir / "TaxaMask_outputs" / "tif_projects"
            created_image_dir = image_root / "review_run"
            created_tif_dir = tif_root / "volume_run"
            calls = []

            def fake_get_existing_directory(_parent, title, start_dir=""):
                calls.append((title, Path(start_dir)))
                if "TIF" in title:
                    created_tif_dir.mkdir(parents=True, exist_ok=True)
                    return str(created_tif_dir)
                created_image_dir.mkdir(parents=True, exist_ok=True)
                return str(created_image_dir)

            with patch.object(main_module.QFileDialog, "getExistingDirectory", fake_get_existing_directory), \
                 patch.object(main_module.QInputDialog, "getText", side_effect=[("review", True), ("volume", True)]), \
                 patch.object(window, "_choose_project_template", return_value={"template_id": PROJECT_TEMPLATE_GENERIC}):
                window.new_project()
                window.new_tif_project()

            self.assertEqual(calls[0][1], image_root)
            self.assertEqual(calls[1][1], tif_root)
            self.assertEqual(Path(window.project.current_project_path), created_image_dir / "review.json")
            self.assertEqual(Path(window.tif_project.current_project_path), created_tif_dir / "project.json")
            self.assertTrue((created_image_dir / "review.json").exists())
            self.assertTrue((created_tif_dir / "project.json").exists())
            self.assertEqual(preload_events, ["preload"])
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

    def test_tif_project_open_path_switches_to_tif_workbench(self):
        window = self._make_window()
        try:
            preload_events = []
            window.ensure_sam_preloaded = lambda: preload_events.append("preload")
            tif_project = TifProjectManager()
            tif_path = tif_project.create_project("tif_smoke", self.project_dir / "tif_smoke")

            self.assertTrue(window._is_tif_project_file(tif_path))
            window.tif_project.load_project(tif_path)
            window.active_project_kind = "tif"
            window._refresh_project_bound_views()

            self.assertEqual(window.tabs.count(), 1)
            self.assertEqual(window.tabs.currentWidget(), window.tif_workbench)
            self.assertEqual(window.tabs.tabText(0), "TIF Volume Workbench")
            self.assertEqual(window.tif_project.project_data["project_type"], "tif_volume")
            self.assertEqual(preload_events, [])
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)
        finally:
            window.deleteLater()

    def test_tif_project_open_path_does_not_preload_sam(self):
        window = self._make_window()
        try:
            preload_events = []
            window.ensure_sam_preloaded = lambda: preload_events.append("preload")
            tif_project = TifProjectManager()
            tif_path = tif_project.create_project("tif_open_smoke", self.project_dir / "tif_open_smoke")

            window.open_project_path(tif_path)

            self.assertEqual(window.active_project_kind, "tif")
            self.assertEqual(window.tabs.currentWidget(), window.tif_workbench)
            self.assertEqual(preload_events, [])
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)
        finally:
            window.deleteLater()

    def test_tif_training_export_defaults_to_project_exports(self):
        window = self._make_window()
        try:
            tif_project = TifProjectManager()
            tif_path = tif_project.create_project("tif_export_defaults", self.project_dir / "tif_export_defaults")
            window.open_project_path(tif_path)
            expected = self.project_dir / "tif_export_defaults" / "exports" / "train_ready"
            captured = []

            def fake_get_existing_directory(_parent, _title, start_dir=""):
                captured.append(Path(start_dir))
                return ""

            with patch.object(main_module.QFileDialog, "getExistingDirectory", fake_get_existing_directory):
                window.tif_workbench.export_training_dataset()

            self.assertEqual(captured, [expected])
            self.assertTrue(expected.exists())
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
            self.assertEqual(dialog.table.rowCount(), 1)
            self.assertEqual(dialog.raw_table.rowCount(), 1)
            dialog.result_tabs.setCurrentWidget(dialog.raw_table)
            self.assertIn("remarkably elongate", dialog.selected_description_text())
            self.assertEqual(dialog.selected_source()["source"], "pdf_text_block")
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
