import ast
import os
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget


    class CountingLogWorkbench(TifWorkbenchWidget):
        def __init__(self, *args, **kwargs):
            self.show_log_calls = 0
            super().__init__(*args, **kwargs)

        def show_workbench_log(self):
            self.show_log_calls += 1


@unittest.skipUnless(QApplication is not None, "PySide6 is required for TIF workbench shell tests")
class TifWorkbenchShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_shell_buttons_bind_once_and_emit_expected_commands(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        start_calls = []
        agent_contexts = []
        widget.start_center_requested.connect(lambda: start_calls.append("start"))
        widget.agent_requested.connect(agent_contexts.append)

        widget.workbench_shell.bind_shell_signals()
        widget.btn_start_center.click()
        widget.btn_ask_agent.click()

        self.assertEqual(start_calls, ["start"])
        self.assertEqual(len(agent_contexts), 1)
        self.assertEqual(widget.signal_router.connection_count("shell"), 3)
        self.assertEqual(
            set(widget.workbench_view.registered_names("shell")),
            {"btn_start_center", "btn_ask_agent", "btn_show_workbench_log"},
        )
        widget.workbench_shell.shutdown()
        widget.deleteLater()

    def test_show_log_button_routes_directly_to_shell_command(self):
        manager = TifProjectManager()
        widget = CountingLogWorkbench(manager, "en")
        widget.btn_show_workbench_log.click()

        self.assertEqual(widget.show_log_calls, 1)
        widget.workbench_shell.shutdown()
        widget.deleteLater()


    def test_controller_registry_and_lifecycle_hooks_are_auditable(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        events = []

        class LifecycleProbe:
            def on_project_opened(self, project):
                events.append(("opened", project))

            def on_selection_changed(self, selection):
                events.append(("selection", selection))

            def on_workbench_closing(self):
                events.append(("closing", None))

            def on_workbench_destroyed(self):
                events.append(("destroyed", None))

        widget.workbench_shell.controllers = {"probe": LifecycleProbe()}
        project = object()
        selection = {"specimen_id": "01-0101-01"}

        self.assertEqual(widget.workbench_shell.notify_controllers("on_project_opened", project), [("probe", None)])
        self.assertEqual(widget.workbench_shell.notify_controllers("on_selection_changed", selection), [("probe", None)])
        widget.workbench_shell.shutdown()

        self.assertEqual(
            events,
            [("opened", project), ("selection", selection), ("closing", None), ("destroyed", None)],
        )
        self.assertEqual(widget.signal_router.connection_count(), 0)
        widget.deleteLater()

    def test_shell_registers_workflow_controllers_in_stable_order(self):
        widget = TifWorkbenchWidget(TifProjectManager(), "en")
        try:
            self.assertEqual(
                tuple(widget.workbench_shell.controllers),
                (
                    "selection",
                    "project_lifecycle",
                    "annotation",
                    "roi",
                    "part_mask",
                    "preview",
                    "volume_render",
                    "local_axis",
                    "backend_panel",
                    "result_review",
                ),
            )
        finally:
            widget.workbench_shell.shutdown()
            widget.deleteLater()

    def test_extracted_modules_do_not_call_missing_workbench_methods(self):
        widget = TifWorkbenchWidget(TifProjectManager(), "en")
        root = Path(__file__).resolve().parents[1]
        files = list((root / "AntSleap" / "ui").glob("tif_*controller.py"))
        files.extend(
            (
                root / "AntSleap" / "ui" / "tif_gpu_volume_canvas.py",
                root / "AntSleap" / "ui" / "tif_workbench_canvas.py",
            )
        )
        missing = []
        misplaced_widget_checks = []
        invalid_dialog_parents = []
        try:
            for path in files:
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if (
                        path.name.endswith("_controller.py")
                        and isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "QMessageBox"
                        and node.args
                        and isinstance(node.args[0], ast.Name)
                        and node.args[0].id == "self"
                    ):
                        invalid_dialog_parents.append(f"{path.name}:{node.lineno}:{node.func.attr}")
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id in {"hasattr", "getattr"}
                        and len(node.args) >= 2
                        and isinstance(node.args[0], ast.Name)
                        and node.args[0].id == "self"
                        and isinstance(node.args[1], ast.Constant)
                        and isinstance(node.args[1].value, str)
                        and hasattr(widget, node.args[1].value)
                    ):
                        misplaced_widget_checks.append(f"{path.name}:{node.lineno}:{node.args[1].value}")
                    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                        continue
                    owner = node.func.value
                    workbench_call = (
                        isinstance(owner, ast.Name)
                        and owner.id in {"workbench", "wb"}
                    ) or (
                        isinstance(owner, ast.Attribute)
                        and isinstance(owner.value, ast.Name)
                        and owner.value.id == "self"
                        and owner.attr == "workbench"
                    )
                    if workbench_call and not hasattr(widget, node.func.attr):
                        missing.append(f"{path.name}:{node.lineno}:{node.func.attr}")
        finally:
            widget.close_project(prompt_unsaved=False)
            widget.deleteLater()

        self.assertEqual(missing, [])
        self.assertEqual(misplaced_widget_checks, [])
        self.assertEqual(invalid_dialog_parents, [])

    def test_workbench_does_not_call_missing_self_or_controller_methods(self):
        widget = TifWorkbenchWidget(TifProjectManager(), "en")
        root = Path(__file__).resolve().parents[1]
        path = root / "AntSleap" / "ui" / "tif_workbench.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        workbench_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "TifWorkbenchWidget"
        )
        missing_self = []
        missing_controller = []
        try:
            for node in ast.walk(workbench_class):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                owner = node.func.value
                if isinstance(owner, ast.Name) and owner.id == "self":
                    if not hasattr(widget, node.func.attr):
                        missing_self.append(f"{node.lineno}:{node.func.attr}")
                    continue
                if not (
                    isinstance(owner, ast.Attribute)
                    and isinstance(owner.value, ast.Name)
                    and owner.value.id == "self"
                ):
                    continue
                target = getattr(widget, owner.attr, None)
                if target is not None and not hasattr(target, node.func.attr):
                    missing_controller.append(f"{node.lineno}:{owner.attr}.{node.func.attr}")
        finally:
            widget.close_project(prompt_unsaved=False)
            widget.deleteLater()

        self.assertEqual(missing_self, [])
        self.assertEqual(missing_controller, [])

if __name__ == "__main__":
    unittest.main()
