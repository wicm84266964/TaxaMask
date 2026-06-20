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
        self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")
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
        self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(summary["draft_boxes_only"])

    def test_auto_annotate_cli_can_write_box_only_model_drafts(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "auto_annotate_box_only_draft"
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
                            "polygons": {},
                            "auto_boxes": {
                                "Head": [12, 14, 48, 45],
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_auto_box_only_draft.json"
        report = tmp / "auto_box_only_draft_report.json"
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
        self.assertEqual(labels["auto_boxes"]["Head"], [12.0, 14.0, 48.0, 45.0])
        self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(summary["saved_label_count"], 1)

    def test_auto_annotate_cli_only_new_replaces_unconfirmed_vlm_draft(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "auto_annotate_priority"
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
                            "parts": {"Head": [[10, 10], [40, 10], [40, 35], [10, 35]]},
                            "auto_boxes": {"Head": [10, 10, 40, 35]},
                            "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                            "descriptions": {"Head": "Auto-Annotated"},
                            "status": "labeled",
                            "genus": "Formica",
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
                                "Head": [[20, 20], [70, 20], [70, 55], [20, 55]],
                            },
                            "auto_boxes": {
                                "Head": [20, 20, 70, 55],
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_auto_priority.json"
        report = tmp / "auto_priority_report.json"
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
                "--only-new",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(out_project.read_text(encoding="utf-8"))
        labels = next(iter(payload["labels"].values()))
        self.assertEqual(labels["parts"]["Head"], [[20.0, 20.0], [70.0, 20.0], [70.0, 55.0], [20.0, 55.0]])
        self.assertEqual(labels["auto_boxes"]["Head"], [20.0, 20.0, 70.0, 55.0])
        self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(summary["saved_label_count"], 1)

    def test_auto_annotate_cli_keeps_confirmed_label_even_without_only_new(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "auto_annotate_confirmed_priority"
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
                            "parts": {"Head": [[10, 10], [40, 10], [40, 35], [10, 35]]},
                            "auto_boxes": {"Head": [10, 10, 40, 35]},
                            "auto_box_meta": {"Head": {"source": "model_prediction", "review_status": "confirmed"}},
                            "descriptions": {},
                            "status": "labeled",
                            "genus": "Formica",
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
                                "Head": [[20, 20], [70, 20], [70, 55], [20, 55]],
                            },
                            "auto_boxes": {
                                "Head": [20, 20, 70, 55],
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_auto_confirmed_priority.json"
        report = tmp / "auto_confirmed_priority_report.json"
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
        self.assertEqual(labels["parts"]["Head"], [[10, 10], [40, 10], [40, 35], [10, 35]])
        self.assertEqual(labels["auto_boxes"]["Head"], [10, 10, 40, 35])
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(summary["saved_label_count"], 0)


if __name__ == "__main__":
    unittest.main()
