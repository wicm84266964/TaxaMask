# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANTSLEAP_ROOT = PROJECT_ROOT / "AntSleap"
if str(ANTSLEAP_ROOT) not in sys.path:
    sys.path.insert(0, str(ANTSLEAP_ROOT))

from core.blink_dataset import BlinkTrajectoryDataset
from core.engine import AntEngine


class _FakeLocator:
    def eval(self):
        return self

    def __call__(self, _tensor):
        hm = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
        hm[0, 0, 220, 180] = 1.0
        wh = torch.zeros((1, 1, 2), dtype=torch.float32)
        wh[0, 0, 0] = 0.20
        wh[0, 0, 1] = 0.24
        return hm, wh


class _FakeMasks:
    def __init__(self):
        self.xy = [np.array([[10.0, 10.0], [40.0, 10.0], [40.0, 40.0], [10.0, 40.0]], dtype=np.float32)]


class _FakeResult:
    def __init__(self):
        self.masks = _FakeMasks()


class _FakeSAMModel:
    def eval(self):
        return None


class _FakeSAMPredictor:
    def predict(self, *args, **kwargs):
        return [_FakeResult()]


class _FakePartsModel:
    def __init__(self):
        self.sam_model = _FakeSAMModel()
        self.ultralytics_sam = _FakeSAMPredictor()


class _FakeCascadeManager:
    def __init__(self):
        self.calls = []
        self.legacy_manifest = {
            "version": "legacy",
            "routes": [
                {
                    "parent": "Head",
                    "child": "Mandible",
                    "enabled": True,
                    "expert_part": "Mandible",
                    "expert_filename": "expert_v20260501_090000.pth",
                    "expert_id": "Mandible/expert_v20260501_090000.pth",
                    "registration_source": "legacy_global_manifest",
                }
            ],
        }

    def get_runtime_route_manifest(self, project_route_manifest=None):
        project_routes = (project_route_manifest or {}).get("routes", []) if isinstance(project_route_manifest, dict) else []
        if project_routes:
            return project_route_manifest
        return self.legacy_manifest

    def routes_ready(self, route_manifest=None):
        manifest = route_manifest or self.legacy_manifest
        routes = manifest.get("routes", []) if isinstance(manifest, dict) else []
        return any(bool(route.get("enabled", False)) for route in routes)

    def _find_route(self, parent_part, child_part_name, route_manifest=None):
        manifest = route_manifest or self.legacy_manifest
        for route in manifest.get("routes", []):
            if route.get("parent") == parent_part and route.get("child") == child_part_name and route.get("enabled"):
                return route
        return None

    def can_override(self, parent_part, child_part_name, route_manifest=None):
        return self._find_route(parent_part, child_part_name, route_manifest=route_manifest) is not None

    def get_route_min_conf(self, parent_part, child_part_name, route_manifest=None):
        return None

    def get_route_block_reason(self, route):
        if route and route.get("expert_id"):
            return None
        return "expert_unappointed"

    def describe_route(self, route):
        return f"{route.get('parent')}->{route.get('child')} [{route.get('expert_id')}]"

    def resolve_route_for_child(self, child_part_name, available_parents, route_manifest=None):
        if child_part_name == "Mandible" and "Head" in available_parents:
            return self._find_route("Head", "Mandible", route_manifest=route_manifest)
        return None

    def infer_child_part(self, image_path, parent_box, child_part_name, parent_part="macro_locator", route_manifest=None):
        self.calls.append(
            {
                "image_path": image_path,
                "parent_box": list(parent_box),
                "child_part_name": child_part_name,
                "parent_part": parent_part,
            }
        )
        return {"box": [32.0, 34.0, 66.0, 70.0], "confidence": 1.0}


