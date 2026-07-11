import unittest
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch


from AntSleap.ui.tif_project_lifecycle_controller import TifProjectLifecycleController


class TifProjectLifecycleControllerTests(unittest.TestCase):
    def test_deferred_array_release_waits_for_captured_preview_thread(self):
        preview_waiting = threading.Event()
        allow_preview_finish = threading.Event()
        array_closed = threading.Event()

        class PreviewThread:
            def isRunning(self):
                return True

            def wait(self):
                preview_waiting.set()
                allow_preview_finish.wait(2.0)

        array = SimpleNamespace(_mmap=SimpleNamespace(close=array_closed.set))
        controller = TifProjectLifecycleController(SimpleNamespace())

        with patch("AntSleap.ui.tif_project_lifecycle_controller.gc.collect") as collect:
            release_thread = controller.release_volume_arrays(
                [array],
                preview_thread=PreviewThread(),
                defer=True,
            )
            self.assertTrue(preview_waiting.wait(2.0))
            self.assertTrue(controller.array_release_running())
            self.assertFalse(array_closed.is_set())
            allow_preview_finish.set()
            release_thread.join(2.0)

        self.assertTrue(array_closed.is_set())
        collect.assert_not_called()
        self.assertFalse(controller.array_release_running())
        self.assertTrue(controller.wait_for_volume_array_releases())

    def test_background_write_running_covers_research_write_tasks(self):
        workbench = SimpleNamespace(
            _tif_import_thread=None,
            _local_axis_reslice_export_thread=None,
            _part_mask_preview_thread=None,
            roi_workflow_controller=SimpleNamespace(is_confirm_running=Mock(return_value=True)),
            part_mask_workflow_controller=SimpleNamespace(materialize_thread=None, cancel_and_wait_preview=Mock()),
            _tif_backend_thread=None,
            _label_auto_save_thread=None,
            _label_manual_save_thread=None,
            _promote_thread=None,
        )

        self.assertTrue(TifProjectLifecycleController(workbench).background_write_running())

    def test_close_project_stops_before_cleanup_when_unsaved_prompt_cancels(self):
        workbench = SimpleNamespace(
            _tif_import_thread=None,
            _local_axis_reslice_export_thread=None,
            _part_mask_preview_thread=None,
            roi_workflow_controller=SimpleNamespace(is_confirm_running=Mock(return_value=False)),
            part_mask_workflow_controller=SimpleNamespace(materialize_thread=None, cancel_and_wait_preview=Mock()),
            _tif_backend_thread=None,
            _label_auto_save_thread=None,
            _label_manual_save_thread=None,
            _promote_thread=None,
            volume_render_controller=SimpleNamespace(_cancel_and_wait_volume_preview_build=Mock(return_value=True)),
            annotation_workflow_controller=SimpleNamespace(wait_for_auto_save=Mock()),
        )
        workbench.annotation_workflow_controller.confirm_discard_or_save = Mock(return_value=False)
        controller = TifProjectLifecycleController(workbench)
        controller._clear_loaded_project_state = Mock()

        self.assertFalse(controller.close_project(prompt_unsaved=True))
        controller._clear_loaded_project_state.assert_not_called()


    def test_close_project_cancels_preview_workflows_before_unsaved_prompt(self):
        calls = []
        volume = SimpleNamespace(_cancel_and_wait_volume_preview_build=Mock(side_effect=lambda: calls.append("volume") or True))
        part_mask = SimpleNamespace(
            materialize_thread=None,
            cancel_and_wait_preview=Mock(side_effect=lambda: calls.append("part_mask") or True),
        )
        annotation = SimpleNamespace(
            wait_for_auto_save=Mock(side_effect=lambda: calls.append("auto_save")),
            confirm_discard_or_save=Mock(side_effect=lambda: calls.append("prompt") or False),
        )
        workbench = SimpleNamespace(
            _tif_import_thread=None,
            _local_axis_reslice_export_thread=None,
            roi_workflow_controller=SimpleNamespace(is_confirm_running=Mock(return_value=False)),
            part_mask_workflow_controller=part_mask,
            volume_render_controller=volume,
            annotation_workflow_controller=annotation,
            _tif_backend_thread=None,
            _label_auto_save_thread=None,
            _label_manual_save_thread=None,
            _promote_thread=None,
        )
        controller = TifProjectLifecycleController(workbench)
        controller._clear_loaded_project_state = Mock()

        self.assertFalse(controller.close_project(prompt_unsaved=True))
        self.assertEqual(calls, ["volume", "part_mask", "auto_save", "prompt"])
        controller._clear_loaded_project_state.assert_not_called()

    def test_close_project_does_not_release_data_while_preview_thread_is_running(self):
        workbench = SimpleNamespace(
            _tif_import_thread=None,
            _local_axis_reslice_export_thread=None,
            roi_workflow_controller=SimpleNamespace(is_confirm_running=Mock(return_value=False)),
            part_mask_workflow_controller=SimpleNamespace(materialize_thread=None, cancel_and_wait_preview=Mock()),
            volume_render_controller=SimpleNamespace(_cancel_and_wait_volume_preview_build=Mock(return_value=False)),
            annotation_workflow_controller=SimpleNamespace(wait_for_auto_save=Mock()),
            _tif_backend_thread=None,
            _label_auto_save_thread=None,
            _label_manual_save_thread=None,
            _promote_thread=None,
        )
        controller = TifProjectLifecycleController(workbench)
        controller._clear_loaded_project_state = Mock()

        self.assertFalse(controller.close_project(prompt_unsaved=False))
        controller._clear_loaded_project_state.assert_not_called()

    def test_close_project_does_not_cleanup_while_part_mask_preview_is_running(self):
        workbench = SimpleNamespace(
            _tif_import_thread=None,
            _local_axis_reslice_export_thread=None,
            roi_workflow_controller=SimpleNamespace(is_confirm_running=Mock(return_value=False)),
            part_mask_workflow_controller=SimpleNamespace(
                materialize_thread=None,
                cancel_and_wait_preview=Mock(return_value=False),
            ),
            volume_render_controller=SimpleNamespace(_cancel_and_wait_volume_preview_build=Mock(return_value=True)),
            annotation_workflow_controller=SimpleNamespace(wait_for_auto_save=Mock()),
            _tif_backend_thread=None,
            _label_auto_save_thread=None,
            _label_manual_save_thread=None,
            _promote_thread=None,
        )
        controller = TifProjectLifecycleController(workbench)
        controller._clear_loaded_project_state = Mock()

        self.assertFalse(controller.close_project(prompt_unsaved=False))
        controller._clear_loaded_project_state.assert_not_called()

    def test_close_project_waits_for_deferred_volume_releases(self):
        workbench = SimpleNamespace(
            _tif_import_thread=None,
            _local_axis_reslice_export_thread=None,
            roi_workflow_controller=SimpleNamespace(is_confirm_running=Mock(return_value=False)),
            part_mask_workflow_controller=SimpleNamespace(
                materialize_thread=None,
                cancel_and_wait_preview=Mock(return_value=True),
            ),
            volume_render_controller=SimpleNamespace(_cancel_and_wait_volume_preview_build=Mock(return_value=True)),
            annotation_workflow_controller=SimpleNamespace(wait_for_auto_save=Mock()),
            _tif_backend_thread=None,
            _label_auto_save_thread=None,
            _label_manual_save_thread=None,
            _promote_thread=None,
        )
        controller = TifProjectLifecycleController(workbench)
        controller.wait_for_volume_array_releases = Mock(return_value=False)
        controller._clear_loaded_project_state = Mock()

        self.assertFalse(controller.close_project(prompt_unsaved=False))
        controller._clear_loaded_project_state.assert_not_called()

if __name__ == "__main__":
    unittest.main()
