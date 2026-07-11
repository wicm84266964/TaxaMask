import ast
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QObject, QTimer
    from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QPushButton, QSlider
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.ui.tif_preview_controller import TifPreviewController
    from AntSleap.ui.tif_volume_render_controller import TifVolumeRenderController
    from AntSleap.ui.tif_workbench_workers import TifVolumePreviewBuildWorker
    from AntSleap.ui.tif_workbench_signal_router import TifWorkbenchSignalRouter
    from AntSleap.ui.tif_workbench_view import TifWorkbenchView


class FakeWorkbench(QObject):
    pass


@unittest.skipUnless(QApplication is not None, "PySide6 is required for volume render controller tests")
class TifVolumeRenderControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_workbench(self, with_controls=False):
        workbench = FakeWorkbench()
        workbench.lang = "en"
        workbench.display_mode = "volume"
        workbench.signal_router = TifWorkbenchSignalRouter()
        workbench.workbench_view = TifWorkbenchView(workbench)
        workbench.training_status_label = QLabel()
        workbench.log = Mock()
        workbench._cancel_tif_task = Mock()
        workbench._fail_tif_task = Mock()
        workbench._task_context_matches_current = Mock(return_value=True)
        workbench._set_scope_controls_enabled = Mock()
        workbench.preview_controller = TifPreviewController(workbench)
        if with_controls:
            combo_names = {
                "volume_projection_combo",
                "volume_roi_source_combo",
                "volume_roi_budget_combo",
                "volume_tint_combo",
                "volume_shader_quality_combo",
                "volume_mask_combo",
            }
            check_names = {
                "volume_clarity_check",
                "volume_roi_detail_check",
                "volume_roi_inspect_check",
                "volume_surface_refine_check",
                "volume_clip_plane_check",
                "volume_local_axes_check",
            }
            button_names = {
                "btn_volume_custom_color",
                "btn_reset_volume_view",
                "btn_volume_morphology_preset",
            }
            names = (
                "volume_cutoff_slider", "volume_projection_combo", "volume_quality_slider",
                "volume_sample_slider", "volume_clarity_check", "volume_roi_detail_check",
                "volume_roi_source_combo", "volume_roi_inspect_check", "volume_roi_scale_slider",
                "volume_roi_budget_combo", "volume_inside_slider", "volume_clip_slider",
                "volume_tint_combo", "btn_volume_custom_color", "volume_transfer_opacity_slider",
                "volume_enhancement_slider", "volume_tone_slider", "volume_shader_quality_combo",
                "volume_surface_refine_check", "volume_clip_plane_check", "volume_local_axes_check",
                "volume_mask_combo", "volume_mask_opacity_slider", "btn_reset_volume_view",
                "btn_volume_morphology_preset", "volume_clip_plane_depth_slider",
            )
            for name in names:
                if name in combo_names:
                    widget = QComboBox()
                elif name in check_names:
                    widget = QCheckBox()
                elif name in button_names:
                    widget = QPushButton()
                else:
                    widget = QSlider()
                setattr(workbench, name, widget)
            workbench.volume_still_timer = QTimer()
        return workbench

    def test_bind_signals_is_idempotent_and_registers_complete_volume_scope(self):
        workbench = self.make_workbench(with_controls=True)
        controller = TifVolumeRenderController(workbench)

        controller.bind_signals()
        controller.bind_signals()

        self.assertEqual(workbench.signal_router.connection_count("volume_render"), 38)

    def test_preview_build_running_tracks_thread_lifecycle_reference(self):
        controller = TifVolumeRenderController(self.make_workbench())

        self.assertFalse(controller.preview_build_running())
        controller.preview_build_thread = object()
        self.assertTrue(controller.preview_build_running())
        controller.preview_build_thread = None
        self.assertFalse(controller.preview_build_running())

    def test_stale_background_result_is_cancelled_without_cache_write(self):
        workbench = self.make_workbench()
        workbench._task_context_matches_current.return_value = False
        controller = TifVolumeRenderController(workbench)
        controller.state.volume_preview_pending_token = 7
        controller.state.volume_preview_build_task_id = "task-7"
        controller._set_volume_preview_build_controls_busy = Mock()
        controller._cache_volume_preview_result = Mock()

        controller._on_volume_preview_build_finished({"token": 7, "preview": object()})

        workbench._cancel_tif_task.assert_called_once_with("task-7", "stale_volume_preview_context")
        controller._cache_volume_preview_result.assert_not_called()
        self.assertEqual(controller.state.volume_preview_pending_token, 0)
        self.assertEqual(controller.state.volume_preview_build_task_id, "")

    def test_stale_background_failure_does_not_replace_current_status(self):
        workbench = self.make_workbench()
        workbench._task_context_matches_current.return_value = False
        controller = TifVolumeRenderController(workbench)
        controller.state.volume_preview_pending_token = 8
        controller.state.volume_preview_build_task_id = "task-8"
        controller._set_volume_preview_build_controls_busy = Mock()
        controller._update_volume_render_status_label = Mock()

        controller._on_volume_preview_build_failed({"token": 8, "error": "old preview failed"})

        workbench._cancel_tif_task.assert_called_once_with("task-8", "stale_volume_preview_context")
        workbench._fail_tif_task.assert_not_called()
        controller._update_volume_render_status_label.assert_not_called()
        self.assertEqual(controller.state.volume_preview_pending_token, 0)
        self.assertEqual(controller.state.volume_preview_build_task_id, "")

    def test_selection_loading_coalesces_volume_renders_until_complete(self):
        workbench = self.make_workbench()
        workbench._loading_specimen = True
        workbench.display_mode = "volume"
        controller = TifVolumeRenderController(workbench)

        controller.render_volume_preview()
        controller.render_volume_preview()
        controller.render_volume_preview()

        self.assertTrue(controller.state.selection_render_pending)
        workbench._loading_specimen = False
        callbacks = []
        with patch("AntSleap.ui.tif_volume_render_controller.QTimer.singleShot", side_effect=lambda _delay, callback: callbacks.append(callback)):
            self.assertTrue(controller.flush_selection_render())
            self.assertFalse(controller.flush_selection_render())

        self.assertEqual(callbacks, [controller.render_volume_preview])
        self.assertFalse(controller.state.selection_render_pending)

    def test_gpu_failure_switches_to_cpu_and_schedules_repaint(self):
        workbench = self.make_workbench()
        controller = TifVolumeRenderController(workbench)
        controller.state.volume_canvas_renderer = "gpu"
        controller._switch_volume_canvas_to_cpu = Mock(side_effect=lambda warning: setattr(controller.state, "volume_canvas_renderer", "cpu"))
        controller._update_volume_render_status_label = Mock()
        controller.schedule_volume_preview_render = Mock()

        controller._on_gpu_volume_failed("OpenGL texture allocation failed")

        controller._switch_volume_canvas_to_cpu.assert_called_once_with("OpenGL texture allocation failed")
        self.assertEqual(controller.state.volume_canvas_renderer, "cpu")
        controller.schedule_volume_preview_render.assert_called_once_with()
        self.assertIn("CPU fallback", workbench.training_status_label.text())

    def test_commit_memory_failure_is_not_reported_as_gpu_or_data_corruption(self):
        workbench = self.make_workbench()
        controller = TifVolumeRenderController(workbench)
        controller.state.volume_preview_pending_token = 4
        controller.state.volume_preview_build_task_id = "task-4"
        controller._set_volume_preview_build_controls_busy = Mock()
        controller._update_volume_render_status_label = Mock()

        controller._on_volume_preview_build_failed({"token": 4, "error": "paging file is too small"})

        message = controller._update_volume_render_status_label.call_args.args[0]
        self.assertIn("page file", message.lower())
        self.assertNotIn("GPU renderer failed", message)
        self.assertNotIn("corrupt", message.lower())
        self.assertEqual(workbench.preview_controller.last_resource_issue.kind, "commit_memory")

    def test_cancel_wait_releases_running_preview_worker(self):
        workbench = self.make_workbench()
        controller = TifVolumeRenderController(workbench)
        worker = Mock()
        thread = Mock()
        thread.isRunning.return_value = True
        thread.wait.return_value = True
        controller.preview_build_worker = worker
        controller.preview_build_thread = thread
        controller._set_volume_preview_build_controls_busy = Mock()
        controller.state.volume_preview_build_task_id = "task-cancel"

        self.assertTrue(controller._cancel_and_wait_volume_preview_build(timeout_ms=250))

        worker.cancel.assert_called_once_with()
        thread.quit.assert_called_once_with()
        thread.wait.assert_called_once_with(250)
        workbench._cancel_tif_task.assert_called_once_with("task-cancel", "volume_preview_cancelled")

    def test_preview_worker_reports_mid_build_cancellation_as_cancelled(self):
        worker = TifVolumePreviewBuildWorker(
            7,
            volume=object(),
            volume_request={"max_dim": 128, "algorithm": "hybrid"},
        )
        finished = []
        failed = []
        worker.finished.connect(finished.append)
        worker.failed.connect(failed.append)

        def cancel_during_build(*_args, yield_callback=None, **_kwargs):
            worker.cancel()
            yield_callback()

        with patch("AntSleap.ui.tif_workbench_workers.build_volume_preview", side_effect=cancel_during_build):
            worker.run()

        self.assertEqual(len(finished), 1)
        self.assertTrue(finished[0]["cancelled"])
        self.assertEqual(failed, [])

    def test_shell_does_not_initialize_volume_state_copies(self):
        root = Path(__file__).resolve().parents[1]
        shell_source = (root / "AntSleap" / "ui" / "tif_workbench_shell.py").read_text(encoding="utf-8")
        widget_source = (root / "AntSleap" / "ui" / "tif_workbench.py").read_text(encoding="utf-8")

        self.assertNotIn('"_volume_preview_cache":', shell_source)
        self.assertNotIn('"_volume_render_mode":', shell_source)
        self.assertIn('_volume_render_state_property("volume_preview_cache")', widget_source)
        self.assertIn('_volume_render_state_property("volume_interaction_render_interval_ms")', widget_source)

    def test_controller_size_and_cross_workflow_state_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        source_path = root / "AntSleap" / "ui" / "tif_volume_render_controller.py"
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        controller_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TifVolumeRenderController")
        names = [node.name for node in controller_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

        self.assertLess(len(source.splitlines()), 3000)
        self.assertEqual(len(names), len(set(names)))
        for forbidden in (
            "annotation_workflow_controller.state",
            "roi_workflow_controller.state",
            "part_mask_workflow_controller.state",
            "local_axis_controller.state",
            "selection_workflow_controller.state",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
