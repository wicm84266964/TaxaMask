import unittest

try:
    import torch

    from tif_blink_nnunet.boundary3d import BoundaryBand3DConfig, make_boundary_band_3d
    from tif_blink_nnunet.losses3d import TifBlink3DLossConfig, tif_blink_grouped_loss_3d
    from tif_blink_nnunet.metrics3d import boundary_dice_3d
    from tif_blink_nnunet.nnunet_trainer import nnUNetTrainerTifBlink
    from tif_blink_nnunet.views3d import BlinkView3DConfig, make_blink_views_3d

    HAS_TORCH = True
except ModuleNotFoundError as exc:
    if exc.name != "torch":
        raise
    torch = None
    HAS_TORCH = False

from tif_blink_nnunet.nnunet_trainer import nnUNetTrainerTifBlink


class TifBlinkNnUNetCoreTests(unittest.TestCase):
    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink nnU-Net tests")
    def test_boundary_band_3d_marks_material_interface(self):
        label = torch.zeros((1, 4, 8, 8), dtype=torch.long)
        label[:, :, :, :4] = 1
        label[:, :, :, 4:] = 2
        band = make_boundary_band_3d(label, BoundaryBand3DConfig(radius_xy=1, radius_z=1))
        self.assertEqual(tuple(band.shape), (1, 4, 8, 8))
        self.assertTrue(bool(band[:, :, :, 3].any()))
        self.assertTrue(bool(band[:, :, :, 4].any()))

    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink nnU-Net tests")
    def test_blink_views_3d_shape_and_weakening(self):
        image = torch.ones((1, 1, 3, 6, 6), dtype=torch.float32)
        label = torch.zeros((1, 3, 6, 6), dtype=torch.long)
        label[:, :, :, :3] = 1
        label[:, :, :, 3:] = 2
        views, boundary = make_blink_views_3d(
            image,
            label,
            BlinkView3DConfig(boundary=BoundaryBand3DConfig(radius_xy=1, radius_z=0)),
        )
        self.assertEqual(tuple(views.shape), (1, 3, 1, 3, 6, 6))
        self.assertEqual(tuple(boundary.shape), (1, 3, 6, 6))
        self.assertLess(float(views[:, 1, :, :, :, 0].mean()), 1.0)
        self.assertLess(float(views[:, 2, :, :, :, 3].mean()), 1.0)

    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink nnU-Net tests")
    def test_grouped_loss_3d_is_differentiable(self):
        logits = torch.randn((2, 3, 3, 4, 8, 8), dtype=torch.float32, requires_grad=True)
        target = torch.zeros((2, 4, 8, 8), dtype=torch.long)
        target[:, :, :, :4] = 1
        target[:, :, :, 4:] = 2
        boundary = make_boundary_band_3d(target, BoundaryBand3DConfig(radius_xy=1, radius_z=1))
        loss, parts = tif_blink_grouped_loss_3d(
            logits,
            target,
            boundary,
            TifBlink3DLossConfig(num_classes=3),
        )
        loss.backward()
        self.assertIsNotNone(logits.grad)
        self.assertIn("consistency_loss", parts)

    @unittest.skipUnless(HAS_TORCH, "PyTorch is required for TIF-Blink nnU-Net tests")
    def test_boundary_dice_3d_perfect_prediction(self):
        logits = torch.zeros((1, 3, 3, 4, 4), dtype=torch.float32)
        target = torch.zeros((1, 3, 4, 4), dtype=torch.long)
        target[:, :, :, :2] = 1
        target[:, :, :, 2:] = 2
        logits[:, 1, :, :, :2] = 4.0
        logits[:, 2, :, :, 2:] = 4.0
        boundary = make_boundary_band_3d(target, BoundaryBand3DConfig(radius_xy=1, radius_z=0))
        metric = boundary_dice_3d(logits, target, boundary, num_classes=3)
        self.assertEqual(metric["boundary_dice"], 1.0)

    def test_trainer_symbol_is_importable_without_instantiation(self):
        self.assertEqual(nnUNetTrainerTifBlink.__name__, "nnUNetTrainerTifBlink")


if __name__ == "__main__":
    unittest.main()
