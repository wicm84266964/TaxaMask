import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
import torch.nn as nn

from AntSleap.core.blink_heatmap_trainer import BlinkHeatmapTrainer
from AntSleap.core.blink_reproducibility import build_blink_seed_record
from AntSleap.core.blink_trainer import BlinkExpertTrainer
from AntSleap.models.expert_networks import MicroExpertLocator


class _TinyLocator(nn.Module):
    def __init__(self, pretrained=False, image_size=224):
        super().__init__()
        if pretrained:
            raise AssertionError("test locator must not receive pretrained=True")
        self.image_size = image_size
        self.projection = nn.Linear(4, 4)

    def forward(self, inputs):
        return self.projection(inputs)


class _TinyVisionTransformer(nn.Module):
    def __init__(self):
        super().__init__()
        self.probe = nn.Linear(4, 4)
        self.heads = nn.Identity()

    def forward(self, inputs):
        features = torch.zeros((inputs.shape[0], 768), device=inputs.device)
        return self.heads(features)


class _EmptyDataset:
    sequence_count = 0

    def __len__(self):
        return 0


def _state_dict_copy(model):
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


class BlinkReproducibilityTests(unittest.TestCase):
    def test_vit_b_forbids_torchvision_pretrained_state(self):
        with patch("AntSleap.models.expert_networks.models.vit_b_16") as builder:
            with self.assertRaisesRegex(ValueError, "blink_vit_torchvision_pretrained_forbidden"):
                MicroExpertLocator(pretrained=True, image_size=224)
            builder.assert_not_called()

        tiny_vit = _TinyVisionTransformer()
        with patch(
            "AntSleap.models.expert_networks.models.vit_b_16",
            return_value=tiny_vit,
        ) as builder:
            model = MicroExpertLocator(pretrained=False, image_size=224)
        self.assertIs(model.vit, tiny_vit)
        builder.assert_called_once_with(weights=None, image_size=224)

    def test_same_seed_repeats_vit_and_heatmap_initialization(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = str(Path(tmp_dir) / "project.json")
            with patch("AntSleap.core.blink_trainer.MicroExpertLocator", _TinyLocator):
                vit_first = BlinkExpertTrainer(
                    project_path, "Eye", parent_part="Head", device="cpu",
                    save_dir=str(Path(tmp_dir) / "vit_a"), random_seed=2468,
                )
                vit_second = BlinkExpertTrainer(
                    project_path, "Eye", parent_part="Head", device="cpu",
                    save_dir=str(Path(tmp_dir) / "vit_b"), random_seed=2468,
                )
            heatmap_first = BlinkHeatmapTrainer(
                project_path, "Eye", parent_part="Head", device="cpu",
                save_dir=str(Path(tmp_dir) / "heatmap_a"), random_seed=2468,
            )
            heatmap_second = BlinkHeatmapTrainer(
                project_path, "Eye", parent_part="Head", device="cpu",
                save_dir=str(Path(tmp_dir) / "heatmap_b"), random_seed=2468,
            )

            for first, second in (
                (_state_dict_copy(vit_first.model), _state_dict_copy(vit_second.model)),
                (_state_dict_copy(heatmap_first.model), _state_dict_copy(heatmap_second.model)),
            ):
                self.assertEqual(set(first), set(second))
                self.assertTrue(all(torch.equal(first[key], second[key]) for key in first))

    def test_both_backends_record_initialization_and_seeds(self):
        expected_seeds = build_blink_seed_record(9753)
        expected_initialization = {
            "method": "random",
            "registered_checkpoint": None,
            "torchvision_pretrained": False,
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            project_path = str(root / "project.json")
            with patch("AntSleap.core.blink_trainer.MicroExpertLocator", _TinyLocator):
                vit = BlinkExpertTrainer(
                    project_path, "Eye", parent_part="Head", device="cpu",
                    save_dir=str(root / "vit"), random_seed=9753,
                )
            heatmap = BlinkHeatmapTrainer(
                project_path, "Eye", parent_part="Head", device="cpu",
                save_dir=str(root / "heatmap"), random_seed=9753,
            )

            for trainer, target_size, name in (
                (vit, (224, 224), "vit"),
                (heatmap, (512, 512), "heatmap"),
            ):
                metadata = trainer._build_checkpoint_meta(target_size, 1, 1, 0.5)
                self.assertEqual(metadata["initialization"], expected_initialization)
                self.assertEqual(metadata["seeds"], expected_seeds)

                weights_path = root / f"{name}.pth"
                weights_path.write_bytes(b"weights")
                _manifest_path, manifest = trainer.write_manifest(
                    str(weights_path), target_size, _EmptyDataset()
                )
                self.assertEqual(manifest["initialization"], expected_initialization)
                self.assertEqual(manifest["seeds"], expected_seeds)
                self.assertEqual(manifest["train_params"]["random_seed"], 9753)

                report_dir = root / f"{name}_report"
                report_dir.mkdir()
                with (
                    patch.object(trainer, "_experiment_dir", return_value=str(report_dir)),
                    patch.object(trainer, "_save_history_csv", return_value=str(report_dir / "training_log.csv")),
                    patch.object(trainer, "_plot_metrics", return_value=None),
                    patch.object(
                        trainer,
                        "_plot_validation_samples",
                        return_value=(None, str(report_dir / "details"), []),
                    ),
                ):
                    report = trainer.generate_report(
                        _EmptyDataset(), str(weights_path), target_size, max_samples=0
                    )
                summary = report["validation_summary"]
                self.assertEqual(summary["initialization"], expected_initialization)
                self.assertEqual(summary["seeds"], expected_seeds)


if __name__ == "__main__":
    unittest.main()
