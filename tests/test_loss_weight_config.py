# pyright: reportMissingImports=false

import sys
import tempfile
import types
import unittest
from pathlib import Path

import torch


if "ultralytics" not in sys.modules:
    ultralytics_stub = types.ModuleType("ultralytics")
    ultralytics_models_stub = types.ModuleType("ultralytics.models")
    ultralytics_models_sam_stub = types.ModuleType("ultralytics.models.sam")

    class _FakeSAM:
        pass

    class _FakePredictor:
        pass

    ultralytics_stub.SAM = _FakeSAM
    ultralytics_models_sam_stub.Predictor = _FakePredictor
    sys.modules["ultralytics"] = ultralytics_stub
    sys.modules["ultralytics.models"] = ultralytics_models_stub
    sys.modules["ultralytics.models.sam"] = ultralytics_models_sam_stub


from AntSleap.core.blink_heatmap_trainer import BlinkHeatmapTrainer
from AntSleap.core.blink_trainer import BlinkExpertTrainer
from AntSleap.core.blink_training_strategy import BLINK_STRATEGY_TRIVIEW_RANDOM
from AntSleap.core.engine import AntEngine, FocalMSELoss
from AntSleap.core.model_profiles import (
    DEFAULT_BLINK_OUTER_LOSS_WEIGHTS,
    DEFAULT_HEATMAP_BLINK_COMPONENT_LOSS_WEIGHTS,
    DEFAULT_LOCATOR_LOSS_WEIGHTS,
    make_default_model_profile,
    sanitize_model_profile,
)


class _CheckpointLocator:
    def state_dict(self):
        return {"weight": torch.tensor([1.0])}


