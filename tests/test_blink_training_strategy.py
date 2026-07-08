import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANTSLEAP_ROOT = PROJECT_ROOT / "AntSleap"
if str(ANTSLEAP_ROOT) not in sys.path:
    sys.path.insert(0, str(ANTSLEAP_ROOT))

from core.blink_dataset import BlinkTrajectoryDataset
from core.blink_training_strategy import (
    BLINK_STRATEGY_FULL_INSIDE_RANDOM,
    BLINK_STRATEGY_TRIVIEW_RANDOM,
    BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
    DEFAULT_BLINK_TRAINING_STRATEGY,
)


class BlinkTrainingStrategyTests(unittest.TestCase):
    def test_default_strategy_is_two_stage_full_then_inside(self):
        self.assertEqual(DEFAULT_BLINK_TRAINING_STRATEGY, BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE)

    def _make_project(self, root):
        image_path = root / "specimen.png"
        Image.new("RGB", (120, 100), color=(160, 160, 160)).save(image_path)
        project_json = root / "project.json"
        project_json.write_text(
            json.dumps(
                {
                    "images": ["specimen.png"],
                    "labels": {
                        "specimen.png": {
                            "trajectories": {
                                "Mandible": {
                                    "frames": [
                                        {"box": [30.0, 30.0, 70.0, 70.0], "coord_frame": "global"},
                                        {"box": [36.0, 36.0, 60.0, 60.0], "coord_frame": "global"},
                                        {"box": [42.0, 42.0, 54.0, 54.0], "coord_frame": "global"},
                                    ],
                                    "parent_context": {
                                        "parent_part": "Head",
                                        "parent_box": [20.0, 20.0, 90.0, 90.0],
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
        return project_json

    def test_plan_one_can_choose_outside_view(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_json = self._make_project(Path(tmp_dir))
            dataset = BlinkTrajectoryDataset(
                str(project_json),
                "Mandible",
                parent_part="Head",
                target_size=(64, 64),
                blink_prob=1.0,
                training_strategy=BLINK_STRATEGY_TRIVIEW_RANDOM,
            )
            with patch("core.blink_dataset.random.random", side_effect=[0.0, 0.9]):
                sample = dataset[0]
            self.assertEqual(sample["view_mode"], "outside")

    def test_plan_two_never_uses_outside_view(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_json = self._make_project(Path(tmp_dir))
            dataset = BlinkTrajectoryDataset(
                str(project_json),
                "Mandible",
                parent_part="Head",
                target_size=(64, 64),
                blink_prob=1.0,
                training_strategy=BLINK_STRATEGY_FULL_INSIDE_RANDOM,
            )
            with patch("core.blink_dataset.random.random", return_value=0.0):
                sample = dataset[0]
            self.assertEqual(sample["view_mode"], "inside")

    def test_plan_three_stage_view_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_json = self._make_project(Path(tmp_dir))
            full_dataset = BlinkTrajectoryDataset(
                str(project_json),
                "Mandible",
                parent_part="Head",
                target_size=(64, 64),
                training_strategy=BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
                stage_view_mode="full",
            )
            inside_dataset = BlinkTrajectoryDataset(
                str(project_json),
                "Mandible",
                parent_part="Head",
                target_size=(64, 64),
                training_strategy=BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
                stage_view_mode="inside",
            )
            self.assertEqual(full_dataset[0]["view_mode"], "full")
            self.assertEqual(inside_dataset[0]["view_mode"], "inside")


if __name__ == "__main__":
    unittest.main()
