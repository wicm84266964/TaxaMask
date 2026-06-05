import json
import sys
import tempfile
import unittest
from pathlib import Path

import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANTSLEAP_ROOT = PROJECT_ROOT / "AntSleap"
if str(ANTSLEAP_ROOT) not in sys.path:
    sys.path.insert(0, str(ANTSLEAP_ROOT))

from core.blink_heatmap_dataset import BlinkHeatmapDataset
from core.blink_heatmap_trainer import HeatmapBlinkNet, normalize_heatmap_input_size


class BlinkHeatmapDatasetTests(unittest.TestCase):
    def test_dataset_reads_parent_roi_and_builds_heatmap_targets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            image_path = root / "specimen.png"
            Image.new("RGB", (120, 100), color=(160, 160, 160)).save(image_path)
            project_json = root / "project.json"
            project_json.write_text(
                json.dumps(
                    {
                        "taxonomy": ["Head", "Eye"],
                        "images": ["specimen.png"],
                        "labels": {
                            "specimen.png": {
                                "trajectories": {
                                    "Eye": {
                                        "frames": [
                                            {"box": [32.0, 34.0, 48.0, 50.0], "coord_frame": "global"},
                                            {"box": [36.0, 38.0, 44.0, 46.0], "coord_frame": "global"},
                                        ],
                                        "parent_context": {
                                            "parent_part": "Head",
                                            "parent_box": [20.0, 20.0, 80.0, 80.0],
                                        },
                                    }
                                }
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            dataset = BlinkHeatmapDataset(str(project_json), "Eye", parent_part="Head", input_size=64, heatmap_sigma=1.5)

            self.assertEqual(dataset.sequence_count, 1)
            self.assertEqual(len(dataset), 10)
            sample = dataset[0]
            self.assertEqual(tuple(sample["image"].shape), (3, 64, 64))
            self.assertEqual(tuple(sample["inside_image"].shape), (3, 64, 64))
            self.assertEqual(tuple(sample["outside_image"].shape), (3, 64, 64))
            self.assertEqual(tuple(sample["heatmap"].shape), (1, 64, 64))
            self.assertEqual(tuple(sample["step_heatmap"].shape), (1, 64, 64))
            self.assertEqual(tuple(sample["wh"].shape), (2,))
            self.assertEqual(tuple(sample["step_wh"].shape), (2,))
            self.assertGreater(float(sample["heatmap"].max()), 0.9)
            self.assertTrue(torch.all(sample["wh"] > 0.0))
            self.assertTrue(torch.all(sample["wh"] <= 1.0))
            self.assertFalse(torch.equal(sample["inside_image"], sample["outside_image"]))

    def test_heatmap_network_preserves_heatmap_resolution_and_wh_shape(self):
        model = HeatmapBlinkNet(base_channels=8)
        x = torch.zeros((2, 3, 64, 64), dtype=torch.float32)
        heatmap, wh = model(x)

        self.assertEqual(tuple(heatmap.shape), (2, 1, 64, 64))
        self.assertEqual(tuple(wh.shape), (2, 1, 2))

    def test_heatmap_input_size_has_safe_minimum(self):
        self.assertEqual(normalize_heatmap_input_size(16), (64, 64))
        self.assertEqual(normalize_heatmap_input_size([128, 128]), (128, 128))


if __name__ == "__main__":
    unittest.main()
