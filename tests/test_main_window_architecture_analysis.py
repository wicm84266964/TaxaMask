import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_main_window_architecture.py"


def load_analysis_module():
    spec = importlib.util.spec_from_file_location("main_window_architecture_analysis", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MainWindowArchitectureAnalysisTests(unittest.TestCase):
    def test_report_covers_round4_structure_signals_state_and_compatibility(self):
        report = load_analysis_module().build_report()
        metrics = report["metrics"]

        self.assertLess(metrics["main_physical_lines"], 16024)
        self.assertLess(metrics["top_level_class_count"], 22)
        self.assertLess(metrics["all_method_count"], 592)
        self.assertEqual(metrics["connection_count"], 194)
        self.assertLessEqual(metrics["main_window_lines"], 9500)
        self.assertEqual(metrics["main_window_method_count"], 390)
        self.assertEqual(metrics["main_window_connection_count"], 128)
        self.assertEqual(metrics["main_window_init_lines"], 668)
        self.assertEqual(len(report["connections"]), metrics["connection_count"])
        self.assertGreater(metrics["main_window_unique_state_fields"], 100)
        self.assertGreater(metrics["main_import_site_count"], 0)
        self.assertGreater(metrics["key_test_reference_line_count"], 100)

    def test_report_maps_known_classes_and_workflows_to_stages(self):
        report = load_analysis_module().build_report()
        classes = {row["name"]: row for row in report["classes"]}
        methods = {row["name"]: row for row in report["main_window_methods"]}

        self.assertNotIn("InferenceThread", classes)
        self.assertEqual(classes["ModelSettingsDialog"]["target_stage"], 2)
        self.assertEqual(classes["MainWindow"]["target_stage"], 3)
        self.assertEqual(methods["open_project_path"]["target_stage"], 4)
        self.assertEqual(methods["launch_blink_from_workbench"]["target_stage"], 6)
        self.assertEqual(methods["run_vlm_preannotation_from_settings"]["target_stage"], 7)
        self.assertEqual(len(report["main_window_methods"]), 390)

    def test_stage1_runtime_workers_and_widgets_leave_main_as_compatibility_facade(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("class InferenceThread", source)
        self.assertNotIn("class TrainingThread", source)
        self.assertNotIn("class ImageGroupListWidget", source)
        self.assertIn("from AntSleap.ui.main_window_workers import", source)
        self.assertIn("from AntSleap.ui.main_window_widgets import", source)

    def test_markdown_contains_stage0_migration_sections(self):
        module = load_analysis_module()
        report = module.build_report()
        method_ledger = module.render_method_inventory(report)
        signal_ledger = module.render_signal_inventory(report)

        self.assertIn("## Top-level Classes", method_ledger)
        self.assertIn("## MainWindow Methods", method_ledger)
        self.assertIn("## MainWindow State Fields", method_ledger)
        self.assertIn("## Main Import Compatibility", method_ledger)
        self.assertIn("## Key Test Dependencies", method_ledger)
        self.assertIn("## Qt Connections", signal_ledger)
        self.assertIn("## Thread Timer and Async Entries", signal_ledger)
        self.assertIn("Target owner", signal_ledger)


if __name__ == "__main__":
    unittest.main()
