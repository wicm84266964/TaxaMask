import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.vlm_preannotation import build_vlm_preannotation_prompt, parse_vlm_response, run_vlm_preannotation


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

    def test_pixel_box_takes_priority_over_legacy_grid_box(self):
        raw_response = json.dumps(
            {
                "detections": [
                    {
                        "part": "Head",
                        "bbox_xyxy": [10, 20, 110, 160],
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
        self.assertEqual(candidates[0]["box_xyxy"], [10.0, 20.0, 110.0, 160.0])

    def test_input_pixel_box_maps_back_to_original_pixels(self):
        raw_response = json.dumps(
            {
                "detections": [
                    {
                        "part": "Head",
                        "bbox_xyxy": [10, 20, 110, 160],
                        "confidence": 0.82,
                    }
                ]
            }
        )
        candidates, rejected, _parsed = parse_vlm_response(
            raw_response,
            ["Head"],
            image_size=(1200, 800),
            overlay_size=(600, 400),
            min_confidence=0.25,
            default_coordinate_space="input",
        )
        self.assertEqual(rejected, [])
        self.assertEqual(len(candidates), 1)
        self.assertAlmostEqual(candidates[0]["box_xyxy"][0], 20.0)
        self.assertAlmostEqual(candidates[0]["box_xyxy"][1], 40.0)
        self.assertAlmostEqual(candidates[0]["box_xyxy"][2], 220.0)
        self.assertAlmostEqual(candidates[0]["box_xyxy"][3], 320.0)

    def test_prompt_allows_reasonable_overlap_between_adjacent_parts(self):
        prompt = build_vlm_preannotation_prompt(["Head", "Mesosoma"], (1200, 800), input_size=(600, 400))

        self.assertIn("允许合理重叠", prompt)
        self.assertIn("不是互斥切片", prompt)
        self.assertIn("不要为了让框不重叠", prompt)
        self.assertIn("Head 与 Mesosoma", prompt)
        self.assertIn("直接按当前输入图片像素坐标", prompt)
        self.assertIn("width=600, height=400", prompt)
        self.assertNotIn("bbox_grid_xyxy", prompt)
        self.assertNotIn("细网格", prompt)

    def test_run_preannotation_uses_pixel_input_image_by_default(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "specimen.png"
            Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)

            result = run_vlm_preannotation(
                str(image_path),
                ["Head"],
                tmp_dir,
                dry_run=True,
                run_id="pixel",
            )

            overlay = result["overlay"]
            self.assertEqual(overlay["image_mode"], "pixel")
            self.assertEqual(overlay["grid_cols"], 0)
            self.assertEqual(overlay["grid_rows"], 0)
            self.assertIn("_vlm_input_pixel.png", overlay["overlay_path"])
            self.assertNotIn("网格", result["prompt"])
            self.assertTrue(Path(overlay["overlay_path"]).exists())

    def test_project_load_normalizes_relative_image_keys_to_absolute(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            image_path = root / "savedata" / "specimen.png"
            image_path.parent.mkdir()
            Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)
            project_dir = root / "projects"
            project_dir.mkdir()
            project_path = project_dir / "project.json"
            relative_image = os.path.relpath(image_path, project_dir)
            project_path.write_text(
                json.dumps(
                    {
                        "name": "demo",
                        "taxonomy": ["Head"],
                        "images": [relative_image],
                        "labels": {
                            relative_image: {
                                "parts": {"Head": [[10, 10], [50, 10], [30, 40]]},
                                "status": "labeled",
                            }
                        },
                        "scales": {relative_image: 12.5},
                        "image_provenance": {relative_image: {"source": "pdf"}},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            old_cwd = os.getcwd()
            try:
                os.chdir(project_dir)
                manager = ProjectManager()
                manager.load_project(str(project_path))
            finally:
                os.chdir(old_cwd)

            absolute_image = os.path.abspath(str(image_path))
            self.assertEqual(manager.project_data["images"], [absolute_image])
            self.assertIn(absolute_image, manager.project_data["labels"])
            self.assertNotIn(relative_image, manager.project_data["labels"])
            self.assertEqual(manager.get_labels(absolute_image)["Head"], [[10, 10], [50, 10], [30, 40]])
            self.assertEqual(manager.get_scale(absolute_image), 12.5)
            self.assertEqual(manager.get_image_provenance(absolute_image)["source"], "pdf")

    def test_project_load_merges_absolute_shadow_vlm_key(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            image_path = root / "savedata" / "specimen.png"
            image_path.parent.mkdir()
            Image.new("RGB", (120, 80), color=(140, 150, 160)).save(image_path)
            project_dir = root / "projects"
            project_dir.mkdir()
            project_path = project_dir / "project.json"
            relative_image = os.path.relpath(image_path, project_dir)
            absolute_image = os.path.abspath(str(image_path))
            project_path.write_text(
                json.dumps(
                    {
                        "name": "demo",
                        "taxonomy": ["Head", "Mesosoma"],
                        "images": [relative_image],
                        "labels": {
                            relative_image: {
                                "parts": {"Head": [[10, 10], [50, 10], [30, 40]]},
                                "status": "labeled",
                            },
                            absolute_image: {
                                "parts": {},
                                "auto_boxes": {"Mesosoma": [40, 20, 100, 70]},
                                "auto_box_meta": {"Mesosoma": {"source": "vlm_first_mile"}},
                                "descriptions": {"Mesosoma": "Auto-Annotated"},
                                "status": "unlabeled",
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manager = ProjectManager()
            manager.load_project(str(project_path))

            self.assertEqual(manager.project_data["images"], [absolute_image])
            self.assertEqual(list(manager.project_data["labels"].keys()), [absolute_image])
            labels = manager.project_data["labels"][absolute_image]
            self.assertIn("Head", labels["parts"])
            self.assertEqual(labels["auto_boxes"]["Mesosoma"], [40, 20, 100, 70])
            self.assertEqual(labels["auto_box_meta"]["Mesosoma"]["source"], "vlm_first_mile")

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
