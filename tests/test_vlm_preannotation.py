import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.vlm_preannotation import parse_vlm_response, run_vlm_preannotation


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class VlmPreannotationTests(unittest.TestCase):
    def test_vlm_settings_are_independent_from_locator_scope(self):
        manager = ProjectManager()
        manager.project_data["taxonomy"] = ["Head", "Eye", "Mandible"]
        manager.set_locator_scope(["Head"], save=False)
        settings = manager.set_vlm_preannotation_settings(
            {
                "target_parts": ["Eye", "Mandible", "Unknown"],
                "processing_scope": "all_images",
            },
            save=False,
        )

        self.assertEqual(settings["target_parts"], ["Eye", "Mandible"])
        self.assertEqual(settings["processing_scope"], "all_images")
        self.assertEqual(manager.get_locator_scope(), ["Head"])

    def test_verify_keeps_confirmed_aibox_source(self):
        manager = ProjectManager()
        image_path = "memory/specimen.png"
        manager.project_data["labels"][image_path] = {
            "parts": {
                "Head": [[10, 10], [50, 10], [30, 40]],
            },
            "auto_boxes": {
                "Head": [10, 10, 50, 40],
            },
            "auto_box_meta": {
                "Head": {"source": "vlm_first_mile", "review_status": "draft"},
            },
            "descriptions": {
                "Head": "Auto-Annotated",
            },
            "status": "labeled",
        }

        count = manager.verify_image_labels(image_path)

        self.assertEqual(count, 1)
        labels = manager.project_data["labels"][image_path]
        self.assertEqual(labels["auto_boxes"]["Head"], [10, 10, 50, 40])
        self.assertEqual(labels["auto_box_meta"]["Head"]["review_status"], "confirmed")
        self.assertNotIn("Head", labels["descriptions"])

    def test_manual_box_replacement_clears_ai_draft_state(self):
        manager = ProjectManager()
        image_path = "memory/specimen.png"
        manager.project_data["labels"][image_path] = {
            "parts": {
                "Head": [[10, 10], [50, 10], [30, 40]],
            },
            "auto_boxes": {
                "Head": [10, 10, 50, 40],
            },
            "auto_box_meta": {
                "Head": {"source": "vlm_first_mile", "review_status": "draft"},
            },
            "descriptions": {
                "Head": "Auto-Annotated",
            },
            "status": "labeled",
        }

        manager.update_label(
            image_path,
            "Head",
            [[12, 12], [52, 12], [32, 42]],
            description_text="",
            box=[12, 12, 52, 42],
            save=False,
        )

        labels = manager.project_data["labels"][image_path]
        self.assertNotIn("Head", labels.get("auto_boxes", {}))
        self.assertNotIn("Head", labels.get("auto_box_meta", {}))
        self.assertNotIn("Head", labels.get("descriptions", {}))
        self.assertEqual(labels["boxes"]["Head"], [12.0, 12.0, 52.0, 42.0])

    def test_delete_label_clears_ai_box_metadata(self):
        manager = ProjectManager()
        image_path = "memory/specimen.png"
        manager.project_data["labels"][image_path] = {
            "parts": {
                "Head": [[10, 10], [50, 10], [30, 40]],
            },
            "auto_boxes": {
                "Head": [10, 10, 50, 40],
            },
            "auto_box_meta": {
                "Head": {"source": "vlm_first_mile", "review_status": "draft"},
            },
            "descriptions": {
                "Head": "Auto-Annotated",
            },
            "status": "labeled",
        }

        manager.delete_label(image_path, "Head", save=False)

        labels = manager.project_data["labels"][image_path]
        self.assertNotIn("Head", labels.get("parts", {}))
        self.assertNotIn("Head", labels.get("auto_boxes", {}))
        self.assertNotIn("Head", labels.get("auto_box_meta", {}))

    def test_parse_grid_box_to_original_pixels(self):
        raw_response = json.dumps(
            {
                "detections": [
                    {
                        "part": "Head",
                        "bbox_grid_xyxy": [2, 3, 5, 7],
                        "confidence": 0.82,
                        "reason": "head capsule visible",
                    }
                ]
            }
        )
        candidates, rejected, _parsed = parse_vlm_response(
            raw_response,
            ["Head", "Eye"],
            image_size=(1200, 800),
            overlay_size=(600, 400),
            grid_cols=12,
            grid_rows=8,
            min_confidence=0.25,
        )
        self.assertEqual(rejected, [])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["part"], "Head")
        self.assertEqual(candidates[0]["box_xyxy"], [200.0, 300.0, 500.0, 700.0])

    def test_provider_non_json_response_is_saved_for_diagnosis(self):
        class FakeResponse:
            status_code = 200
            text = "<html>provider gateway error</html>"

            def json(self):
                raise ValueError("not json")

        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "specimen.png"
            Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)

            with patch("AntSleap.core.vlm_preannotation.requests.post", return_value=FakeResponse()):
                with self.assertRaises(ValueError) as ctx:
                    run_vlm_preannotation(
                        str(image_path),
                        ["Head"],
                        tmp_dir,
                        api_config={"api_key": "test-key", "base_url": "https://example.test/v1", "model": "vlm"},
                        run_id="badjson",
                    )

            message = str(ctx.exception)
            self.assertIn("vlm_api_response_not_json", message)
            raw_response_path = Path(tmp_dir) / "specimen_raw_response_badjson.txt"
            report_path = Path(tmp_dir) / "specimen_vlm_preannotation_badjson.json"
            self.assertEqual(raw_response_path.read_text(encoding="utf-8"), FakeResponse.text)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertIn("vlm_api_response_not_json", report["error"])
            self.assertEqual(report["raw_response_path"], str(raw_response_path))

    def test_provider_empty_model_text_response_is_saved_for_diagnosis(self):
        class FakeResponse:
            status_code = 200
            text = '{"choices":[{"message":{"content":""},"finish_reason":"stop"}]}'

            def json(self):
                return json.loads(self.text)

        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "specimen.png"
            Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)

            with patch("AntSleap.core.vlm_preannotation.requests.post", return_value=FakeResponse()):
                with self.assertRaises(ValueError) as ctx:
                    run_vlm_preannotation(
                        str(image_path),
                        ["Head"],
                        tmp_dir,
                        api_config={"api_key": "test-key", "base_url": "https://example.test/v1", "model": "vlm"},
                        run_id="emptytext",
                    )

            message = str(ctx.exception)
            self.assertIn("empty_vlm_output", message)
            raw_response_path = Path(tmp_dir) / "specimen_raw_response_emptytext.txt"
            report_path = Path(tmp_dir) / "specimen_vlm_preannotation_emptytext.json"
            self.assertEqual(raw_response_path.read_text(encoding="utf-8"), FakeResponse.text)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["raw_response_path"], str(raw_response_path))

    def test_cli_prediction_fixture_writes_auto_boxes_only(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "vlm_preannotation"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "specimen.png"
        Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)

        project_path = tmp / "project.json"
        project_path.write_text(
            json.dumps(
                {
                    "name": "demo",
                    "taxonomy": ["Head", "Eye"],
                    "locator_scope": ["Head"],
                    "vlm_preannotation": {
                        "target_parts": ["Head"],
                        "processing_scope": "current_image",
                    },
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
                        "specimen.png": {
                            "detections": [
                                {
                                    "part": "Head",
                                    "bbox_xyxy": [10, 12, 50, 44],
                                    "confidence": 0.9,
                                }
                            ]
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_vlm.json"
        report = tmp / "vlm_report.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "vlm_preannotate_project.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_project),
                "--prediction-json",
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
        self.assertEqual(labels.get("parts", {}), {})
        self.assertEqual(labels["auto_boxes"]["Head"], [10.0, 12.0, 50.0, 44.0])
        self.assertNotIn("boxes", labels)
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(summary["saved_box_count"], 1)

    def test_cli_requires_explicit_or_saved_vlm_target_parts(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "vlm_preannotation_no_parts"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "specimen.png"
        Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)
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
        out_project = tmp / "project_vlm.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "vlm_preannotate_project.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_project),
                "--dry-run",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("no_vlm_target_parts_configured", result.stderr)

    def test_verify_keeps_box_only_drafts_unreviewed(self):
        manager = ProjectManager()
        image_path = "memory/specimen.png"
        manager.project_data["labels"][image_path] = {
            "parts": {
                "Head": [[10, 10], [50, 10], [30, 40]],
            },
            "auto_boxes": {
                "Head": [10, 10, 50, 40],
                "Eye": [20, 18, 28, 26],
            },
            "descriptions": {
                "Head": "Auto-Annotated",
                "Eye": "Auto-Annotated",
            },
            "status": "labeled",
        }

        count = manager.verify_image_labels(image_path)

        self.assertEqual(count, 1)
        labels = manager.project_data["labels"][image_path]
        self.assertNotIn("Head", labels["descriptions"])
        self.assertEqual(labels["descriptions"]["Eye"], "Auto-Annotated")


if __name__ == "__main__":
    unittest.main()
