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

        self.assertLessEqual(metrics["main_physical_lines"], 800)
        self.assertEqual(metrics["top_level_class_count"], 1)
        self.assertEqual(metrics["all_method_count"], 1)
        self.assertEqual(metrics["connection_count"], 198)
        self.assertLessEqual(metrics["main_window_lines"], 40)
        self.assertEqual(metrics["main_window_method_count"], 1)
        self.assertEqual(metrics["main_window_connection_count"], 0)
        self.assertLessEqual(metrics["main_window_init_lines"], 20)
        self.assertEqual(len(report["connections"]), metrics["connection_count"])
        self.assertEqual(metrics["main_window_unique_state_fields"], 0)
        self.assertEqual(metrics["key_test_direct_main_private_reference_occurrences"], 0)
        self.assertGreater(metrics["main_import_site_count"], 0)
        self.assertGreater(metrics["key_test_reference_line_count"], 100)

    def test_report_maps_known_classes_and_workflows_to_stages(self):
        report = load_analysis_module().build_report()
        classes = {row["name"]: row for row in report["classes"]}
        methods = {row["name"]: row for row in report["main_window_methods"]}

        self.assertNotIn("InferenceThread", classes)
        self.assertNotIn("ModelSettingsDialog", classes)
        self.assertEqual(classes["MainWindow"]["target_stage"], 3)
        self.assertNotIn("open_project_path", methods)
        self.assertNotIn("launch_blink_from_workbench", methods)
        self.assertNotIn("run_vlm_preannotation_from_settings", methods)
        self.assertEqual(len(report["main_window_methods"]), 1)

    def test_stage1_runtime_workers_and_widgets_leave_main_as_compatibility_facade(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("class InferenceThread", source)
        self.assertNotIn("class TrainingThread", source)
        self.assertNotIn("class ImageGroupListWidget", source)
        self.assertIn("from AntSleap.ui.main_window_workers import", source)
        self.assertIn("from AntSleap.ui.main_window_widgets import", source)

    def test_stage2_dialogs_leave_main_as_compatibility_facade(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("class ModelSettingsDialog", source)
        self.assertNotIn("class RouteManagementPanel", source)
        self.assertNotIn("class LiteratureDescriptionDialog", source)
        self.assertIn("from AntSleap.ui.model_settings_dialog import", source)
        self.assertIn("from AntSleap.ui.training_report_dialogs import", source)
        self.assertIn("from AntSleap.ui.main_window_dialogs import", source)

    def test_stage3_shell_and_agent_methods_leave_main(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("def _build_start_center", source)
        self.assertNotIn("def _compact_agent_context", source)
        self.assertNotIn("def enter_image_workflow", source)
        self.assertIn("from AntSleap.ui.main_window_shell import", source)
        self.assertIn("from AntSleap.ui.main_window_start_center import", source)
        self.assertIn("from AntSleap.ui.main_window_agent_context import", source)

    def test_stage4_project_lifecycle_methods_leave_main(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("def open_project_path", source)
        self.assertNotIn("def _flush_pending_project_save", source)
        self.assertNotIn("def backup_current_sqlite_project", source)
        self.assertIn("from AntSleap.ui.main_window_project_lifecycle import", source)

    def test_stage5_navigation_and_literature_methods_leave_main(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("def refresh_file_list", source)
        self.assertNotIn("def on_file_selected", source)
        self.assertNotIn("def _resolve_current_literature_context", source)
        self.assertIn("from AntSleap.ui.main_window_image_navigation import", source)
        self.assertIn("from AntSleap.ui.main_window_literature_bridge import", source)
        self.assertIn("from AntSleap.ui.main_window_part_tree import", source)

    def test_stage6_annotation_sam_and_blink_methods_leave_main(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("def on_polygon_completed", source)
        self.assertNotIn("def launch_blink_from_workbench", source)
        self.assertNotIn("def run_blink_batch_auto_shrink", source)
        self.assertIn("from AntSleap.ui.main_window_annotation import", source)
        self.assertIn("from AntSleap.ui.main_window_blink_context import", source)
        self.assertIn("from AntSleap.ui.main_window_blink_workflow import", source)

    def test_stage7_training_prediction_vlm_and_export_methods_leave_main(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("def run_training", source)
        self.assertNotIn("def run_prediction", source)
        self.assertNotIn("def run_vlm_preannotation_from_settings", source)
        self.assertNotIn("def export_dataset", source)
        self.assertIn("from AntSleap.ui.main_window_training import", source)
        self.assertIn("from AntSleap.ui.main_window_prediction import", source)
        self.assertIn("from AntSleap.ui.main_window_vlm import", source)
        self.assertIn("from AntSleap.ui.main_window_export import", source)

    def test_stage8_presentation_methods_leave_main(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("def refresh_ui", source)
        self.assertNotIn("def open_general_settings", source)
        self.assertNotIn("def change_theme", source)
        self.assertNotIn("def log", source)
        self.assertIn("from AntSleap.ui.main_window_presentation import", source)

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