class LossWeightConfigTests(unittest.TestCase):
    def test_model_profile_preserves_named_loss_weight_defaults_and_overrides(self):
        defaults = make_default_model_profile()
        self.assertEqual(defaults["parent_backend"]["loss_weights"], DEFAULT_LOCATOR_LOSS_WEIGHTS)
        self.assertEqual(defaults["child_backend_defaults"]["loss_weights"], DEFAULT_BLINK_OUTER_LOSS_WEIGHTS)

        raw = {
            **defaults,
            "parent_backend": {
                **defaults["parent_backend"],
                "loss_weights": {"heatmap": "1.5", "wh": -2},
            },
            "child_backend_defaults": {
                **defaults["child_backend_defaults"],
                "loss_weights": {"final": 2, "step": "0.4"},
            },
        }
        clean = sanitize_model_profile(raw, defaults=defaults)
        self.assertEqual(clean["parent_backend"]["loss_weights"], {"heatmap": 1.5, "wh": 0.0})
        self.assertEqual(
            clean["child_backend_defaults"]["loss_weights"],
            {"final": 2.0, "step": 0.4, "view": 0.2, "consistency": 0.1},
        )

        legacy = sanitize_model_profile(
            {
                "profile_id": "legacy_without_loss_weights",
                "parent_backend": {"backend_type": defaults["parent_backend"]["backend_type"]},
                "child_backend_defaults": {"backend_type": defaults["child_backend_defaults"]["backend_type"]},
            },
            defaults=defaults,
        )
        self.assertEqual(legacy["parent_backend"]["loss_weights"], DEFAULT_LOCATOR_LOSS_WEIGHTS)
        self.assertEqual(legacy["child_backend_defaults"]["loss_weights"], DEFAULT_BLINK_OUTER_LOSS_WEIGHTS)

    def test_engine_runtime_setter_sanitizes_and_exposes_effective_weights(self):
        engine = AntEngine.__new__(AntEngine)

        snapshot = engine.set_locator_loss_weights({"heatmap": "1.75", "wh": -1})

        self.assertEqual(snapshot, {"locator": {"heatmap": 1.75, "wh": 0.0}})
        self.assertEqual(engine.get_loss_config_snapshot(), snapshot)

    def test_locator_default_weighted_loss_matches_legacy_formula(self):
        engine = AntEngine.__new__(AntEngine)
        engine.crit_heatmap = FocalMSELoss()
        engine.crit_wh = torch.nn.SmoothL1Loss(reduction="none")
        engine._locator_loss_weights = dict(DEFAULT_LOCATOR_LOSS_WEIGHTS)

        hm_pred = torch.tensor([[[[0.2, 0.7], [0.4, 0.9]]]], dtype=torch.float32)
        hm_target = torch.tensor([[[[0.0, 1.0], [0.5, 1.0]]]], dtype=torch.float32)
        wh_pred = torch.tensor([[[0.2, 0.8]]], dtype=torch.float32)
        wh_target = torch.tensor([[[0.4, 0.5]]], dtype=torch.float32)
        valid_mask = torch.tensor([[1.0]], dtype=torch.float32)

        loss_hm, loss_wh, actual = engine._compute_locator_losses(
            hm_pred,
            hm_target,
            wh_pred,
            wh_target,
            valid_mask,
        )
        legacy = loss_hm + 0.5 * loss_wh

        torch.testing.assert_close(actual, legacy, rtol=0, atol=0)
        self.assertAlmostEqual(float(actual.item()), 2.0625, places=6)
        self.assertEqual(engine.loss_config_snapshot, {"locator": {"heatmap": 1.0, "wh": 0.5}})

    def test_locator_checkpoint_saves_effective_loss_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            engine = AntEngine.__new__(AntEngine)
            engine.weights_dir = tmp_dir
            engine.locator = _CheckpointLocator()
            engine.ensure_locator_loaded = lambda: engine.locator
            engine.locator_resolution = (512, 512)
            engine.current_num_classes = 3
            engine.loaded_locator_timestamp = None
            engine.loaded_locator_requires_legacy_confirmation = False
            engine.loaded_locator_is_legacy_512 = False
            engine._locator_loss_weights = {"heatmap": 1.25, "wh": 0.75}

            timestamp = engine.save_weights(save_locator=True, save_segmenter=False)
            payload = torch.load(Path(tmp_dir) / f"locator_{timestamp}.pth", map_location="cpu")

        self.assertEqual(
            payload["meta"]["loss_config"],
            {"locator": {"heatmap": 1.25, "wh": 0.75}},
        )

    def test_vit_b_blink_default_outer_loss_matches_legacy_formula(self):
        trainer = BlinkExpertTrainer.__new__(BlinkExpertTrainer)
        trainer._outer_loss_weights = dict(DEFAULT_BLINK_OUTER_LOSS_WEIGHTS)
        components = [torch.tensor(value) for value in (1.2, 0.4, 0.6, 0.8)]

        actual = trainer._combine_outer_losses(*components)
        legacy = components[0] + 0.35 * components[1] + 0.20 * components[2] + 0.10 * components[3]

        torch.testing.assert_close(actual, legacy, rtol=0, atol=0)
        self.assertAlmostEqual(float(actual.item()), 1.54, places=6)
        self.assertEqual(trainer.loss_config_snapshot, {"outer": DEFAULT_BLINK_OUTER_LOSS_WEIGHTS})

        trainer.part_name = "Mandible"
        trainer.parent_part = "Head"
        trainer.learning_rate = 1e-3
        trainer.weight_decay = 1e-4
        trainer.training_strategy = BLINK_STRATEGY_TRIVIEW_RANDOM
        meta = trainer._build_checkpoint_meta((224, 224), 5, 2, float(actual.item()))
        self.assertEqual(meta["loss_config"], trainer.loss_config_snapshot)

    def test_heatmap_blink_default_inner_and_outer_losses_match_legacy_formula(self):
        trainer = BlinkHeatmapTrainer.__new__(BlinkHeatmapTrainer)
        trainer._outer_loss_weights = dict(DEFAULT_BLINK_OUTER_LOSS_WEIGHTS)
        trainer.center_loss_weight = DEFAULT_HEATMAP_BLINK_COMPONENT_LOSS_WEIGHTS["center"]
        trainer.wh_loss_weight = DEFAULT_HEATMAP_BLINK_COMPONENT_LOSS_WEIGHTS["wh"]

        final_loss = trainer._combine_component_losses(torch.tensor(0.25), torch.tensor(0.5))
        step_loss = trainer._combine_component_losses(torch.tensor(0.1), torch.tensor(0.2))
        view_loss = torch.tensor(0.4)
        consistency_loss = torch.tensor(0.6)
        actual = trainer._combine_outer_losses(final_loss, step_loss, view_loss, consistency_loss)
        legacy = final_loss + 0.35 * step_loss + 0.20 * view_loss + 0.10 * consistency_loss

        torch.testing.assert_close(final_loss, torch.tensor(0.75), rtol=0, atol=0)
        torch.testing.assert_close(actual, legacy, rtol=0, atol=0)
        self.assertAlmostEqual(float(actual.item()), 0.995, places=6)
        self.assertEqual(
            trainer.loss_config_snapshot,
            {
                "outer": DEFAULT_BLINK_OUTER_LOSS_WEIGHTS,
                "components": DEFAULT_HEATMAP_BLINK_COMPONENT_LOSS_WEIGHTS,
            },
        )

        trainer.part_name = "Eye"
        trainer.parent_part = "Head"
        trainer.input_size = (512, 512)
        trainer.heatmap_sigma = 2.0
        trainer.learning_rate = 1e-3
        trainer.weight_decay = 1e-4
        trainer.training_strategy = BLINK_STRATEGY_TRIVIEW_RANDOM
        trainer.model = types.SimpleNamespace(base_channels=24)
        meta = trainer._build_checkpoint_meta((512, 512), 5, 2, float(actual.item()))
        self.assertEqual(meta["loss_config"], trainer.loss_config_snapshot)


if __name__ == "__main__":
    unittest.main()
