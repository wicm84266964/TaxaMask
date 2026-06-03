import tempfile
import types
import unittest
from pathlib import Path

import cv2
import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANTSLEAP_ROOT = PROJECT_ROOT / "AntSleap"

import sys

if str(ANTSLEAP_ROOT) not in sys.path:
    sys.path.insert(0, str(ANTSLEAP_ROOT))

from core.cascade_manager import CascadingManager
from core.blink_expert_backends import create_default_blink_backend_registry
from core.blink_heatmap_trainer import HeatmapBlinkNet
from core.cascade_routes import (
    ROUTE_BACKEND_HEATMAP_BLINK,
    ROUTE_BACKEND_VIT_B_BLINK,
)


class BlinkRouteBackendTests(unittest.TestCase):
    def _manager(self, weights_dir):
        engine = types.SimpleNamespace(device="cpu", weights_dir=str(weights_dir))
        manager = CascadingManager.__new__(CascadingManager)
        manager.engine = engine
        manager.device = "cpu"
        manager.loaded_experts = {}
        manager.expert_dir = str(Path(weights_dir) / "experts")
        manager.route_manifest_path = str(Path(weights_dir) / "experts" / "cascade_routes.json")
        manager.legacy_route_manifest = {"version": "", "approved": False, "routes": []}
        manager.blink_backend_registry = create_default_blink_backend_registry()
        return manager

    def test_vit_b_backend_keeps_existing_loader_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            expert_path = weights_dir / "experts" / "Mandible" / "expert_v1.pth"
            expert_path.parent.mkdir(parents=True, exist_ok=True)
            expert_path.write_bytes(b"placeholder")
            manager = self._manager(weights_dir)
            loader_calls = []
            infer_calls = []

            def fake_load(part_name, model_path=None):
                loader_calls.append((part_name, model_path))
                return object()

            def fake_infer(image_path, parent_box, child_part_name, expert_model):
                infer_calls.append((image_path, list(parent_box), child_part_name, expert_model))
                return {"box": [1, 2, 3, 4], "confidence": 1.0}

            manager._load_expert = fake_load
            manager._infer_with_loaded_expert = fake_infer

            result = manager.infer_child_part(
                "specimen.png",
                [10, 20, 80, 70],
                "Mandible",
                parent_part="Head",
                route_manifest={
                    "version": "project-v2",
                    "routes": [
                        {
                            "parent": "Head",
                            "child": "Mandible",
                            "enabled": True,
                            "expert_id": "Mandible/expert_v1.pth",
                            "expert_part": "Mandible",
                            "expert_filename": "expert_v1.pth",
                            "expert_backend": ROUTE_BACKEND_VIT_B_BLINK,
                        }
                    ],
                },
            )

            self.assertEqual(result["box"], [1, 2, 3, 4])
            self.assertEqual(loader_calls, [("Mandible", str(expert_path))])
            self.assertEqual(infer_calls[0][1], [10, 20, 80, 70])

    def test_heatmap_backend_predicts_without_calling_vit_b_loader(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            expert_path = weights_dir / "experts" / "Eye" / "heatmap_v1.pth"
            expert_path.parent.mkdir(parents=True, exist_ok=True)
            model = HeatmapBlinkNet(base_channels=8)
            for param in model.parameters():
                torch.nn.init.constant_(param, 0.0)
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "meta": {
                        "kind": "blink_heatmap_expert",
                        "input_size": [64, 64],
                        "base_channels": 8,
                    },
                },
                expert_path,
            )
            image_path = Path(tmp_dir) / "specimen.png"
            cv2.imwrite(str(image_path), np.full((80, 100, 3), 180, dtype=np.uint8))
            manager = self._manager(weights_dir)
            loader_calls = []

            def fake_load(part_name, model_path=None):
                loader_calls.append((part_name, model_path))
                return object()

            manager._load_expert = fake_load

            route = {
                "parent": "Head",
                "child": "Eye",
                "enabled": True,
                "expert_id": "Eye/heatmap_v1.pth",
                "expert_part": "Eye",
                "expert_filename": "heatmap_v1.pth",
                "expert_backend": ROUTE_BACKEND_HEATMAP_BLINK,
                "input_size": [64, 64],
            }
            self.assertIsNone(manager.get_route_block_reason(route))

            result = manager.infer_child_part(
                str(image_path),
                [10, 20, 80, 70],
                "Eye",
                parent_part="Head",
                route_manifest={"version": "project-v2", "routes": [route]},
            )

            self.assertIsInstance(result, dict)
            self.assertEqual(result.get("backend"), ROUTE_BACKEND_HEATMAP_BLINK)
            self.assertEqual(len(result.get("box", [])), 4)
            self.assertEqual(loader_calls, [])


if __name__ == "__main__":
    unittest.main()