class MacroMicroPipelineTests(unittest.TestCase):
    def test_predict_full_pipeline_routes_child_parts_outside_locator_scope(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "specimen.png"
            Image.new("RGB", (200, 180), color=(180, 180, 180)).save(image_path)

            engine = AntEngine.__new__(AntEngine)
            engine.device = "cpu"
            engine.locator = _FakeLocator()
            engine.parts_model = _FakePartsModel()
            engine.cascade_manager = _FakeCascadeManager()

            preds = engine.predict_full_pipeline(
                str(image_path),
                current_taxonomy=["Head", "Mandible"],
                locator_scope=["Head"],
                project_route_manifest={
                    "version": "legacy",
                    "routes": [
                        {
                            "parent": "Head",
                            "child": "Mandible",
                            "enabled": True,
                            "expert_id": "Mandible/expert_v20260501_090000.pth",
                            "expert_part": "Mandible",
                            "expert_filename": "expert_v20260501_090000.pth",
                            "registration_source": "legacy_global_manifest",
                        }
                    ],
                },
            )

            self.assertEqual(preds["meta"]["locator_scope"], ["Head"])
            self.assertIn("Head", preds["auto_boxes"])
            self.assertIn("Mandible", preds["auto_boxes"])
            self.assertIn("Mandible", preds["polygons"])
            self.assertEqual(preds["meta"]["cascade_applied_count"], 1)
            self.assertEqual(preds["meta"]["cascade_route_source"], "project")
            self.assertEqual(len(engine.cascade_manager.calls), 1)
            self.assertEqual(engine.cascade_manager.calls[0]["parent_part"], "Head")

    def test_predict_full_pipeline_uses_legacy_fallback_when_project_routes_absent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "specimen.png"
            Image.new("RGB", (200, 180), color=(180, 180, 180)).save(image_path)

            engine = AntEngine.__new__(AntEngine)
            engine.device = "cpu"
            engine.locator = _FakeLocator()
            engine.parts_model = _FakePartsModel()
            engine.cascade_manager = _FakeCascadeManager()

            preds = engine.predict_full_pipeline(
                str(image_path),
                current_taxonomy=["Head", "Mandible"],
                locator_scope=["Head"],
                project_route_manifest={"version": "project-v1", "routes": []},
            )

            self.assertEqual(preds["meta"]["cascade_route_source"], "legacy_global")
            self.assertEqual(preds["meta"]["cascade_applied_count"], 1)
            self.assertEqual(len(engine.cascade_manager.calls), 1)

    def test_predict_full_pipeline_prefers_project_route_manifest_and_respects_disabled_project_routes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "specimen.png"
            Image.new("RGB", (200, 180), color=(180, 180, 180)).save(image_path)

            engine = AntEngine.__new__(AntEngine)
            engine.device = "cpu"
            engine.locator = _FakeLocator()
            engine.parts_model = _FakePartsModel()
            engine.cascade_manager = _FakeCascadeManager()

            preds = engine.predict_full_pipeline(
                str(image_path),
                current_taxonomy=["Head", "Mandible"],
                locator_scope=["Head"],
                project_route_manifest={
                    "version": "project-v1",
                    "routes": [
                        {
                            "parent": "Head",
                            "child": "Mandible",
                            "enabled": False,
                            "expert_id": "Mandible/expert_v20260501_090000.pth",
                            "expert_part": "Mandible",
                            "expert_filename": "expert_v20260501_090000.pth",
                            "registration_source": "blink_candidate",
                        }
                    ],
                },
            )

            self.assertEqual(preds["meta"]["cascade_route_source"], "project")
            self.assertNotIn("Mandible", preds["auto_boxes"])
            self.assertEqual(preds["meta"]["cascade_applied_count"], 0)
            self.assertEqual(preds["meta"]["cascade_block_reasons"].get("Mandible"), "route_disabled")

    def test_predict_full_pipeline_reads_nested_appointed_expert_but_ignores_history_candidates_for_runtime(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "specimen.png"
            Image.new("RGB", (200, 180), color=(180, 180, 180)).save(image_path)

            engine = AntEngine.__new__(AntEngine)
            engine.device = "cpu"
            engine.locator = _FakeLocator()
            engine.parts_model = _FakePartsModel()
            engine.cascade_manager = _FakeCascadeManager()

            preds = engine.predict_full_pipeline(
                str(image_path),
                current_taxonomy=["Head", "Mandible"],
                locator_scope=["Head"],
                project_route_manifest={
                    "version": "project-v2",
                    "routes": [
                        {
                            "parent": "Head",
                            "child": "Mandible",
                            "enabled": True,
                            "appointed_expert": {
                                "expert_id": "Mandible/mandible_v2.pth",
                                "expert_part": "Mandible",
                                "expert_filename": "mandible_v2.pth",
                            },
                            "expert_candidates": [
                                {
                                    "expert_id": "Mandible/mandible_v2.pth",
                                    "expert_part": "Mandible",
                                    "expert_filename": "mandible_v2.pth",
                                },
                                {
                                    "expert_id": "Mandible/expert_v20260501_090000.pth",
                                    "expert_part": "Mandible",
                                    "expert_filename": "expert_v20260501_090000.pth",
                                },
                            ],
                            "expert_id": "Mandible/mandible_v2.pth",
                            "expert_part": "Mandible",
                            "expert_filename": "mandible_v2.pth",
                            "registration_source": "project",
                        }
                    ],
                },
            )

            self.assertEqual(preds["meta"]["cascade_route_source"], "project")
            self.assertEqual(preds["meta"]["cascade_route_manifest_version"], "project-v2")
            self.assertEqual(preds["meta"]["cascade_applied_count"], 1)
            self.assertEqual(len(engine.cascade_manager.calls), 1)
            self.assertEqual(engine.cascade_manager.calls[0]["parent_part"], "Head")

    def test_blink_dataset_reads_parent_context_crop_format(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            image_path = tmp_root / "specimen.png"
            Image.new("RGB", (120, 100), color=(160, 160, 160)).save(image_path)

            project_json = tmp_root / "project.json"
            project_json.write_text(
                json.dumps(
                    {
                        "name": "demo",
                        "taxonomy": ["Head", "Mandible"],
                        "locator_scope": ["Head"],
                        "images": ["specimen.png"],
                        "labels": {
                            "specimen.png": {
                                "parts": {},
                                "trajectories": {
                                    "Mandible": {
                                        "frames": [
                                            {"step": 0, "alpha": 0.0, "box": [18.0, 20.0, 58.0, 62.0], "coord_frame": "global"},
                                            {"step": 1, "alpha": 1.0, "box": [22.0, 24.0, 52.0, 56.0], "coord_frame": "global"},
                                        ],
                                        "parent_context": {
                                            "parent_part": "Head",
                                            "parent_box": [10.0, 12.0, 80.0, 78.0],
                                            "source": "manual",
                                        },
                                    }
                                },
                            }
                        },
                        "scales": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            dataset = BlinkTrajectoryDataset(
                str(project_json),
                part_name="Mandible",
                parent_part="Head",
                target_size=(64, 64),
                blink_prob=0.0,
            )

            self.assertGreater(len(dataset), 0)
            sample = dataset[0]
            self.assertEqual(tuple(sample["image"].shape[-2:]), (64, 64))
            self.assertTrue(torch.all(sample["target_step"] >= 0.0))
            self.assertTrue(torch.all(sample["target_step"] <= 1.0))
            self.assertTrue(torch.all(sample["target_final"] >= 0.0))
            self.assertTrue(torch.all(sample["target_final"] <= 1.0))


if __name__ == "__main__":
    unittest.main()
