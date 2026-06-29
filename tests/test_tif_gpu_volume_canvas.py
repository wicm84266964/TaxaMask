import unittest
from unittest.mock import patch

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
        self.assertIn("front_clip_start_t", gpu_canvas._FRAGMENT_SHADER)
        self.assertNotIn("front_clip_discards", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_gradient_weight", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_texel_step", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("accum.rgb", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("accum.a > 0.985", gpu_canvas._FRAGMENT_SHADER)
        self.assertEqual(gpu_canvas.GPU_VOLUME_MAX_TEXTURE_DIM, 4096)
        self.assertEqual(gpu_canvas.GPU_VOLUME_MAX_RAY_STEPS, 4096)
        self.assertIn("MAX_RAY_STEPS = 4096", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_clarity", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_transfer_lut", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("uniform sampler3D u_mask", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("uniform int u_mask_mode", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("uniform vec3 u_tint_rgb", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("mask_boundary_sample", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_enhancement", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("tetra_gradient", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_jitter_strength", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_adaptive_step_strength", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("hash12", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_gradient_opacity", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_gradient_opacity_range", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("gradient_opacity_density", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_clip_plane_enabled", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("clip_plane_discards", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("clip_plane_extent", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("section_plane_color", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("section_accum", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("vec4 transfer = transfer_sample", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("vec3 gray = vec3", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("float section_surface", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("vec3 tint = normalize", gpu_canvas._FRAGMENT_SHADER)
        source = gpu_canvas.__loader__.get_source(gpu_canvas.__name__)
        self.assertIn('self._set_uniform_vec3("u_tint_rgb"', source)
        self.assertIn('self._set_uniform_float("u_opacity", max(0.0, min(1.4, float(getattr(self, "_transfer_opacity", 1.0)))))', source)
        self.assertNotIn('self._set_uniform_float("u_opacity", 1.0)', source)
        self.assertIn("color += transfer.rgb * edge", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("section_accum.a * 0.76", gpu_canvas._FRAGMENT_SHADER)
        self.assertNotIn("section_accum.a * 0.48", gpu_canvas._FRAGMENT_SHADER)
        self.assertNotIn("section_accum.a * 0.96", gpu_canvas._FRAGMENT_SHADER)
        self.assertIn("u_surface_refine", gpu_canvas._FRAGMENT_SHADER)
        self.assertEqual(gpu_canvas.GPU_VOLUME_MASK_MODES["image_only"], 0)
        self.assertEqual(gpu_canvas.GPU_VOLUME_MASK_MODES["mask_boundary"], 1)
        self.assertEqual(gpu_canvas.GPU_VOLUME_MASK_MODES["masked_image"], 2)

    def test_shader_quality_settings_are_explicit_and_transfer_driven(self):
        self.assertEqual(gpu_canvas._jitter_strength_for_render("drag", "composite", 0.65), 0.0)
        self.assertEqual(gpu_canvas._jitter_strength_for_render("still", "mip", 0.65), 0.0)
        self.assertAlmostEqual(gpu_canvas._jitter_strength_for_render("still", "composite", 0.0), 0.28)
        self.assertAlmostEqual(gpu_canvas._jitter_strength_for_render("still", "composite", 0.65), 0.42)
        self.assertAlmostEqual(gpu_canvas._adaptive_step_strength_for_render("still", "composite"), 0.35)
        self.assertEqual(gpu_canvas._adaptive_step_strength_for_render("drag", "composite"), 0.0)
        self.assertEqual(gpu_canvas._adaptive_step_strength_for_render("still", "mip"), 0.0)
        self.assertEqual(gpu_canvas._adaptive_step_strength_for_render("still", "composite", "mask_boundary"), 0.0)
        self.assertEqual(gpu_canvas._adaptive_step_strength_for_render("still", "composite", "image_only", True), 0.0)

        amber_strength, amber_range = gpu_canvas._gradient_opacity_settings("amber", "still", "preset")
        morphology_strength, morphology_range = gpu_canvas._gradient_opacity_settings("morphology", "still")
        publication_strength, publication_range = gpu_canvas._gradient_opacity_settings("publication", "still")

        self.assertEqual(amber_strength, 0.0)
        self.assertEqual(amber_range, (0.04, 0.34))
        self.assertAlmostEqual(morphology_strength, 0.65)
        self.assertEqual(morphology_range, (0.04, 0.34))
        self.assertAlmostEqual(publication_strength, 0.45)
        self.assertEqual(publication_range, (0.08, 0.42))
        self.assertEqual(gpu_canvas._gradient_opacity_settings("morphology", "drag")[0], 0.0)

        still_settings = gpu_canvas.volume_shader_quality_settings("amber", "still", "composite")
        self.assertEqual(still_settings["shader_quality_mode"], "preset")
        self.assertEqual(still_settings["jitter_strength"], 0.0)
        self.assertEqual(still_settings["adaptive_step_strength"], 0.0)
        all_still_settings = gpu_canvas.volume_shader_quality_settings("amber", "still", "composite", quality_mode="all_still")
        self.assertAlmostEqual(all_still_settings["adaptive_step_strength"], 0.35)
        self.assertGreater(all_still_settings["jitter_strength"], 0.0)
        off_settings = gpu_canvas.volume_shader_quality_settings("morphology", "still", "composite", quality_mode="off")
        self.assertEqual(off_settings["jitter_strength"], 0.0)
        self.assertEqual(off_settings["adaptive_step_strength"], 0.0)
        self.assertEqual(off_settings["gradient_opacity"], 0.0)
        masked_settings = gpu_canvas.volume_shader_quality_settings("morphology", "still", "composite", "masked_image")
        self.assertEqual(masked_settings["adaptive_step_strength"], 0.0)

    def test_grayscale_volume_sampling_stays_linear_when_still_or_clipped(self):
        self.assertEqual(gpu_canvas._texture_filter_name(True, "still"), "linear")
        self.assertEqual(gpu_canvas._display_scaling_name(True, "still"), "smooth")
        self.assertEqual(gpu_canvas._texture_filter_name(False, "still", True), "linear")
        self.assertEqual(gpu_canvas._display_scaling_name(False, "still", True), "smooth")
        self.assertEqual(gpu_canvas._texture_filter_name(True, "drag"), "linear")
        self.assertEqual(gpu_canvas._display_scaling_name(False, "still"), "smooth")

    def test_gpu_pan_limit_scales_with_zoom(self):
        self.assertEqual(gpu_canvas.volume_pan_limit_for_zoom(1.0), 8.0)
        self.assertEqual(gpu_canvas.volume_pan_limit_for_zoom(16.0), 36.0)

    def test_transfer_lut_presets_are_distinct_and_alpha_ramps_up(self):
        amber = gpu_canvas.build_volume_transfer_lut("amber", (1.0, 0.83, 0.30), opacity=1.0)
        cyan = gpu_canvas.build_volume_transfer_lut("cyan", (0.3, 0.9, 1.0), opacity=1.0)
        custom = gpu_canvas.build_volume_transfer_lut("custom", (0.9, 0.2, 0.2), opacity=0.5)

        self.assertEqual(amber.shape, (1, gpu_canvas.GPU_VOLUME_TRANSFER_LUT_SIZE, 4))
        self.assertEqual(str(amber.dtype), "uint8")
        self.assertGreater(int(amber[0, -1, 3]), int(amber[0, 4, 3]))
        self.assertFalse((amber[0, 180, :3] == cyan[0, 180, :3]).all())
        self.assertLess(int(custom[0, -1, 3]), int(amber[0, -1, 3]))

    def test_gpu_texture_cache_budget_env_parser(self):
        import os

        old = os.environ.get("TAXAMASK_TIF_GPU_TEXTURE_CACHE_GB")
        try:
            os.environ["TAXAMASK_TIF_GPU_TEXTURE_CACHE_GB"] = "1.5"
            self.assertEqual(gpu_canvas._gpu_texture_cache_budget_bytes(), int(1.5 * 1024 * 1024 * 1024))
            os.environ["TAXAMASK_TIF_GPU_TEXTURE_CACHE_GB"] = "0"
            self.assertEqual(gpu_canvas._gpu_texture_cache_budget_bytes(), 0)
            os.environ["TAXAMASK_TIF_GPU_TEXTURE_CACHE_GB"] = "bad"
            self.assertEqual(gpu_canvas._gpu_texture_cache_budget_bytes(), gpu_canvas.GPU_VOLUME_TEXTURE_CACHE_DEFAULT_BUDGET_BYTES)
            self.assertEqual(gpu_canvas.GPU_VOLUME_TEXTURE_CACHE_DEFAULT_BUDGET_BYTES, 2 * 1024 * 1024 * 1024)
        finally:
            if old is None:
                os.environ.pop("TAXAMASK_TIF_GPU_TEXTURE_CACHE_GB", None)
            else:
                os.environ["TAXAMASK_TIF_GPU_TEXTURE_CACHE_GB"] = old

    def test_gpu_render_core_cache_activation_skips_reupload(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        key = ("owner", "volume", 1)
        record_key = core._texture_cache_record_key(key, "volume")
        core._texture_cache[record_key] = {
            "texture_id": 17,
            "kind": "volume",
            "shape": (2, 3, 4),
            "dtype": "uint8",
            "bytes": 24,
        }
        core._texture_cache_bytes = 24

        self.assertTrue(core._store_volume_data(gpu_canvas.np.zeros((2, 3, 4), dtype=gpu_canvas.np.uint8), cache_key=key))

        self.assertEqual(core._texture_id, 17)
        self.assertFalse(core._upload_needed)
        self.assertEqual(core._uploaded_shape, (2, 3, 4))
        self.assertEqual(core.render_stats()["texture_cache_hits"], 1)

    def test_gpu_texture_cache_eviction_prefers_non_active_owner_and_mask(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._texture_cache_budget_bytes = 100
        active_owner = ("active", "full", "", "")
        other_owner = ("other", "full", "", "")
        active_key = (active_owner, "volume-active")
        active_record_key = core._texture_cache_record_key(active_key, "volume")
        other_volume_key = (other_owner, "volume")
        other_mask_key = (other_owner, "mask")
        active_mask_key = (active_owner, "mask")
        for key, kind, texture_id in (
            (active_key, "volume", 1),
            (other_volume_key, "volume", 2),
            (other_mask_key, "mask", 3),
            (active_mask_key, "mask", 4),
        ):
            core._texture_cache[core._texture_cache_record_key(key, kind)] = {
                "texture_id": texture_id,
                "kind": kind,
                "owner": core._texture_cache_owner_from_key(key),
                "shape": (1, 1, 1),
                "dtype": "uint8",
                "bytes": 60,
            }
        core._texture_cache_bytes = 240
        core._texture_id = 1
        core._volume_cache_key = active_key

        candidate_key, candidate = core._texture_cache_eviction_candidate()

        self.assertEqual(candidate["texture_id"], 3)
        self.assertNotEqual(candidate_key, active_record_key)

    def test_cached_texture_delete_detaches_without_deleting_lru_entry(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        key = (("owner", "full", "", ""), "volume")
        record_key = core._texture_cache_record_key(key, "volume")
        core._texture_cache[record_key] = {
            "texture_id": 33,
            "kind": "volume",
            "owner": core._texture_cache_owner_from_key(key),
            "shape": (1, 1, 1),
            "dtype": "uint8",
            "bytes": 1,
        }
        core._texture_id = 33
        core._initialized = True

        with patch.object(gpu_canvas.GL, "glDeleteTextures") as delete_textures:
            core._delete_volume_texture()

        delete_textures.assert_not_called()
        self.assertIsNone(core._texture_id)
        self.assertIn(record_key, core._texture_cache)

    def test_release_texture_cache_deletes_records_and_detaches_active_ids(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        key = (("owner", "full", "", ""), "volume")
        record_key = core._texture_cache_record_key(key, "volume")
        core._texture_cache[record_key] = {
            "texture_id": 44,
            "kind": "volume",
            "owner": core._texture_cache_owner_from_key(key),
            "shape": (1, 1, 1),
            "dtype": "uint8",
            "bytes": 1,
        }
        core._texture_cache_bytes = 1
        core._texture_id = 44
        core._initialized = True

        with patch.object(gpu_canvas.GL, "glDeleteTextures") as delete_textures:
            core._release_texture_cache()

        delete_textures.assert_called_once()
        self.assertEqual(len(core._texture_cache), 0)
        self.assertEqual(core._texture_cache_bytes, 0)
        self.assertIsNone(core._texture_id)

    def test_prune_texture_cache_keeps_only_active_when_active_exceeds_budget(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._texture_cache_budget_bytes = 100
        active_key = (("active", "full", "", ""), "volume")
        stale_key = (("stale", "full", "", ""), "volume")
        active_record_key = core._texture_cache_record_key(active_key, "volume")
        stale_record_key = core._texture_cache_record_key(stale_key, "volume")
        core._texture_cache[stale_record_key] = {
            "texture_id": 55,
            "kind": "volume",
            "owner": core._texture_cache_owner_from_key(stale_key),
            "shape": (1, 1, 1),
            "dtype": "uint8",
            "bytes": 80,
        }
        core._texture_cache[active_record_key] = {
            "texture_id": 66,
            "kind": "volume",
            "owner": core._texture_cache_owner_from_key(active_key),
            "shape": (1, 1, 1),
            "dtype": "uint8",
            "bytes": 160,
        }
        core._texture_cache_bytes = 240
        core._texture_id = 66
        core._volume_cache_key = active_key
        core._initialized = True

        with patch.object(gpu_canvas.GL, "glDeleteTextures") as delete_textures:
            core._prune_texture_cache()

        delete_textures.assert_called_once()
        self.assertIn(active_record_key, core._texture_cache)
        self.assertNotIn(stale_record_key, core._texture_cache)
        self.assertEqual(core._texture_cache_bytes, 160)


if __name__ == "__main__":
    unittest.main()
