import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FakeSignal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


class MainWindowStage3ShellTests(unittest.TestCase):
    def test_main_window_init_is_shell_composition_only(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        main_window = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MainWindow")
        init_method = next(node for node in main_window.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")

        self.assertLessEqual(init_method.end_lineno - init_method.lineno + 1, 20)
        self.assertIn("self._initialize_main_window_state", source)
        self.assertIn("self._build_main_window_views", source)
        self.assertIn("self._connect_main_window_integrations", source)
        self.assertIn("self._finish_main_window_startup", source)

    def test_main_window_inherits_start_center_and_agent_implementations(self):
        import AntSleap.main as main_module
        from AntSleap.ui.main_window_agent_context import MainWindowAgentContextMixin
        from AntSleap.ui.main_window_start_center import MainWindowStartCenterMixin

        self.assertIs(main_module.MainWindow._compact_agent_context, MainWindowAgentContextMixin._compact_agent_context)
        self.assertIs(main_module.MainWindow._build_start_center, MainWindowStartCenterMixin._build_start_center)
        self.assertIs(main_module.MainWindow.enter_image_workflow, MainWindowAgentContextMixin.enter_image_workflow)

    def test_signal_router_connects_each_key_once(self):
        from AntSleap.ui.main_window_signal_router import MainWindowSignalRouter

        signal = FakeSignal()
        calls = []
        router = MainWindowSignalRouter()

        self.assertTrue(router.connect_once("agent", signal, calls.append))
        self.assertFalse(router.connect_once("agent", signal, calls.append))
        signal.emit("context")
        self.assertEqual(calls, ["context"])
        self.assertEqual(len(signal.slots), 1)

    def test_coordinator_serializes_reentrant_transitions(self):
        from AntSleap.ui.main_window_coordinator import MainWindowCoordinator

        calls = []
        coordinator = None

        def enter_image():
            calls.append("image")
            self.assertFalse(coordinator.enter_image())

        coordinator = MainWindowCoordinator(
            enter_image=enter_image,
            enter_tif=lambda: calls.append("tif"),
            open_agent=lambda context: calls.append(context["route"]),
            return_to_start=lambda: calls.append("start"),
        )

        self.assertTrue(coordinator.enter_image())
        self.assertTrue(coordinator.open_agent({"route": "agent"}))
        self.assertEqual(calls, ["image", "agent"])

    def test_start_center_remembers_last_workbench_for_recent_project(self):
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin
        from AntSleap.ui.main_window_start_center import MainWindowStartCenterMixin

        owner = type(
            "StartOwner",
            (MainWindowStartCenterMixin, MainWindowProjectLifecycleMixin),
            {},
        )()
        owner.active_project_kind = "tif"
        owner.active_project_source_kind = "tif"
        owner.tif_project = type("TifProject", (), {"current_project_path": "volume.sqlite_manifest.json"})()
        owner.project = type("ImageProject", (), {"current_project_path": "image.sqlite_manifest.json"})()
        owner._apply_project_mode_tabs = lambda: None
        owner._update_start_center_texts = lambda: None

        owner._show_start_center()

        self.assertEqual(owner.active_project_kind, "start")
        self.assertEqual(owner.last_workbench_kind, "tif")
        self.assertEqual(owner._active_recent_project_path(), "volume.sqlite_manifest.json")

    def test_shell_collaborators_do_not_import_main_window(self):
        for module_name in [
            "main_window_agent_context.py",
            "main_window_coordinator.py",
            "main_window_shell.py",
            "main_window_signal_router.py",
            "main_window_start_center.py",
            "main_window_view.py",
        ]:
            source = (ROOT / "AntSleap" / "ui" / module_name).read_text(encoding="utf-8")
            self.assertNotIn("AntSleap.main", source)
            self.assertNotIn("from main import", source)

    def test_pdf_and_tif_workbenches_are_lazy_shell_dependencies(self):
        main_source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")
        dependencies_source = (
            ROOT / "AntSleap" / "ui" / "main_window_shell_dependencies.py"
        ).read_text(encoding="utf-8")
        shell_source = (ROOT / "AntSleap" / "ui" / "main_window_shell.py").read_text(encoding="utf-8")

        self.assertNotIn("from AntSleap.ui.pdf_processing_widget import", main_source)
        self.assertNotIn("from AntSleap.ui.tif_workbench import", main_source)
        self.assertNotIn("from AntSleap.ui.pdf_processing_widget import", dependencies_source)
        self.assertNotIn("from AntSleap.ui.tif_workbench import", dependencies_source)
        self.assertIn("def _ensure_pdf_widget", shell_source)
        self.assertIn("def _ensure_tif_workbench", shell_source)


if __name__ == "__main__":
    unittest.main()
