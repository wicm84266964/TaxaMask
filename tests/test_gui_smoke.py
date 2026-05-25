# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

import os
import sys
import tempfile
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
    from AntSleap.core.project_templates import PROJECT_TEMPLATE_GENERIC
    from AntSleap.core.stl_project import StlRenderedProjectManager
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget

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
             patch.object(main_module, "SAMWorker", SmokeSamWorker), \
             patch.object(main_module, "QThread", SmokeThread), \
             patch.object(PdfProcessingWidget, "load_api_settings", lambda self: None), \
             patch.object(PdfProcessingWidget, "refresh_profile_list", lambda self: None), \
             patch.object(PdfProcessingWidget, "sync_runtime_controls_from_config", lambda self: None), \
             patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):
            return main_module.MainWindow()

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
            context = window.pdf_widget.get_agent_context()
            self.assertEqual(
                context["settings_question_focus"],
                "stage_1_confirm_pdf_keys_models_with_short_requirement_questions_only",
            )
            self.assertEqual(context["text_llm_key_configured"], "no")
            self.assertEqual(context["text_llm_model"], "gpt-5.4")
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
            self.assertIn("STL rendered-view project", window._start_console_project_summary())
            self.assertIn("1 STL rendered 2D view", window._start_console_image_summary())
            self.assertEqual(preload_events, ["preload"])
            self.assertIsNone(window.sam_worker)
            self.assertIsNone(window.sam_thread)
        finally:
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
