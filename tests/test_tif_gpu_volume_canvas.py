import unittest

from AntSleap.ui import tif_gpu_volume_canvas as gpu_canvas


class TifGpuVolumeCanvasImportTests(unittest.TestCase):
    def test_gpu_volume_canvas_availability_is_import_safe(self):
        available = gpu_canvas.gpu_volume_canvas_available()
        self.assertIsInstance(available, bool)
        reason = gpu_canvas.gpu_volume_unavailable_reason()
        self.assertIsInstance(reason, str)
        if available:
            self.assertIsNotNone(gpu_canvas.TifGpuVolumeCanvas)
            self.assertEqual(reason, "")
        else:
            self.assertTrue(reason)

    def test_rotation_inverse_matrix_shape(self):
        matrix = gpu_canvas._rotation_inverse_matrix(-35.0, 20.0)
        self.assertEqual(matrix.shape, (3, 3))
        self.assertEqual(str(matrix.dtype), "float32")

    def test_volume_shape_scale_uses_source_geometry(self):
        self.assertEqual(gpu_canvas.volume_shape_scale((10, 20, 40)), (1.0, 0.5, 0.25))
        self.assertEqual(gpu_canvas.volume_shape_scale((10, 20, 40), (2.0, 1.0, 1.0)), (1.0, 0.5, 0.5))
        self.assertEqual(gpu_canvas.volume_shape_scale(()), (1.0, 1.0, 1.0))

    def test_inside_camera_can_enter_past_volume_center(self):
        matrix = gpu_canvas._rotation_inverse_matrix(0.0, 0.0)
        outside = gpu_canvas.camera_distance_for_inside_zoom((1.0, 1.0, 1.0), matrix, 1.0, 0.0)
        outside_zoomed = gpu_canvas.camera_distance_for_inside_zoom((1.0, 1.0, 1.0), matrix, 8.0, 0.0)
        center = gpu_canvas.camera_distance_for_inside_zoom((1.0, 1.0, 1.0), matrix, 1.0, 1.0)
        deeper = gpu_canvas.camera_distance_for_inside_zoom((1.0, 1.0, 1.0), matrix, 1.0, 1.6)
        self.assertGreater(outside, 0.0)
        self.assertEqual(outside_zoomed, outside)
        self.assertEqual(center, 0.0)
        self.assertLess(deeper, 0.0)
        self.assertGreater(deeper, -0.5)

    def test_front_clip_discards_viewer_side_ray_segment(self):
        self.assertEqual(gpu_canvas.front_clip_start_t(-0.5, 1.5, 0.0), 0.0)
        self.assertAlmostEqual(gpu_canvas.front_clip_start_t(-0.5, 1.5, 0.5), 0.75)
        self.assertAlmostEqual(gpu_canvas.front_clip_start_t(0.2, 1.2, 0.25), 0.45)

    def test_renderer_text_is_compacted_for_status_overlay(self):
        self.assertEqual(
            gpu_canvas._compact_renderer_text("NVIDIA GeForce RTX 3090/PCIe/SSE2"),
            "RTX 3090",
        )
        self.assertEqual(gpu_canvas._compact_renderer_text(""), "")
        self.assertIn("u_camera_distance", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_front_clip", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("clip_depth", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("dot(near_point, view_axis)", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_gradient_weight", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_texel_step", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("accum.rgb", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("accum.a > 0.985", gpu_canvas._FRAGMENT_SHADER)
        self.assertEqual(gpu_canvas.GPU_VOLUME_MAX_TEXTURE_DIM, 4096)
        self.assertEqual(gpu_canvas.GPU_VOLUME_MAX_RAY_STEPS, 4096)
        self.assertIn("MAX_RAY_STEPS = 4096", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_clarity", gpu_canvas._FRAGMENT_SHADER)


if __name__ == "__main__":
    unittest.main()
