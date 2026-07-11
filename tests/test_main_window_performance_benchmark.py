import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_main_window_workflows.py"


def load_benchmark_module():
    spec = importlib.util.spec_from_file_location("main_window_performance_benchmark", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MainWindowPerformanceBenchmarkTests(unittest.TestCase):
    def test_summary_uses_median_and_nearest_rank_p95(self):
        module = load_benchmark_module()
        summary = module.summarize_runs([{"startup_ms": value} for value in range(1, 11)])

        self.assertEqual(summary["startup_ms"]["median"], 5.5)
        self.assertEqual(summary["startup_ms"]["p95"], 10.0)
        self.assertEqual(summary["startup_ms"]["min"], 1.0)
        self.assertEqual(summary["startup_ms"]["max"], 10.0)

    def test_default_output_is_disposable_validation_directory(self):
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('".tmp_validation" / "round4_stage0"', source)
        self.assertIn('"private_data": False', source)
        self.assertNotIn("CHANGELOG_zh.md", source)


if __name__ == "__main__":
    unittest.main()
