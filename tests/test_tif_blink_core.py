import unittest
from pathlib import Path
import tempfile

import numpy as np

from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar, write_volume_sidecar
from tif_blink.boundary import BoundaryBandConfig, make_boundary_band
from tif_blink.labels import build_label_mapping, decode_label, encode_label
from tif_blink.preprocess import input_channel_count, normalize_stack_percentile, slice_stack
from tif_blink.sampler import BalancedSliceSamplerConfig, sampler_weights_from_densities
from tif_blink.taxamask_io import load_train_ready_samples, save_prediction_as_model_draft
from tif_blink.views import BlinkViewConfig, make_blink_view

try:
    import torch

    from tif_blink.dataset import TifBlinkDatasetConfig, TifBlinkGroupedSliceDataset, TifBlinkSample, TifBlinkSliceDataset
    from tif_blink.losses import consistency_loss, masked_cross_entropy, masked_dice_loss
    from tif_blink.metrics import boundary_dice
    from tif_blink.model import TifBlinkUNet2D
    from tif_blink.train import TifBlinkTrainConfig, train_model, train_one_epoch

    HAS_TORCH = True
except ModuleNotFoundError as exc:
    if exc.name != "torch":
        raise
    torch = None
    HAS_TORCH = False


class TifBlinkCoreTests(unittest.TestCase):
    def test_boundary_band_marks_material_interfaces(self):
        label = np.zeros((8, 8), dtype=np.uint16)
        label[:, :4] = 1
        label[:, 4:] = 2
        band = make_boundary_band(label, BoundaryBandConfig(radius_xy=1))
        self.assertTrue(np.any(band[:, 3]))
        self.assertTrue(np.any(band[:, 4]))
        self.assertFalse(np.any(band[:, 0]))

    def test_boundary_band_excludes_background_edges_by_default(self):
        label = np.zeros((8, 8), dtype=np.uint16)
        label[2:6, 2:6] = 1
        band = make_boundary_band(label, BoundaryBandConfig(radius_xy=1))
        self.assertFalse(np.any(band))

    def test_boundary_band_can_include_background_edges(self):
        label = np.zeros((8, 8), dtype=np.uint16)
        label[2:6, 2:6] = 1
        band = make_boundary_band(
            label,
            BoundaryBandConfig(radius_xy=1, include_background_boundary=True),
        )
        self.assertTrue(np.any(band[1:7, 1:7]))

    def test_blink_inside_and_outside_views_use_boundary_band(self):
        image = np.ones((1, 6, 6), dtype=np.float32)
        image[:, :, :] = 3.0
        band = np.zeros((6, 6), dtype=bool)
        band[:, 2:4] = True

        inside = make_blink_view(image, band, BlinkViewConfig(mode="inside_band", outside_scale=0.0))
        outside = make_blink_view(image, band, BlinkViewConfig(mode="outside_band", inside_scale=0.0))

        self.assertEqual(float(inside[:, 0, 0].max()), 0.0)
        self.assertEqual(float(inside[:, 3, 3].max()), 3.0)
        self.assertEqual(float(outside[:, 0, 0].max()), 3.0)
        self.assertEqual(float(outside[:, 3, 3].max()), 0.0)

    def test_blink_view_broadcasts_boundary_band_over_channels(self):
        image = np.stack(
            [
                np.full((4, 4), 2.0, dtype=np.float32),
                np.full((4, 4), 5.0, dtype=np.float32),
                np.full((4, 4), 9.0, dtype=np.float32),
            ],
            axis=0,
        )
        band = np.zeros((4, 4), dtype=bool)
        band[1:3, 1:3] = True
        inside = make_blink_view(image, band, BlinkViewConfig(mode="inside_band", outside_scale=0.0))
        self.assertEqual(float(inside[0, 0, 0]), 0.0)
        self.assertEqual(float(inside[0, 1, 1]), 2.0)
        self.assertEqual(float(inside[1, 1, 1]), 5.0)
        self.assertEqual(float(inside[2, 1, 1]), 9.0)

    def test_label_mapping_handles_non_contiguous_material_ids(self):
        label = np.array([[0, 5, 5], [12, 12, 5]], dtype=np.uint16)
        mapping = build_label_mapping([label])
        encoded = encode_label(label, mapping)
        decoded = decode_label(encoded, mapping)
        self.assertEqual(mapping.label_id_to_class[0], 0)
        self.assertEqual(mapping.label_id_to_class[5], 1)
        self.assertEqual(mapping.label_id_to_class[12], 2)
        np.testing.assert_array_equal(decoded, label)

    def test_preprocess_reports_inference_safe_channel_count(self):
        self.assertEqual(input_channel_count(context_slices=0), 1)
        self.assertEqual(input_channel_count(context_slices=1), 3)
        self.assertEqual(input_channel_count(context_slices=1, include_boundary_channel=True), 4)

    def test_slice_stack_clamps_context_at_volume_edges(self):
        volume = np.arange(3 * 2 * 2, dtype=np.float32).reshape(3, 2, 2)
        stack = slice_stack(volume, z_index=0, context_slices=1)
        self.assertEqual(tuple(stack.shape), (3, 2, 2))
        np.testing.assert_array_equal(stack[0], volume[0])
        np.testing.assert_array_equal(stack[1], volume[0])
        np.testing.assert_array_equal(stack[2], volume[1])

    def test_percentile_normalization_handles_constant_input(self):
        stack = np.full((3, 4, 4), 7.0, dtype=np.float32)
        normalized = normalize_stack_percentile(stack)
        self.assertTrue(np.all(normalized == 0.0))

    def test_sampler_weights_clip_abnormally_dense_boundaries(self):
        weights = sampler_weights_from_densities(
            [0.0, 0.2, 0.7],
            BalancedSliceSamplerConfig(boundary_bias=4.0, max_boundary_density=0.6),
        )
        self.assertEqual([round(float(value), 3) for value in weights.tolist()], [1.0, 1.8, 1.0])

    def test_taxamask_io_loads_train_ready_manual_truth_and_saves_draft_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("tif_blink_io", root / "project")
            manager.create_specimen_scaffold(
                "brain-01",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 5, "name": "region", "display_name": "Region", "trainable": True},
                    ]
                },
            )
            image = np.arange(2 * 3 * 4, dtype=np.uint8).reshape(2, 3, 4)
            manual = np.zeros((2, 3, 4), dtype=np.uint16)
            manual[:, :, 2:] = 5
            image_rel = "specimens/brain-01/working/image.ome.zarr"
            manual_rel = "specimens/brain-01/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(root / "project" / image_rel, image, role="working_image")
            manual_meta = write_volume_sidecar(root / "project" / manual_rel, manual, role="manual_truth")
            manager.register_working_volume("brain-01", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("brain-01", "manual_truth", manual_rel, manual_meta["shape_zyx"], manual_meta["dtype"], save=False)
            manager.set_review_status("brain-01", "train_ready", train_ready=True)

            samples = load_train_ready_samples(manager, ["brain-01"])
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0].specimen_id, "brain-01")
            np.testing.assert_array_equal(samples[0].label, manual)

            prediction = np.full((2, 3, 4), 5, dtype=np.uint16)
            result = save_prediction_as_model_draft(
                manager,
                "brain-01",
                prediction,
                prediction_id="tif_blink_unit",
                source_model="tif_blink_test",
            )
            specimen = manager.get_specimen("brain-01")
            draft = specimen["labels"]["model_drafts"][0]
            draft_array = load_volume_sidecar(manager.to_absolute(draft["path"]))
            manual_array = load_volume_sidecar(manager.to_absolute(specimen["labels"]["manual_truth"]["path"]))

            self.assertEqual(draft["role"], "model_draft")
            self.assertEqual(draft["prediction_report"], result["report"]["files"]["prediction_report"])
            self.assertFalse(result["report"]["safety"]["manual_truth_overwritten"])
            np.testing.assert_array_equal(draft_array, prediction)
            np.testing.assert_array_equal(manual_array, manual)

    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink grouped dataset tests")
    def test_grouped_slice_dataset_returns_three_views(self):
        image = np.ones((2, 6, 6), dtype=np.float32)
        label = np.zeros((2, 6, 6), dtype=np.uint16)
        label[:, :, :3] = 1
        label[:, :, 3:] = 2
        dataset = TifBlinkGroupedSliceDataset(
            [TifBlinkSample(image=image, label=label, specimen_id="brain")],
            TifBlinkDatasetConfig(context_slices=0, view_modes=("normal", "inside_band", "outside_band")),
        )
        item = dataset[0]
        self.assertEqual(tuple(item["images"].shape), (3, 1, 6, 6))
        self.assertEqual(tuple(item["label"].shape), (6, 6))
        self.assertEqual(tuple(item["boundary"].shape), (6, 6))
        self.assertEqual(tuple(item["view_modes"]), ("normal", "inside_band", "outside_band"))

    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink loss tests")
    def test_masked_losses_and_consistency_are_differentiable(self):
        logits_a = torch.randn((2, 3, 5, 5), dtype=torch.float32, requires_grad=True)
        logits_b = torch.randn((2, 3, 5, 5), dtype=torch.float32, requires_grad=True)
        labels = torch.randint(0, 3, (2, 5, 5), dtype=torch.int64)
        mask = torch.zeros((2, 5, 5), dtype=torch.float32)
        mask[:, 1:4, 1:4] = 1.0
        loss = (
            masked_cross_entropy(logits_a, labels, mask=mask)
            + masked_dice_loss(logits_a, labels, num_classes=3, mask=mask)
            + consistency_loss(logits_a, logits_b, mask=mask)
        )
        loss.backward()
        self.assertIsNotNone(logits_a.grad)
        self.assertIsNotNone(logits_b.grad)

    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink metric tests")
    def test_boundary_dice_focuses_on_boundary_band(self):
        logits = torch.zeros((1, 3, 4, 4), dtype=torch.float32)
        target = torch.zeros((1, 4, 4), dtype=torch.int64)
        target[:, :, :2] = 1
        target[:, :, 2:] = 2
        logits[:, 1, :, :2] = 5.0
        logits[:, 2, :, 2:] = 5.0
        boundary = torch.zeros((1, 4, 4), dtype=torch.float32)
        boundary[:, :, 1:3] = 1.0
        metric = boundary_dice(logits, target, boundary, num_classes=3)
        self.assertEqual(metric["boundary_dice"], 1.0)

    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink dataset tests")
    def test_slice_dataset_returns_2_5d_channels_and_boundary(self):
        image = np.arange(3 * 8 * 8, dtype=np.float32).reshape(3, 8, 8)
        label = np.zeros((3, 8, 8), dtype=np.uint16)
        label[:, :, :4] = 1
        label[:, :, 4:] = 2
        dataset = TifBlinkSliceDataset(
            [TifBlinkSample(image=image, label=label, specimen_id="brain")],
            TifBlinkDatasetConfig(context_slices=1, view_modes=("normal",)),
        )
        item = dataset[1]
        self.assertEqual(tuple(item["image"].shape), (3, 8, 8))
        self.assertEqual(tuple(item["label"].shape), (8, 8))
        self.assertEqual(tuple(item["boundary"].shape), (8, 8))
        self.assertEqual(item["specimen_id"], "brain")

    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink model tests")
    def test_unet_forward_preserves_spatial_shape(self):
        model = TifBlinkUNet2D(in_channels=3, num_classes=3, base_channels=4)

        out = model(torch.zeros((2, 3, 17, 19), dtype=torch.float32))
        self.assertEqual(tuple(out.shape), (2, 3, 17, 19))

    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink training tests")
    def test_training_smoke_updates_on_tiny_dataset(self):
        image = np.zeros((2, 12, 12), dtype=np.float32)
        label = np.zeros((2, 12, 12), dtype=np.uint16)
        label[:, :, :6] = 1
        label[:, :, 6:] = 2
        dataset = TifBlinkSliceDataset(
            [TifBlinkSample(image=image, label=label)],
            TifBlinkDatasetConfig(context_slices=0, view_modes=("normal",)),
        )
        model = TifBlinkUNet2D(in_channels=1, num_classes=3, base_channels=4)
        loss = train_one_epoch(
            model,
            dataset,
            TifBlinkTrainConfig(
                num_classes=3,
                in_channels=1,
                context_slices=0,
                base_channels=4,
                batch_size=1,
                device="cpu",
            ),
        )
        self.assertGreater(loss, 0.0)

    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink grouped training tests")
    def test_grouped_training_smoke_saves_history_and_checkpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = np.zeros((2, 12, 12), dtype=np.float32)
            label = np.zeros((2, 12, 12), dtype=np.uint16)
            image[:, :, :6] = 0.25
            image[:, :, 6:] = 0.75
            label[:, :, :6] = 1
            label[:, :, 6:] = 2
            dataset = TifBlinkGroupedSliceDataset(
                [TifBlinkSample(image=image, label=label, specimen_id="brain")],
                TifBlinkDatasetConfig(context_slices=0, view_modes=("normal", "inside_band", "outside_band")),
            )
            result = train_model(
                dataset,
                TifBlinkTrainConfig(
                    num_classes=3,
                    in_channels=1,
                    context_slices=0,
                    base_channels=4,
                    epochs=1,
                    batch_size=1,
                    device="cpu",
                    output_dir=tmp,
                    use_grouped_views=True,
                ),
                trained_specimens=["brain"],
            )
            self.assertTrue(Path(result["best_checkpoint"]).exists())
            self.assertTrue(Path(result["last_checkpoint"]).exists())
            self.assertIn("consistency_loss", result["history"][0]["train"])
            self.assertIn("boundary_dice", result["history"][0]["train"])


if __name__ == "__main__":
    unittest.main()
