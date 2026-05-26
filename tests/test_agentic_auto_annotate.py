import json
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AgenticAutoAnnotateTests(unittest.TestCase):
    def test_auto_annotate_cli_applies_prediction_json(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "auto_annotate"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "specimen.png"
        Image.new("RGB", (100, 80), color=(110, 120, 130)).save(image_path)

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
                            "parts": {},
                            "status": "unlabeled",
                            "genus": "Formica",
                            "descriptions": {},
                        }
                    },
                    "scales": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        predictions_path = tmp / "predictions.json"
        predictions_path.write_text(
            json.dumps(
                {
                    "images": {
                        str(image_path): {
                            "polygons": {
                                "Head": [[10, 10], [40, 10], [40, 35], [10, 35]],
                            },
                            "auto_boxes": {
                                "Head": [10, 10, 40, 35],
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_auto.json"
        report = tmp / "auto_report.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "auto_annotate_project.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_project),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(out_project.read_text(encoding="utf-8"))
        labels = next(iter(payload["labels"].values()))
        self.assertIn("Head", labels["parts"])
        self.assertEqual(labels["descriptions"]["Head"], "Auto-Annotated")
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(summary["saved_label_count"], 1)

    def test_auto_annotate_cli_can_write_draft_boxes_only(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "auto_annotate_draft"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "specimen.png"
        Image.new("RGB", (100, 80), color=(110, 120, 130)).save(image_path)

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
                            "parts": {},
                            "status": "unlabeled",
                            "genus": "Formica",
                            "descriptions": {},
                        }
                    },
                    "scales": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        predictions_path = tmp / "predictions.json"
        predictions_path.write_text(
            json.dumps(
                {
                    "images": {
                        str(image_path): {
                            "polygons": {
                                "Head": [[10, 10], [40, 10], [40, 35], [10, 35]],
                            },
                            "auto_boxes": {
                                "Head": [10, 10, 40, 35],
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_auto_draft.json"
        report = tmp / "auto_report_draft.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "auto_annotate_project.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_project),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report),
                "--draft-boxes-only",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(out_project.read_text(encoding="utf-8"))
        labels = next(iter(payload["labels"].values()))
        self.assertEqual(labels.get("parts", {}), {})
        self.assertEqual(labels["auto_boxes"]["Head"], [10.0, 10.0, 40.0, 35.0])
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(summary["draft_boxes_only"])


if __name__ == "__main__":
    unittest.main()
