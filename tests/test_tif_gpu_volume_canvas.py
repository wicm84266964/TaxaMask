import unittest
from contextlib import ExitStack
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
            self.assertEqual(gpu_canvas.GPU_VOLUME_TEXTURE_CACHE_DEFAULT_BUDGET_BYTES, 5 * 1024 * 1024 * 1024)
        finally:
            if old is None:
                os.environ.pop("TAXAMASK_TIF_GPU_TEXTURE_CACHE_GB", None)
            else:
                os.environ["TAXAMASK_TIF_GPU_TEXTURE_CACHE_GB"] = old

    def test_volume_texture_format_prefers_modern_single_channel_formats(self):
        class FakeModernGL:
            GL_R16 = 101
            GL_R8 = 102
            GL_RED = 103
            GL_UNSIGNED_SHORT = 104
            GL_UNSIGNED_BYTE = 105
            GL_LUMINANCE16 = 201
            GL_LUMINANCE = 202

        self.assertEqual(gpu_canvas._volume_texture_format(gpu_canvas.np.uint16, FakeModernGL()), (101, 103, 104, "r16"))
        self.assertEqual(gpu_canvas._volume_texture_format(gpu_canvas.np.uint8, FakeModernGL()), (102, 103, 105, "r8"))

    def test_volume_texture_format_falls_back_to_luminance_when_needed(self):
        class FakeLegacyGL:
            GL_UNSIGNED_SHORT = 104
            GL_UNSIGNED_BYTE = 105
            GL_LUMINANCE16 = 201
            GL_LUMINANCE = 202

        self.assertEqual(gpu_canvas._volume_texture_format(gpu_canvas.np.uint16, FakeLegacyGL()), (201, 202, 104, "luminance16"))
        self.assertEqual(gpu_canvas._volume_texture_format(gpu_canvas.np.uint8, FakeLegacyGL()), (202, 202, 105, "luminance8"))

    def test_budget_limited_preview_shape_degrades_to_fit_texture_budget(self):
        plan = gpu_canvas._budget_limited_preview_shape((512, 512, 512), 512, 2, 32 * 1024 * 1024, 4096)

        self.assertTrue(plan["degraded"])
        self.assertEqual(plan["degrade_reason"], "texture_budget")
        self.assertLess(plan["bytes"], 512 * 512 * 512 * 2)
        self.assertLessEqual(plan["bytes"], 32 * 1024 * 1024)

    def test_gpu_preview_build_probe_is_safe_without_current_context(self):
        class FakeNoContextGL:
            GL_VENDOR = 1
            GL_RENDERER = 2
            GL_VERSION = 3

            def glGetString(self, _name):
                return None

        capabilities = gpu_canvas.probe_gpu_preview_build_capabilities(FakeNoContextGL())

        self.assertFalse(capabilities.available)
        self.assertEqual(capabilities.backend, gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_UNAVAILABLE)
        self.assertIn("current context", capabilities.reason)

    def test_gpu_preview_build_probe_detects_compute_backend(self):
        class FakeComputeGL:
            GL_VENDOR = 1
            GL_RENDERER = 2
            GL_VERSION = 3
            GL_EXTENSIONS = 4
            GL_MAX_3D_TEXTURE_SIZE = 5
            GL_MAX_COMPUTE_WORK_GROUP_COUNT = 6
            GL_MAX_COMPUTE_WORK_GROUP_SIZE = 7
            GL_R16 = 10
            GL_RED = 11
            GL_UNSIGNED_SHORT = 12

            def glGetString(self, name):
                values = {
                    self.GL_VENDOR: b"TestVendor",
                    self.GL_RENDERER: b"TestRenderer",
                    self.GL_VERSION: b"4.6 Test",
                    self.GL_EXTENSIONS: b"GL_ARB_compute_shader GL_ARB_shader_image_load_store GL_ARB_sync",
                }
                return values.get(name, b"")

            def glGetIntegerv(self, name):
                if name == self.GL_MAX_3D_TEXTURE_SIZE:
                    return 4096
                if name == self.GL_MAX_COMPUTE_WORK_GROUP_COUNT:
                    return (65535, 65535, 65535)
                if name == self.GL_MAX_COMPUTE_WORK_GROUP_SIZE:
                    return (1024, 1024, 64)
                return 0

            def glDispatchCompute(self, *_args):
                return None

            def glFenceSync(self, *_args):
                return None

        capabilities = gpu_canvas.probe_gpu_preview_build_capabilities(FakeComputeGL())

        self.assertTrue(capabilities.available)
        self.assertEqual(capabilities.backend, gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_COMPUTE)
        self.assertTrue(capabilities.supports_compute_shader)
        self.assertTrue(capabilities.supports_image_load_store)
        self.assertTrue(capabilities.supports_r16_texture)
        self.assertEqual(capabilities.max_3d_texture_size, 4096)
        self.assertEqual(capabilities.to_stats()["renderer"], "TestRenderer")

    def test_gpu_preview_build_probe_accepts_opengl_es_compute(self):
        class FakeOpenGLESComputeGL:
            GL_VENDOR = 1
            GL_RENDERER = 2
            GL_VERSION = 3
            GL_EXTENSIONS = 4
            GL_MAX_3D_TEXTURE_SIZE = 5
            GL_MAX_COMPUTE_WORK_GROUP_COUNT = 6
            GL_MAX_COMPUTE_WORK_GROUP_SIZE = 7
            GL_R16 = 10
            GL_RED = 11
            GL_UNSIGNED_SHORT = 12

            def glGetString(self, name):
                values = {
                    self.GL_VENDOR: b"TestVendor",
                    self.GL_RENDERER: b"TestES",
                    self.GL_VERSION: b"OpenGL ES 3.1 Test",
                    self.GL_EXTENSIONS: b"GL_ARB_shader_image_load_store GL_ARB_sync",
                }
                return values.get(name, b"")

            def glGetIntegerv(self, name):
                if name == self.GL_MAX_3D_TEXTURE_SIZE:
                    return 2048
                if name == self.GL_MAX_COMPUTE_WORK_GROUP_COUNT:
                    return (1024, 1024, 1024)
                if name == self.GL_MAX_COMPUTE_WORK_GROUP_SIZE:
                    return (256, 256, 64)
                return 0

            def glDispatchCompute(self, *_args):
                return None

            def glFenceSync(self, *_args):
                return None

        capabilities = gpu_canvas.probe_gpu_preview_build_capabilities(FakeOpenGLESComputeGL())

        self.assertTrue(capabilities.available)
        self.assertEqual(capabilities.backend, gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_COMPUTE)

    def test_preview_texture_providers_describe_cpu_and_gpu_sources(self):
        volume = gpu_canvas.np.zeros((2, 3, 4), dtype=gpu_canvas.np.uint16)

        cpu_provider = gpu_canvas.cpu_volume_preview_provider(volume, source_shape=(4, 6, 8), spacing_zyx=(1.0, 2.0, 3.0), cache_key=("k",))
        gpu_provider = gpu_canvas.gpu_texture_preview_provider(99, (2, 3, 4), "uint16", source_shape=(4, 6, 8), cache_key=("g",))

        self.assertTrue(cpu_provider.requires_upload)
        self.assertFalse(cpu_provider.is_gpu_texture)
        self.assertEqual(cpu_provider.to_stats()["estimated_bytes"], int(volume.nbytes))
        self.assertTrue(gpu_provider.is_gpu_texture)
        self.assertFalse(gpu_provider.requires_upload)
        self.assertEqual(gpu_provider.to_stats()["estimated_bytes"], 2 * 3 * 4 * 2)

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
        self.assertEqual(core.render_stats()["preview_provider"]["kind"], "gpu_texture")
        self.assertEqual(core.render_stats()["preview_provider"]["build_backend"], "gpu_cache")

    def test_gpu_render_core_cpu_volume_provider_is_recorded_without_changing_upload_path(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        volume = gpu_canvas.np.zeros((2, 3, 4), dtype=gpu_canvas.np.uint8)

        self.assertTrue(core._store_volume_data(volume, source_shape=(4, 6, 8), spacing_zyx=(1.0, 1.0, 2.0), cache_key=("owner", "volume")))

        stats = core.render_stats()["preview_provider"]
        self.assertEqual(stats["kind"], "cpu_array")
        self.assertEqual(stats["build_backend"], "cpu")
        self.assertTrue(stats["requires_upload"])
        self.assertEqual(stats["shape_zyx"], (2, 3, 4))

    def test_gpu_render_core_stream_build_uploads_slabs_without_retaining_cpu_volume(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_FRAGMENT,
            max_3d_texture_size=4096,
        )
        volume = gpu_canvas.np.arange(4 * 6 * 8, dtype=gpu_canvas.np.uint16).reshape((4, 6, 8))
        uploads = []

        with patch.object(gpu_canvas.GL, "glGenTextures", return_value=101), \
            patch.object(gpu_canvas.GL, "glBindTexture"), \
            patch.object(gpu_canvas.GL, "glTexParameteri"), \
            patch.object(gpu_canvas.GL, "glPixelStorei"), \
            patch.object(gpu_canvas.GL, "glTexImage3D") as tex_image, \
            patch.object(gpu_canvas.GL, "glTexSubImage3D", side_effect=lambda *args: uploads.append(args)), \
            patch.object(gpu_canvas.GL, "glDeleteTextures"):
            provider = core._stream_upload_source_volume_texture(
                volume,
                4,
                algorithm="hybrid",
                preserve_source=False,
                cache_key=("owner", "stream"),
                source_shape=volume.shape,
                staging_budget_bytes=16,
            )

        self.assertTrue(provider.is_gpu_texture)
        self.assertEqual(provider.build_backend, "gpu_stream")
        self.assertIsNone(core._volume_data)
        self.assertEqual(core._texture_id, 101)
        self.assertEqual(core._uploaded_shape, (4, 3, 4))
        self.assertEqual(core._uploaded_dtype, "uint8")
        self.assertGreater(len(uploads), 1)
        tex_image.assert_called_once()
        self.assertEqual(tex_image.call_args.args[2], gpu_canvas.GL.GL_R8)
        self.assertEqual(tex_image.call_args.args[7], gpu_canvas.GL.GL_RED)
        self.assertEqual(uploads[0][8], gpu_canvas.GL.GL_RED)
        stats = core.render_stats()["gpu_stream_build"]
        self.assertEqual(stats["algorithm"], "hybrid")
        self.assertEqual(stats["texture_format"], "r8")
        self.assertFalse(stats["degraded"])

    def test_gpu_render_core_stream_build_yields_between_slabs(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_FRAGMENT,
            max_3d_texture_size=4096,
        )
        volume = gpu_canvas.np.arange(4 * 6 * 8, dtype=gpu_canvas.np.uint16).reshape((4, 6, 8))
        yields = []
        core.set_stream_build_yield_callback(lambda: yields.append("yield"))

        with patch.object(gpu_canvas.GL, "glGenTextures", return_value=111), \
            patch.object(gpu_canvas.GL, "glBindTexture"), \
            patch.object(gpu_canvas.GL, "glTexParameteri"), \
            patch.object(gpu_canvas.GL, "glPixelStorei"), \
            patch.object(gpu_canvas.GL, "glTexImage3D"), \
            patch.object(gpu_canvas.GL, "glTexSubImage3D"), \
            patch.object(gpu_canvas.GL, "glDeleteTextures"):
            core._stream_upload_source_volume_texture(
                volume,
                4,
                algorithm="hybrid",
                preserve_source=False,
                cache_key=("owner", "stream-yield"),
                source_shape=volume.shape,
                staging_budget_bytes=16,
            )

        self.assertGreater(len(yields), 1)

    def test_gpu_render_core_stream_build_degrades_target_shape_to_budget(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._texture_cache_budget_bytes = 64 * 1024
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_FRAGMENT,
            max_3d_texture_size=4096,
        )
        volume = gpu_canvas.np.arange(128 * 128 * 128, dtype=gpu_canvas.np.uint16).reshape((128, 128, 128))

        with patch.object(gpu_canvas.GL, "glGenTextures", return_value=102), \
            patch.object(gpu_canvas.GL, "glBindTexture"), \
            patch.object(gpu_canvas.GL, "glTexParameteri"), \
            patch.object(gpu_canvas.GL, "glPixelStorei"), \
            patch.object(gpu_canvas.GL, "glTexImage3D"), \
            patch.object(gpu_canvas.GL, "glTexSubImage3D"), \
            patch.object(gpu_canvas.GL, "glDeleteTextures"):
            provider = core._stream_upload_source_volume_texture(
                volume,
                128,
                algorithm="stride",
                preserve_source=True,
                cache_key=("owner", "degraded-stream"),
                source_shape=volume.shape,
                staging_budget_bytes=16 * 1024,
            )

        stats = core.render_stats()["gpu_stream_build"]
        self.assertTrue(provider.is_gpu_texture)
        self.assertTrue(stats["degraded"])
        self.assertEqual(stats["degrade_reason"], "texture_budget")
        self.assertLess(stats["actual_max_dim"], 128)
        self.assertLessEqual(stats["bytes"], 64 * 1024)
        self.assertEqual(core._uploaded_dtype, "uint16")

    def test_gpu_render_core_stream_build_reuses_cached_texture(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_FRAGMENT,
            max_3d_texture_size=4096,
        )
        key = (("specimen-a", "full", "", ""), "volume", 1024)
        record_key = core._texture_cache_record_key(key, "volume")
        core._texture_cache[record_key] = {
            "texture_id": 77,
            "kind": "volume",
            "owner": core._texture_cache_owner_from_key(key),
            "shape": (16, 32, 32),
            "dtype": "uint16",
            "bytes": 16 * 32 * 32 * 2,
        }
        core._texture_cache_bytes = 16 * 32 * 32 * 2
        volume = gpu_canvas.np.zeros((16, 32, 32), dtype=gpu_canvas.np.uint16)

        with patch.object(gpu_canvas.GL, "glTexImage3D") as tex_image, \
            patch.object(gpu_canvas.GL, "glTexSubImage3D") as tex_sub_image:
            provider = core._stream_upload_source_volume_texture(
                volume,
                1024,
                algorithm="hybrid",
                preserve_source=True,
                cache_key=key,
                source_shape=volume.shape,
            )

        self.assertTrue(provider.is_gpu_texture)
        self.assertEqual(provider.texture_id, 77)
        self.assertEqual(provider.build_backend, "gpu_cache")
        self.assertEqual(core.render_stats()["texture_cache_hits"], 1)
        self.assertTrue(core.render_stats()["gpu_stream_build"]["cache_hit"])
        tex_image.assert_not_called()
        tex_sub_image.assert_not_called()

    def test_gpu_render_core_compute_build_handles_stride_identity_volume(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_COMPUTE,
            max_3d_texture_size=4096,
            supports_compute_shader=True,
            supports_image_load_store=True,
            supports_r16_texture=True,
        )
        volume = gpu_canvas.np.arange(2 * 3 * 4, dtype=gpu_canvas.np.uint8).reshape((2, 3, 4))
        dispatches = []

        with ExitStack() as stack:
            stack.enter_context(patch.object(gpu_canvas.GL, "glGenTextures", side_effect=[301, 302]))
            stack.enter_context(patch.object(gpu_canvas.GL, "glBindTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glTexParameteri"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glPixelStorei"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glTexImage3D"))
            tex_sub_image = stack.enter_context(patch.object(gpu_canvas.GL, "glTexSubImage3D"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glCreateShader", return_value=11))
            stack.enter_context(patch.object(gpu_canvas.GL, "glShaderSource"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glCompileShader"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glGetShaderiv", return_value=True))
            stack.enter_context(patch.object(gpu_canvas.GL, "glCreateProgram", return_value=12))
            stack.enter_context(patch.object(gpu_canvas.GL, "glAttachShader"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glLinkProgram"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDeleteShader"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glGetProgramiv", return_value=True))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUseProgram"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDeleteProgram"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glGetUniformLocation", return_value=0))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUniform1i"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUniform3i"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUniform2f"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glActiveTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glBindImageTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDispatchCompute", side_effect=lambda *args: dispatches.append(args)))
            stack.enter_context(patch.object(gpu_canvas.GL, "glMemoryBarrier"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDeleteTextures"))
            provider = core._stream_upload_source_volume_texture(
                volume,
                4,
                algorithm="stride",
                preserve_source=False,
                cache_key=("owner", "compute"),
                source_shape=volume.shape,
                staging_budget_bytes=1024,
            )

        self.assertTrue(provider.is_gpu_texture)
        self.assertEqual(provider.build_backend, "gpu_compute")
        self.assertEqual(core._texture_id, 301)
        self.assertEqual(core._uploaded_shape, (2, 3, 4))
        self.assertEqual(core.render_stats()["gpu_stream_build"]["backend"], "gpu_compute")
        self.assertGreaterEqual(len(dispatches), 1)
        tex_sub_image.assert_not_called()

    def test_gpu_render_core_compute_build_handles_stride_downsample_volume(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_COMPUTE,
            max_3d_texture_size=4096,
            supports_compute_shader=True,
            supports_image_load_store=True,
            supports_r16_texture=True,
        )
        volume = gpu_canvas.np.arange(6 * 8 * 10, dtype=gpu_canvas.np.uint8).reshape((6, 8, 10))
        tex_image_calls = []
        uniform3i_calls = []

        with ExitStack() as stack:
            stack.enter_context(patch.object(gpu_canvas.GL, "glGenTextures", side_effect=[311, 312]))
            stack.enter_context(patch.object(gpu_canvas.GL, "glBindTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glTexParameteri"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glPixelStorei"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glTexImage3D", side_effect=lambda *args: tex_image_calls.append(args)))
            tex_sub_image = stack.enter_context(patch.object(gpu_canvas.GL, "glTexSubImage3D"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glCreateShader", return_value=21))
            stack.enter_context(patch.object(gpu_canvas.GL, "glShaderSource"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glCompileShader"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glGetShaderiv", return_value=True))
            stack.enter_context(patch.object(gpu_canvas.GL, "glCreateProgram", return_value=22))
            stack.enter_context(patch.object(gpu_canvas.GL, "glAttachShader"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glLinkProgram"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDeleteShader"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glGetProgramiv", return_value=True))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUseProgram"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDeleteProgram"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glGetUniformLocation", return_value=0))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUniform1i"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUniform3i", side_effect=lambda *args: uniform3i_calls.append(args)))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUniform2f"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glActiveTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glBindImageTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDispatchCompute"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glMemoryBarrier"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDeleteTextures"))
            provider = core._stream_upload_source_volume_texture(
                volume,
                4,
                algorithm="stride",
                preserve_source=False,
                cache_key=("owner", "compute-downsample"),
                source_shape=volume.shape,
                staging_budget_bytes=1024,
            )

        self.assertTrue(provider.is_gpu_texture)
        self.assertEqual(provider.build_backend, "gpu_compute")
        self.assertEqual(core._uploaded_shape, (3, 4, 4))
        self.assertEqual(core.render_stats()["gpu_stream_build"]["factors_zyx"], (2, 2, 3))
        self.assertEqual(tex_image_calls[0][3:6], (4, 4, 3))
        self.assertEqual(tex_image_calls[1][3:6], (10, 8, 3))
        self.assertIn((3, 2, 1), [tuple(call[-3:]) for call in uniform3i_calls])
        tex_sub_image.assert_not_called()

    def test_gpu_render_core_compute_build_handles_hybrid_uint16_downsample_to_r8(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_COMPUTE,
            max_3d_texture_size=4096,
            supports_compute_shader=True,
            supports_image_load_store=True,
            supports_r16_texture=True,
        )
        volume = (gpu_canvas.np.arange(6 * 8 * 10, dtype=gpu_canvas.np.uint16).reshape((6, 8, 10)) * 16)
        tex_image_calls = []
        uniform1i_calls = []
        uniform2f_calls = []

        with ExitStack() as stack:
            stack.enter_context(patch.object(gpu_canvas.GL, "glGenTextures", side_effect=[321, 322]))
            stack.enter_context(patch.object(gpu_canvas.GL, "glBindTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glTexParameteri"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glPixelStorei"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glTexImage3D", side_effect=lambda *args: tex_image_calls.append(args)))
            tex_sub_image = stack.enter_context(patch.object(gpu_canvas.GL, "glTexSubImage3D"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glCreateShader", return_value=31))
            stack.enter_context(patch.object(gpu_canvas.GL, "glShaderSource"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glCompileShader"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glGetShaderiv", return_value=True))
            stack.enter_context(patch.object(gpu_canvas.GL, "glCreateProgram", return_value=32))
            stack.enter_context(patch.object(gpu_canvas.GL, "glAttachShader"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glLinkProgram"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDeleteShader"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glGetProgramiv", return_value=True))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUseProgram"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDeleteProgram"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glGetUniformLocation", return_value=0))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUniform1i", side_effect=lambda *args: uniform1i_calls.append(args)))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUniform3i"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glUniform2f", side_effect=lambda *args: uniform2f_calls.append(args)))
            stack.enter_context(patch.object(gpu_canvas.GL, "glActiveTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glBindImageTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDispatchCompute"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glMemoryBarrier"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDeleteTextures"))
            provider = core._stream_upload_source_volume_texture(
                volume,
                4,
                algorithm="hybrid",
                preserve_source=False,
                cache_key=("owner", "compute-hybrid-uint16"),
                source_shape=volume.shape,
                staging_budget_bytes=2048,
            )

        self.assertTrue(provider.is_gpu_texture)
        self.assertEqual(provider.build_backend, "gpu_compute")
        self.assertEqual(core._uploaded_dtype, "uint8")
        self.assertEqual(core.render_stats()["gpu_stream_build"]["algorithm"], "hybrid")
        self.assertEqual(core.render_stats()["gpu_stream_build"]["source_texture_format"], "r16")
        self.assertEqual(tex_image_calls[0][2], gpu_canvas.GL.GL_R8)
        self.assertEqual(tex_image_calls[1][2], gpu_canvas.GL.GL_R16)
        self.assertIn((0, 3), uniform1i_calls)
        self.assertIn((0, 1), uniform1i_calls)
        self.assertTrue(uniform2f_calls)
        tex_sub_image.assert_not_called()

    def test_gpu_render_core_compute_build_failure_falls_back_to_stream(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_COMPUTE,
            max_3d_texture_size=4096,
            supports_compute_shader=True,
            supports_image_load_store=True,
            supports_r16_texture=True,
        )
        volume = gpu_canvas.np.arange(2 * 3 * 4, dtype=gpu_canvas.np.uint8).reshape((2, 3, 4))
        uploads = []

        with ExitStack() as stack:
            stack.enter_context(patch.object(gpu_canvas.GL, "glGenTextures", side_effect=[401, 402, 403]))
            stack.enter_context(patch.object(gpu_canvas.GL, "glBindTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glTexParameteri"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glPixelStorei"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glTexImage3D"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glTexSubImage3D", side_effect=lambda *args: uploads.append(args)))
            stack.enter_context(patch.object(gpu_canvas.GL, "glCreateShader", side_effect=RuntimeError("compute compile failed")))
            stack.enter_context(patch.object(gpu_canvas.GL, "glActiveTexture"))
            stack.enter_context(patch.object(gpu_canvas.GL, "glDeleteTextures"))
            provider = core._stream_upload_source_volume_texture(
                volume,
                4,
                algorithm="stride",
                preserve_source=False,
                cache_key=("owner", "compute-fallback"),
                source_shape=volume.shape,
                staging_budget_bytes=1024,
            )

        self.assertTrue(provider.is_gpu_texture)
        self.assertEqual(provider.build_backend, "gpu_stream")
        self.assertEqual(core.render_stats()["gpu_stream_build"]["backend"], "gpu_stream")
        self.assertGreaterEqual(len(uploads), 1)

    def test_gpu_render_core_stream_build_uploads_mask_without_retaining_cpu_preview(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_FRAGMENT,
            max_3d_texture_size=4096,
        )
        mask = gpu_canvas.np.zeros((4, 6, 8), dtype=gpu_canvas.np.uint16)
        mask[:, 2:5, 3:7] = 3
        uploads = []

        with patch.object(gpu_canvas.GL, "glGenTextures", return_value=201), \
            patch.object(gpu_canvas.GL, "glActiveTexture"), \
            patch.object(gpu_canvas.GL, "glBindTexture"), \
            patch.object(gpu_canvas.GL, "glTexParameteri"), \
            patch.object(gpu_canvas.GL, "glPixelStorei"), \
            patch.object(gpu_canvas.GL, "glTexImage3D") as tex_image, \
            patch.object(gpu_canvas.GL, "glTexSubImage3D", side_effect=lambda *args: uploads.append(args)), \
            patch.object(gpu_canvas.GL, "glDeleteTextures"):
            self.assertTrue(
                core._stream_upload_source_mask_texture(
                    mask,
                    4,
                    algorithm="occupancy",
                    cache_key=("owner", "mask-stream"),
                    source_shape=mask.shape,
                    staging_budget_bytes=8,
                )
            )

        self.assertIsNone(core._mask_data)
        self.assertEqual(core._mask_texture_id, 201)
        self.assertEqual(core._mask_shape, (4, 3, 4))
        self.assertGreater(len(uploads), 1)
        tex_image.assert_called_once()
        self.assertEqual(tex_image.call_args.args[2], gpu_canvas.GL.GL_R8)
        self.assertEqual(uploads[0][8], gpu_canvas.GL.GL_RED)
        stats = core.render_stats()["gpu_stream_build"]["mask"]
        self.assertEqual(stats["backend"], "gpu_stream")
        self.assertEqual(stats["algorithm"], "occupancy")
        self.assertEqual(stats["texture_format"], "r8")

    def test_gpu_render_core_stream_build_reuses_cached_mask_texture(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_FRAGMENT,
            max_3d_texture_size=4096,
        )
        key = (("specimen-a", "part", "head", ""), "mask", 1024)
        record_key = core._texture_cache_record_key(key, "mask")
        core._texture_cache[record_key] = {
            "texture_id": 88,
            "kind": "mask",
            "owner": core._texture_cache_owner_from_key(key),
            "shape": (16, 32, 32),
            "dtype": "uint8",
            "bytes": 16 * 32 * 32,
        }
        core._texture_cache_bytes = 16 * 32 * 32
        mask = gpu_canvas.np.zeros((16, 32, 32), dtype=gpu_canvas.np.uint8)

        with patch.object(gpu_canvas.GL, "glTexImage3D") as tex_image, \
            patch.object(gpu_canvas.GL, "glTexSubImage3D") as tex_sub_image:
            self.assertTrue(
                core._stream_upload_source_mask_texture(
                    mask,
                    1024,
                    algorithm="occupancy",
                    cache_key=key,
                    source_shape=mask.shape,
                )
            )

        self.assertEqual(core._mask_texture_id, 88)
        self.assertEqual(core._mask_shape, (16, 32, 32))
        self.assertIsNone(core._mask_data)
        self.assertEqual(core.render_stats()["texture_cache_hits"], 1)
        self.assertTrue(core.render_stats()["gpu_stream_build"]["mask"]["cache_hit"])
        tex_image.assert_not_called()
        tex_sub_image.assert_not_called()

    def test_gpu_render_core_stream_build_effective_budget_accounts_for_active_texture(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._texture_cache_budget_bytes = 1024 * 1024 * 1024
        key = (("active", "full", "", ""), "old")
        record_key = core._texture_cache_record_key(key, "volume")
        core._texture_cache[record_key] = {
            "texture_id": 88,
            "kind": "volume",
            "owner": core._texture_cache_owner_from_key(key),
            "shape": (1, 1, 1),
            "dtype": "uint8",
            "bytes": 384 * 1024 * 1024,
        }
        core._texture_cache_bytes = 384 * 1024 * 1024
        core._texture_id = 88
        core._volume_cache_key = key

        self.assertEqual(
            core._stream_build_texture_budget_bytes(cache_key=(("active", "full", "", ""), "new")),
            640 * 1024 * 1024,
        )
        self.assertEqual(core._stream_build_texture_budget_bytes(cache_key=key), 1024 * 1024 * 1024)

    def test_gpu_render_core_stream_build_can_release_active_texture_to_avoid_budget_spike(self):
        core = gpu_canvas._GpuVolumeRenderCore()
        core._init_render_state()
        core._texture_cache_budget_bytes = 128 * 1024
        core._preview_build_capabilities = gpu_canvas.GpuPreviewBuildCapabilities(
            available=True,
            backend=gpu_canvas.GPU_PREVIEW_BUILD_BACKEND_FRAGMENT,
            max_3d_texture_size=4096,
        )
        old_key = (("owner", "full", "", ""), "old")
        core._texture_cache[core._texture_cache_record_key(old_key, "volume")] = {
            "texture_id": 55,
            "kind": "volume",
            "owner": core._texture_cache_owner_from_key(old_key),
            "shape": (32, 32, 32),
            "dtype": "uint8",
            "bytes": 120 * 1024,
        }
        core._texture_cache_bytes = 120 * 1024
        core._texture_id = 55
        core._volume_cache_key = old_key
        volume = gpu_canvas.np.ones((32, 32, 32), dtype=gpu_canvas.np.uint8)
        deleted = []

        with patch.object(gpu_canvas.GL, "glGenTextures", return_value=103), \
            patch.object(gpu_canvas.GL, "glBindTexture"), \
            patch.object(gpu_canvas.GL, "glTexParameteri"), \
            patch.object(gpu_canvas.GL, "glPixelStorei"), \
            patch.object(gpu_canvas.GL, "glTexImage3D"), \
            patch.object(gpu_canvas.GL, "glTexSubImage3D"), \
            patch.object(gpu_canvas.GL, "glDeleteTextures", side_effect=lambda ids: deleted.extend(int(value) for value in ids)):
            core._stream_upload_source_volume_texture(
                volume,
                32,
                algorithm="stride",
                preserve_source=False,
                cache_key=(("owner", "full", "", ""), "new"),
                source_shape=volume.shape,
                staging_budget_bytes=16 * 1024,
            )

        self.assertIn(55, deleted)
        self.assertEqual(core._texture_id, 103)
        self.assertTrue(core.render_stats()["gpu_stream_build"]["released_active_for_budget"])

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
