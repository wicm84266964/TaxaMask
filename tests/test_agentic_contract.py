import json
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AgenticContractTests(unittest.TestCase):
    def test_contract_stage_ids_are_unique(self):
        contract_path = PROJECT_ROOT / "AntSleap" / "config" / "agentic_pipeline_contract.json"
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
        stage_ids = [stage["id"] for stage in payload["stages"]]
        self.assertEqual(len(stage_ids), len(set(stage_ids)))
        self.assertIn("stage_30_candidate_bridge_and_routing", stage_ids)

    def test_dry_run_writes_machine_readable_plan(self):
        script_path = PROJECT_ROOT / "tools" / "agentic" / "run_agentic_pipeline.py"
        out_dir = PROJECT_ROOT / "artifacts" / "agentic_pipeline_test"
        out_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--dry-run",
                "--out",
                str(out_dir),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plan_path = out_dir / "agentic_run_plan.json"
        self.assertTrue(plan_path.exists())
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["status"], "dry_run")
        self.assertGreaterEqual(len(plan["stages"]), 5)
        blocked = [stage for stage in plan["stages"] if stage["blocked_reasons"]]
        self.assertTrue(blocked)


if __name__ == "__main__":
    unittest.main()
