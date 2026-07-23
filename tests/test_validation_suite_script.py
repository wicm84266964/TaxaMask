import subprocess
import sys
import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_validation_suite.py"


class ValidationSuiteScriptTests(unittest.TestCase):
    def test_list_reports_core_and_safety_suites(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--list"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=30,
        )

        self.assertIn("tif_core:", result.stdout)
        self.assertIn("tif_storage_safety:", result.stdout)
        self.assertIn("pdf_safety:", result.stdout)
        self.assertIn("validation_tooling:", result.stdout)
        self.assertIn("round5_traceability:", result.stdout)
        self.assertIn("round5_inference:", result.stdout)
        self.assertIn("round5_mesh:", result.stdout)
        self.assertIn("round5_local_axis_risk:", result.stdout)

    def test_default_suites_cover_every_test_module(self):
        spec = importlib.util.spec_from_file_location("run_validation_suite_for_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        suite_modules = set()
        for suite_name in module.DEFAULT_ORDER:
            for entry in module.SUITES[suite_name]:
                parts = entry.split(".")
                if len(parts) >= 2 and parts[0] == "tests":
                    suite_modules.add(".".join(parts[:2]))
        all_modules = {
            path.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".")
            for path in (ROOT / "tests").glob("test_*.py")
        }

        self.assertEqual(sorted(all_modules - suite_modules), [])

    def test_unknown_suite_returns_argparse_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--suite", "missing_suite"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_round5_ci_smoke_covers_each_safety_boundary(self):
        spec = importlib.util.spec_from_file_location("run_validation_suite_for_smoke", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        smoke = "\n".join(module.SUITES["round5_ci_smoke"])
        for keyword in (
            "manifest",
            "training_snapshot",
            "full_pipeline",
            "physical_xyz_mesh",
            "in_sqlite",
            "incomplete_recoverable",
            "no_partial_file",
            "risk_components",
            "manual_truth_gate",
            "accept_selected",
            "training_uses_manual_truth_only",
        ):
            self.assertIn(keyword, smoke)
        self.assertNotIn("round5_ci_smoke", module.DEFAULT_ORDER)

    def test_chunked_suite_runs_single_fast_tooling_test(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--suite",
                "validation_chunk_sample",
                "--chunk-size",
                "1",
                "--timeout",
                "30",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validation_chunk_sample chunk", result.stdout)


if __name__ == "__main__":
    unittest.main()
