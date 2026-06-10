# pyright: reportMissingImports=false

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
from PIL import Image
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if "ultralytics" not in sys.modules:
    ultralytics_stub = types.ModuleType("ultralytics")
    ultralytics_models_stub = types.ModuleType("ultralytics.models")
    ultralytics_models_sam_stub = types.ModuleType("ultralytics.models.sam")

    class _FakeSAM:
        def __init__(self, *args, **kwargs):
            pass

        def predict(self, *args, **kwargs):
            return []

    class _FakePredictor:
        pass

    setattr(ultralytics_stub, "SAM", _FakeSAM)
    setattr(ultralytics_models_sam_stub, "Predictor", _FakePredictor)
    sys.modules["ultralytics"] = ultralytics_stub
    sys.modules["ultralytics.models"] = ultralytics_models_stub
    sys.modules["ultralytics.models.sam"] = ultralytics_models_sam_stub

from AntSleap.core.engine import AntEngine
from AntSleap.core.dataset import TwoStageDataset


class _LazyTrainableSAM(torch.nn.Module):
    constructed = 0

    def __init__(self, model_path=None, device="cpu"):
        super().__init__()
        type(self).constructed += 1
        self.device = torch.device(device if str(device) != "auto" else "cpu")
        self.trainable = torch.nn.Parameter(torch.zeros(1))
        self.sam_model = types.SimpleNamespace(
            mask_decoder=types.SimpleNamespace(state_dict=lambda: {"decoder": torch.zeros(1)})
        )

    def parameters(self, recurse=True):
        return [self.trainable]


class _FakeMaskedCriterion:
    def __call__(self, pred, gt, reduction='mean'):
        loss = (pred - gt) ** 2
        if reduction == 'none':
            return loss
        if reduction == 'sum':
            return loss.sum()
        return loss.mean()


class _FakeWHCriterion:
    def __call__(self, pred, gt):
        return torch.abs(pred - gt)


class _FakeLocatorModel:
    def __init__(self):
        self.loaded_state = None
        self.last_device = None
        self.param = torch.nn.Parameter(torch.zeros(1))

    def state_dict(self):
        return {"outc.conv.weight": torch.zeros((1, 1, 1, 1), dtype=torch.float32)}

    def parameters(self):
        return [self.param]

    def load_state_dict(self, state, strict=False):
        self.loaded_state = dict(state)

    def eval(self):
        return self

    def to(self, device):
        self.last_device = torch.device(device)
        return self

    def __call__(self, _tensor):
        hm = torch.zeros((1, 1, 384, 640), dtype=torch.float32)
        hm[0, 0, 192, 320] = 1.0
        wh = torch.zeros((1, 1, 2), dtype=torch.float32)
        wh[0, 0, 0] = 0.25
        wh[0, 0, 1] = 0.25
        return hm, wh


class _FakePartsModel:
    class _FakeSAMModel:
        def eval(self):
            return None

        class mask_decoder:
            @staticmethod
            def state_dict():
                return {"decoder": torch.tensor([1.0])}

    class _FakePredictor:
        def predict(self, *args, **kwargs):
            return []

    def __init__(self):
        self.sam_model = self._FakeSAMModel()
        self.ultralytics_sam = self._FakePredictor()
        self.device = None
        self.last_device = None
        self.param = torch.nn.Parameter(torch.zeros(1))

    def parameters(self):
        return [self.param]

    def to(self, device):
        self.device = torch.device(device)
        self.last_device = torch.device(device)
        return self


class _FakeCascadeManagerWithCache:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.loaded_experts = {"cached": object()}


class _DeterministicLocatorModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.offset = torch.nn.Parameter(torch.zeros(1, dtype=torch.float32))

    def __call__(self, imgs):
        batch_size = imgs.shape[0]
        heatmap = torch.zeros((batch_size, 2, 8, 8), dtype=torch.float32, device=imgs.device)
        wh = torch.zeros((batch_size, 2, 2), dtype=torch.float32, device=imgs.device)
        heatmap[:, 0, 3, 3] = 1.0
        heatmap[:, 1, 7, 7] = 1.0
        return heatmap + (self.offset.view(1, 1, 1, 1) * 0.0), wh + (self.offset.view(1, 1, 1) * 0.0)


