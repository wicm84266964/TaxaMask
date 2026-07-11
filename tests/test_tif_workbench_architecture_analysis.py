import ast
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_tif_workbench_architecture.py"


def load_analysis_module():
    spec = importlib.util.spec_from_file_location("tif_workbench_architecture_analysis", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TifWorkbenchArchitectureAnalysisTests(unittest.TestCase):
    def test_report_covers_methods_signals_and_private_test_dependencies(self):
        report = load_analysis_module().build_report()

        self.assertGreater(report["metrics"]["workbench_lines"], 0)
        self.assertGreater(report["metrics"]["widget_method_count"], 0)
        self.assertGreater(report["metrics"]["connection_count"], 0)
        self.assertEqual(report["metrics"]["connection_count"], len(report["connections"]))
        self.assertGreater(report["metrics"]["tests_with_private_refs"], 0)
        self.assertTrue(any(row["name"] == "save_working_edit" for row in report["methods"]))
        self.assertTrue(any("render_failed" in row["signal"] for row in report["connections"]))
        self.assertFalse(any("clicked" in row["signal"] for row in report["connections"]))

    def test_round3_widget_metrics_stay_within_stage9_limits(self):
        report = load_analysis_module().build_report()
        metrics = report["metrics"]

        self.assertLessEqual(metrics["workbench_lines"], 8000)
        self.assertLess(metrics["widget_method_count"], 350)
        self.assertLess(metrics["connection_count"], 80)
        self.assertLess(metrics["thin_method_count_le_4"], 40)

        source = (ROOT / "AntSleap" / "ui" / "tif_workbench.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        widget = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TifWorkbenchWidget")
        init = next(node for node in widget.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
        self.assertLess(init.end_lineno - init.lineno + 1, 300)
        self.assertFalse(any(isinstance(node, ast.FunctionDef) and node.name == "_build_layout" for node in widget.body))

    def test_view_builder_and_coordinator_remain_bounded(self):
        builder = (ROOT / "AntSleap" / "ui" / "tif_workbench_view_builder.py").read_text(encoding="utf-8")
        coordinator = (ROOT / "AntSleap" / "ui" / "tif_workbench_coordinator.py").read_text(encoding="utf-8")

        self.assertLess(len(builder.splitlines()), 3000)
        self.assertLess(len(coordinator.splitlines()), 300)
        self.assertNotIn("roi_keyframes", coordinator)
        self.assertNotIn("mask_volume", coordinator)
        self.assertNotIn("render_cache", coordinator)

    def test_markdown_contains_migration_inventory_sections(self):
        module = load_analysis_module()
        report = module.build_report()
        markdown = module.render_markdown(report)
        test_ledger = module.render_test_migration_markdown(report)
        signal_ledger = module.render_signal_migration_markdown(report)

        self.assertIn("## Metrics", markdown)
        self.assertIn("## Workflow Method Counts", markdown)
        self.assertIn("## Compatibility Counts", markdown)
        self.assertIn("## Methods", markdown)
        self.assertIn("Private refs", test_ledger)
        self.assertIn("Target owner", signal_ledger)


if __name__ == "__main__":
    unittest.main()
