import json
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AgenticMultimodalExportTests(unittest.TestCase):
    def test_export_cli_adds_schema_run_and_provenance_fields(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "multimodal_export"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "specimen.png"
        Image.new("RGB", (80, 60), color=(150, 150, 150)).save(image_path)

        project_path = tmp / "project.json"
        project_path.write_text(
            json.dumps(
                {
                    "name": "demo",
                    "taxonomy": ["Head"],
                    "locator_scope": ["Head"],
                    "images": ["specimen.png"],
                    "labels": {
                        "specimen.png": {
                            "parts": {"Head": [[10, 10], [30, 10], [30, 30], [10, 30]]},
                            "boxes": {"Head": [10, 10, 30, 30]},
                            "descriptions": {"Head": "Auto-Annotated"},
                            "status": "labeled",
                            "genus": "Formica",
                            "taxon": "Formica",
                            "taxon_rank": "genus",
                            "taxon_metadata": {"source": "unit-test"},
                        }
                    },
                    "scales": {},
                    "image_provenance": {
                        "specimen.png": {
                            "schema_version": "formica-image-provenance-v1",
                            "candidate_id": "cand_1",
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_dir = tmp / "dataset"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "export_multimodal_dataset.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_dir),
                "--run-id",
                "test_run",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        records = [
            json.loads(line)
            for line in (out_dir / "multimodal_dataset.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["schema_version"], "taxamask-multimodal-sample-v1")
        self.assertEqual(records[0]["taxon"], "Formica")
        self.assertEqual(records[0]["taxon_rank"], "genus")
        self.assertEqual(records[0]["taxon_metadata"], {"source": "unit-test"})
        self.assertEqual(records[0]["genus"], "Formica")
        self.assertEqual(records[0]["annotation_status"], "workbench_export")
        self.assertEqual(records[0]["export_run_id"], "test_run")
        self.assertEqual(records[0]["source_provenance"]["candidate_id"], "cand_1")
        self.assertIn("model_provenance", records[0])
        summary = json.loads((out_dir / "export_summary.json").read_text(encoding="utf-8"))
        profile_summary_path = Path(summary["model_profile_summary_path"])
        self.assertTrue(profile_summary_path.exists())
        profile_summary = json.loads(profile_summary_path.read_text(encoding="utf-8"))
        self.assertEqual(profile_summary["schema_version"], "taxamask-model-profile-export-summary-v1")
        self.assertEqual(profile_summary["active_profile"]["profile_scope"], "2d_stl")
        self.assertEqual(profile_summary["parent_backend"]["locator_scope"], ["Head"])


if __name__ == "__main__":
    unittest.main()