class LocatorResolutionMetadataTests(unittest.TestCase):
    def test_engine_initialization_defers_trainable_sam_until_needed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _LazyTrainableSAM.constructed = 0

            def fake_dirname(path):
                return str(Path(tmp_dir) / "pkg") if str(path).endswith("engine.py") else str(Path(path).parent)

            with patch("AntSleap.core.engine.TrainableSAM", _LazyTrainableSAM), \
                 patch("AntSleap.core.engine.os.path.dirname", side_effect=fake_dirname):
                engine = AntEngine(device="cpu")

                self.assertIsNone(engine.parts_model)
                self.assertIsNone(engine.opt_parts)
                self.assertEqual(_LazyTrainableSAM.constructed, 0)

                parts_model = engine.ensure_parts_model_loaded()

                self.assertIs(parts_model, engine.parts_model)
                self.assertIsNotNone(engine.opt_parts)
                self.assertEqual(_LazyTrainableSAM.constructed, 1)

    def test_runtime_device_switch_moves_builtin_models_and_clears_cascade_cache(self):
        engine = AntEngine.__new__(AntEngine)
        engine.device_preference = "auto"
        engine.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        engine.learning_rate = 1e-4
        engine.weight_decay = 1e-4
        engine.locator = _FakeLocatorModel()
        engine.parts_model = _FakePartsModel()
        engine.opt_loc = torch.optim.SGD([torch.nn.Parameter(torch.zeros(1))], lr=0.1)
        engine.opt_parts = torch.optim.SGD([torch.nn.Parameter(torch.zeros(1))], lr=0.1)
        engine.base_sam_predictor = object()
        engine.cascade_manager = _FakeCascadeManagerWithCache()

        changed = engine.set_device_preference("cpu")

        self.assertTrue(changed)
        self.assertEqual(engine.device_preference, "cpu")
        self.assertEqual(engine.device.type, "cpu")
        self.assertEqual(engine.locator.last_device.type, "cpu")
        self.assertEqual(engine.parts_model.last_device.type, "cpu")
        self.assertEqual(engine.parts_model.device.type, "cpu")
        self.assertIsNone(engine.base_sam_predictor)
        self.assertEqual(engine.cascade_manager.device.type, "cpu")
        self.assertEqual(engine.cascade_manager.loaded_experts, {})

    def test_save_locator_persists_resolution_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            engine = AntEngine.__new__(AntEngine)
            engine.weights_dir = tmp_dir
            engine.locator = _FakeLocatorModel()
            engine.parts_model = _FakePartsModel()
            engine.locator_resolution = (768, 512)
            engine.current_num_classes = 1
            engine.loaded_locator_timestamp = None
            engine.loaded_locator_requires_legacy_confirmation = False
            engine.loaded_locator_is_legacy_512 = False

            timestamp = engine.save_weights(save_locator=True, save_segmenter=False)
            payload = torch.load(Path(tmp_dir) / f"locator_{timestamp}.pth", map_location="cpu")

            self.assertEqual(payload["meta"]["locator_size"], [768, 512])
            self.assertEqual(payload["meta"]["num_classes"], 1)

    def test_load_locator_uses_saved_resolution_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_path = Path(tmp_dir) / "locator_demo.pth"
            torch.save(
                {
                    "state_dict": {"outc.conv.weight": torch.zeros((1, 1, 1, 1), dtype=torch.float32)},
                    "meta": {"locator_size": [640, 384]},
                },
                weights_path,
            )

            engine = AntEngine.__new__(AntEngine)
            engine.device = "cpu"
            engine.weights_dir = tmp_dir
            engine.current_num_classes = 1
            engine.locator = _FakeLocatorModel()
            engine.locator_resolution = (512, 512)
            engine.loaded_locator_timestamp = None
            engine.loaded_locator_requires_legacy_confirmation = False
            engine.loaded_locator_is_legacy_512 = False

            engine.load_locator("demo")

            self.assertEqual(engine.locator_resolution, (640, 384))
            self.assertFalse(engine.loaded_locator_requires_legacy_confirmation)
            self.assertFalse(engine.loaded_locator_is_legacy_512)

    def test_load_locator_requires_confirmation_for_legacy_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_path = Path(tmp_dir) / "locator_legacy.pth"
            torch.save({"outc.conv.weight": torch.zeros((1, 1, 1, 1), dtype=torch.float32)}, weights_path)

            engine = AntEngine.__new__(AntEngine)
            engine.device = "cpu"
            engine.weights_dir = tmp_dir
            engine.current_num_classes = 1
            engine.locator = _FakeLocatorModel()
            engine.locator_resolution = (768, 512)
            engine.loaded_locator_timestamp = None
            engine.loaded_locator_requires_legacy_confirmation = False
            engine.loaded_locator_is_legacy_512 = False

            engine.load_locator("legacy")

            self.assertEqual(engine.locator_resolution, (512, 512))
            self.assertTrue(engine.loaded_locator_requires_legacy_confirmation)
            self.assertTrue(engine.loaded_locator_is_legacy_512)

    def test_predict_full_pipeline_uses_loaded_locator_resolution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "specimen.png"
            Image.new("RGB", (300, 180), color=(180, 180, 180)).save(image_path)

            engine = AntEngine.__new__(AntEngine)
            engine.device = "cpu"
            engine.locator = _FakeLocatorModel()
            engine.parts_model = _FakePartsModel()
            engine.locator_resolution = (640, 384)
            engine.cascade_manager = types.SimpleNamespace(routes_ready=lambda: False)

            with patch.object(engine, "_run_sam_polygon", return_value=None):
                preds = engine.predict_full_pipeline(
                    str(image_path),
                    current_taxonomy=["Head"],
                    locator_scope=["Head"],
                )

            self.assertEqual(preds["meta"]["locator_size"], [640, 384])
            self.assertIn("Head", preds["auto_boxes"])

    def test_locator_dataset_returns_valid_parts_mask_and_safe_fallback(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "sample.png"
            Image.new("RGB", (64, 48), color=(180, 180, 180)).save(image_path)

            dataset = TwoStageDataset(
                [
                    (
                        str(image_path),
                        {
                            "parts": {
                                "Head": [[10, 10], [20, 10], [15, 20]],
                            },
                            "boxes": {},
                        },
                    )
                ],
                ["Head", "Mesosoma"],
                mode="locator",
                input_size=(64, 48),
            )

            img_tensor, hm_target, wh_target, valid_parts_mask = dataset[0]
            self.assertEqual(tuple(img_tensor.shape), (3, 48, 64))
            self.assertEqual(tuple(hm_target.shape), (2, 48, 64))
            self.assertEqual(tuple(wh_target.shape), (2, 2))
            self.assertTrue(torch.equal(valid_parts_mask, torch.tensor([1.0, 0.0])))

            broken_dataset = TwoStageDataset(
                [(str(Path(tmp_dir) / "missing.png"), {"parts": {}, "boxes": {}})],
                ["Head", "Mesosoma"],
                mode="locator",
                input_size=(64, 48),
            )
            broken_sample = broken_dataset[0]
            self.assertEqual(len(broken_sample), 4)
            self.assertTrue(torch.equal(broken_sample[3], torch.zeros(2)))
            self.assertTrue(torch.equal(broken_sample[1], torch.zeros((2, 48, 64))))
            self.assertTrue(torch.equal(broken_sample[2], torch.zeros((2, 2))))

    def test_locator_train_and_validate_ignore_unlabeled_channels(self):
        engine = AntEngine.__new__(AntEngine)
        engine.device = torch.device("cpu")
        engine.crit_heatmap = _FakeMaskedCriterion()
        engine.crit_wh = _FakeWHCriterion()

        model = _DeterministicLocatorModel()
        optimizer = torch.optim.SGD(model.parameters(), lr=0.1)

        imgs = torch.zeros((1, 3, 8, 8), dtype=torch.float32)
        hm_target = torch.zeros((1, 2, 8, 8), dtype=torch.float32)
        hm_target[0, 0, 3, 3] = 1.0
        hm_target[0, 1, 0, 0] = 1.0
        wh_target = torch.zeros((1, 2, 2), dtype=torch.float32)
        valid_parts_mask = torch.tensor([[1.0, 0.0]], dtype=torch.float32)

        dataloader = DataLoader(torch.utils.data.TensorDataset(imgs, hm_target, wh_target, valid_parts_mask), batch_size=1)

        train_loss = engine.train_epoch(dataloader, model, optimizer, None)
        metrics = engine.validate_epoch(dataloader, model)

        self.assertAlmostEqual(train_loss, 0.0, places=6)
        self.assertAlmostEqual(metrics["loss"], 0.0, places=6)
        self.assertAlmostEqual(metrics["pixel_error"], 0.0, places=6)

    def test_locator_validation_returns_nan_when_no_valid_channels_exist(self):
        engine = AntEngine.__new__(AntEngine)
        engine.device = torch.device("cpu")
        engine.crit_heatmap = _FakeMaskedCriterion()
        engine.crit_wh = _FakeWHCriterion()

        model = _DeterministicLocatorModel()
        imgs = torch.zeros((1, 3, 8, 8), dtype=torch.float32)
        hm_target = torch.zeros((1, 2, 8, 8), dtype=torch.float32)
        wh_target = torch.zeros((1, 2, 2), dtype=torch.float32)
        valid_parts_mask = torch.zeros((1, 2), dtype=torch.float32)

        dataloader = DataLoader(torch.utils.data.TensorDataset(imgs, hm_target, wh_target, valid_parts_mask), batch_size=1)
        metrics = engine.validate_epoch(dataloader, model)

        self.assertTrue(torch.isnan(torch.tensor(metrics["pixel_error"])))


if __name__ == "__main__":
    unittest.main()
