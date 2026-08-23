import copy
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class FakeTimer:
    def __init__(self):
        self.active = False
        self.delay = 0

    def start(self, delay):
        self.active = True
        self.delay = delay

    def stop(self):
        self.active = False

    def isActive(self):
        return self.active


class FakeProject:
    def __init__(self, path):
        self.current_project_path = path
        self.project_data = {"images": [], "labels": {}}
        self.save_count = 0
        self.load_calls = []
        self.save_error = None

    def save_project(self, force=False):
        self.save_count += 1
        if self.save_error is not None:
            raise self.save_error

    def load_project(self, path):
        self.load_calls.append(str(path))
        self.current_project_path = str(path)
        self.project_data = {"images": [f"{path}.png"], "labels": {}}

    def _snapshot_runtime_state(self, deep=False):
        state = {
            "current_project_path": self.current_project_path,
            "project_data": self.project_data,
        }
        return copy.deepcopy(state) if deep else state

    def _restore_runtime_state(self, state):
        self.current_project_path = state["current_project_path"]
        self.project_data = state["project_data"]


class FakeTifProject:
    def __init__(self, path):
        self.current_project_path = path
        self.project_data = {"specimens": []}
        self.load_calls = []

    def create_project(self, _name, project_dir):
        self.current_project_path = str(Path(project_dir) / "project.tif_sqlite_manifest.json")
        return self.current_project_path

    def load_project(self, path):
        self.load_calls.append(str(path))
        self.current_project_path = str(path)
        self.project_data = {"specimens": [{"id": str(path)}]}
        return self.current_project_path

    def _snapshot_runtime_state(self):
        return {
            "current_project_path": self.current_project_path,
            "project_data": copy.deepcopy(self.project_data),
        }

    def _restore_runtime_state(self, state):
        self.current_project_path = state["current_project_path"]
        self.project_data = state["project_data"]


class FakeStlProject:
    def __init__(self, path):
        self.current_project_path = path
        self.project_data = {"specimens": [{"id": "old-stl"}]}
        self.load_calls = []

    def load_project(self, path):
        self.load_calls.append(str(path))
        self.current_project_path = str(path)
        self.project_data = {"specimens": [{"id": "target-stl"}]}

    def _snapshot_runtime_state(self):
        return {
            "current_project_path": self.current_project_path,
            "project_data": copy.deepcopy(self.project_data),
        }

    def _restore_runtime_state(self, state):
        self.current_project_path = state["current_project_path"]
        self.project_data = state["project_data"]


class FakeTabs:
    def __init__(self, current):
        self.current = current
        self.set_calls = []

    def currentWidget(self):
        return self.current

    def setCurrentWidget(self, widget):
        self.current = widget
        self.set_calls.append(widget)


class FakeCanvas:
    def __init__(self):
        self.load_calls = []
        self.load_error = None

    def load_image(self, path):
        self.load_calls.append(path)
        if self.load_error is not None:
            error = self.load_error
            self.load_error = None
            raise error


class FakeRollbackToken:
    def __init__(self):
        self.rollback_count = 0
        self.finalize_count = 0
        self.active = True

    def rollback(self):
        self.rollback_count += 1
        self.active = False

    def finalize(self):
        self.finalize_count += 1
        self.active = False


class FakeRunningThread:
    def isRunning(self):
        return True


class FakeCloseEvent:
    def __init__(self):
        self.ignored = False
        self.accepted = False

    def ignore(self):
        self.ignored = True

    def accept(self):
        self.accepted = True


class MainWindowStage4ProjectLifecycleTests(unittest.TestCase):
    def _make_open_switch_owner(self, source_kind="image", configured_last_project_path=None):
        from AntSleap.core.path_identity import canonical_path
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        owner = type("LifecycleOwner", (MainWindowProjectLifecycleMixin,), {})()
        old_image_path = canonical_path("old-project.json")
        old_tif_path = canonical_path("old.tif_sqlite_manifest.json")
        old_stl_path = canonical_path("old-stl.json")
        if source_kind == "tif":
            owner.active_project_kind = "tif"
            owner.last_workbench_kind = "tif"
            owner.active_project_source_kind = "tif"
            owner.active_project_entry_path = old_tif_path
        elif source_kind == "stl":
            owner.active_project_kind = "image"
            owner.last_workbench_kind = "image"
            owner.active_project_source_kind = "stl"
            owner.active_project_entry_path = old_stl_path
        elif source_kind == "start":
            owner.active_project_kind = "start"
            owner.last_workbench_kind = "image"
            owner.active_project_source_kind = "image"
            owner.active_project_entry_path = old_image_path
        else:
            owner.active_project_kind = "image"
            owner.last_workbench_kind = "image"
            owner.active_project_source_kind = "image"
            owner.active_project_entry_path = old_image_path

        owner.current_lang = "en"
        owner.project = FakeProject(old_image_path)
        owner.tif_project = FakeTifProject(old_tif_path)
        owner.stl_project = FakeStlProject(old_stl_path)
        owner.tif_workbench = SimpleNamespace(
            close_project=Mock(return_value=True),
            refresh_project=Mock(),
        )
        owner.current_image = canonical_path("old-image.png")
        owner._image_list_state_cache = {"marker": "old-cache"}
        owner.image_list_group_collapsed = {"original": True, "split": False}
        owner.old_tab = object()
        owner.target_tab = object()
        owner.tabs = FakeTabs(owner.old_tab)
        owner.canvas = FakeCanvas()

        config_state = {
            "last_project_path": (
                owner.active_project_entry_path
                if configured_last_project_path is None
                else configured_last_project_path
            )
        }

        def config_get(key, default=None):
            return config_state.get(key, default)

        def config_set(key, value):
            config_state[key] = value

        owner.config = SimpleNamespace(
            get=Mock(side_effect=config_get),
            set=Mock(side_effect=config_set),
        )
        owner.config_state = config_state
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._flush_pending_project_save = Mock()
        owner._is_project_sqlite_database_file = Mock(return_value=False)
        owner._read_project_probe_payload = Mock(return_value={})
        owner._is_legacy_2d_json_project_payload = Mock(return_value=False)
        owner._is_tif_workflow_enabled = Mock(return_value=True)
        owner._is_tif_project_file = Mock(return_value=False)
        owner._is_stl_project_file = Mock(return_value=False)
        owner._prepare_image_list_for_project_open = Mock()
        owner._refresh_project_bound_views = Mock()
        owner._sync_blink_lab_model_profile_defaults = Mock()
        owner._preload_2d_stl_models_after_open = Mock()
        owner.engine = SimpleNamespace()
        owner.log = Mock()
        return owner

    def test_main_window_inherits_project_lifecycle_contract(self):
        import AntSleap.main as main_module
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        self.assertIs(main_module.MainWindow.open_project_path, MainWindowProjectLifecycleMixin.open_project_path)
        self.assertIs(main_module.MainWindow.closeEvent, MainWindowProjectLifecycleMixin.closeEvent)
        self.assertIs(
            main_module.MainWindow._flush_pending_project_save,
            MainWindowProjectLifecycleMixin._flush_pending_project_save,
        )

    def test_stale_save_callback_never_writes_new_project(self):
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        with tempfile.TemporaryDirectory() as temp_dir:
            old_path = str(Path(temp_dir) / "old.sqlite_manifest.json")
            new_path = str(Path(temp_dir) / "new.sqlite_manifest.json")
            owner = type("LifecycleOwner", (MainWindowProjectLifecycleMixin,), {})()
            owner.project = FakeProject(old_path)
            owner.project_save_timer = FakeTimer()
            owner.project_autosave_delay_ms = 100
            owner.project_save_navigation_idle_ms = 100
            owner.project_last_image_switch_at = 0.0
            owner.project_save_pending = False
            owner.project_save_context = {}

            owner._schedule_project_save("annotation_changed")
            owner.project.current_project_path = new_path

            self.assertFalse(owner._flush_pending_project_save(force=True))
            self.assertEqual(owner.project.save_count, 0)
            self.assertFalse(owner.project_save_pending)
            self.assertEqual(owner.project_save_context, {})

    def test_project_lifecycle_module_does_not_import_main_window(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "AntSleap"
            / "ui"
            / "main_window_project_lifecycle.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("AntSleap.main", source)
        self.assertNotIn("from main import", source)

    def test_training_preflight_blocks_window_close_before_process_exit(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        owner = type(
            "LifecycleOwner",
            (
                lifecycle_module.MainWindowProjectLifecycleMixin,
                MainWindowModelManagementMixin,
            ),
            {},
        )()
        owner.current_lang = "en"
        owner.training_preflight_thread = FakeRunningThread()
        event = FakeCloseEvent()

        with patch.object(
            lifecycle_module.QMessageBox, "information"
        ) as information, patch.object(lifecycle_module.os, "_exit") as hard_exit:
            owner.closeEvent(event)

        self.assertTrue(event.ignored)
        self.assertFalse(event.accepted)
        information.assert_called_once()
        hard_exit.assert_not_called()

    def test_window_close_honors_active_tif_unsaved_cancel(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        close_project = Mock(return_value=False)
        owner = type(
            "LifecycleOwner",
            (lifecycle_module.MainWindowProjectLifecycleMixin, MainWindowModelManagementMixin),
            {},
        )()
        owner.current_lang = "en"
        owner.active_project_kind = "tif"
        owner.tif_workbench = SimpleNamespace(close_project=close_project)
        event = FakeCloseEvent()

        with patch.object(lifecycle_module.os, "_exit") as hard_exit:
            owner.closeEvent(event)

        self.assertTrue(event.ignored)
        self.assertFalse(event.accepted)
        close_project.assert_called_once_with(prompt_unsaved=True)
        hard_exit.assert_not_called()

    def test_open_project_does_not_replace_active_tif_when_close_is_cancelled(self):
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        owner = type("LifecycleOwner", (MainWindowProjectLifecycleMixin,), {})()
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._flush_pending_project_save = Mock()
        owner._is_project_sqlite_database_file = Mock(return_value=False)
        owner._read_project_probe_payload = Mock(return_value={})
        owner._is_legacy_2d_json_project_payload = Mock(return_value=False)
        owner._is_tif_project_file = Mock(return_value=False)
        owner._is_stl_project_file = Mock(return_value=False)
        owner._close_active_tif_workbench_for_project_switch = Mock(return_value=False)
        owner.project = SimpleNamespace(load_project=Mock())

        owner.open_project_path(str(Path("new-project.json")))

        owner._close_active_tif_workbench_for_project_switch.assert_called_once_with()
        owner.project.load_project.assert_not_called()

    def test_failed_target_load_restores_closed_active_tif_workbench(self):
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        owner = type("LifecycleOwner", (MainWindowProjectLifecycleMixin,), {})()
        owner.current_lang = "en"
        owner.active_project_kind = "tif"
        owner.last_workbench_kind = "tif"
        owner.active_project_source_kind = "tif"
        owner.active_project_entry_path = "old.tif_sqlite_manifest.json"
        owner.tif_project = SimpleNamespace(current_project_path="old.tif_sqlite_manifest.json")
        owner.tif_workbench = SimpleNamespace(
            close_project=Mock(return_value=True),
            refresh_project=Mock(),
        )
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._flush_pending_project_save = Mock()
        owner._is_project_sqlite_database_file = Mock(return_value=False)
        owner._read_project_probe_payload = Mock(return_value={})
        owner._is_legacy_2d_json_project_payload = Mock(return_value=False)
        owner._is_tif_project_file = Mock(return_value=False)
        owner._is_stl_project_file = Mock(return_value=False)
        owner.project = SimpleNamespace(load_project=Mock(side_effect=RuntimeError("injected load failure")))
        owner._refresh_project_bound_views = Mock(side_effect=owner.tif_workbench.refresh_project)

        with self.assertRaisesRegex(RuntimeError, "injected load failure"):
            owner.open_project_path("new-project.json")

        owner.tif_workbench.close_project.assert_called_once_with(prompt_unsaved=True)
        owner.tif_workbench.refresh_project.assert_called_once_with()
        self.assertEqual(owner.active_project_kind, "tif")
        self.assertEqual(owner.active_project_entry_path, "old.tif_sqlite_manifest.json")

    def test_open_tif_refresh_failure_reloads_previous_tif_project(self):
        from AntSleap.core.path_identity import canonical_path
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        owner = type("LifecycleOwner", (MainWindowProjectLifecycleMixin,), {})()
        old_path = canonical_path("old.tif_sqlite_manifest.json")
        target_path = canonical_path("target.tif_sqlite_manifest.json")
        owner.current_lang = "en"
        owner.active_project_kind = "tif"
        owner.last_workbench_kind = "tif"
        owner.active_project_source_kind = "tif"
        owner.active_project_entry_path = old_path
        owner.tif_project = FakeTifProject(old_path)
        owner.tif_workbench = SimpleNamespace(
            close_project=Mock(return_value=True),
            refresh_project=Mock(),
        )
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._flush_pending_project_save = Mock()
        owner._is_project_sqlite_database_file = Mock(return_value=False)
        owner._read_project_probe_payload = Mock(return_value={})
        owner._is_legacy_2d_json_project_payload = Mock(return_value=False)
        owner._is_tif_project_file = Mock(return_value=True)
        owner._is_tif_workflow_enabled = Mock(return_value=True)
        refresh_attempts = 0

        def refresh_project_bound_views():
            nonlocal refresh_attempts
            refresh_attempts += 1
            if refresh_attempts == 1:
                raise RuntimeError("injected refresh failure")
            owner.tif_workbench.refresh_project()

        owner._refresh_project_bound_views = Mock(side_effect=refresh_project_bound_views)
        owner.config = SimpleNamespace(get=Mock(return_value=old_path), set=Mock())
        owner.log = Mock()

        with self.assertRaisesRegex(RuntimeError, "injected refresh failure"):
            owner.open_project_path(target_path)

        self.assertEqual(owner.tif_project.load_calls, [target_path])
        self.assertEqual(owner.tif_project.current_project_path, old_path)
        self.assertEqual(owner.active_project_kind, "tif")
        self.assertEqual(owner.active_project_entry_path, old_path)
        owner.config.set.assert_any_call("last_project_path", old_path)
        owner.tif_workbench.refresh_project.assert_called_once_with()
        self.assertEqual(owner._refresh_project_bound_views.call_count, 2)

    def test_tif_refresh_failure_restores_preclose_specimen_part_reslice_selection(self):
        from AntSleap.core.path_identity import canonical_path

        owner = self._make_open_switch_owner("tif")
        target_path = canonical_path("target.tif_sqlite_manifest.json")
        workbench = owner.tif_workbench
        old_selection = {
            "current_specimen_id": "source-specimen",
            "current_volume_scope": "part",
            "current_part_id": "source-brain",
            "current_reslice_id": "source-head-axis",
        }
        for name, value in old_selection.items():
            setattr(workbench, name, value)

        def close_project(prompt_unsaved=True):
            self.assertTrue(prompt_unsaved)
            workbench.current_specimen_id = ""
            workbench.current_volume_scope = "full"
            workbench.current_part_id = ""
            workbench.current_reslice_id = ""
            return True

        refresh_attempts = 0

        def refresh_project():
            nonlocal refresh_attempts
            refresh_attempts += 1
            if refresh_attempts == 1:
                workbench.current_specimen_id = "target-specimen"
                workbench.current_volume_scope = "part"
                workbench.current_part_id = "target-head"
                workbench.current_reslice_id = "target-axis"
                raise RuntimeError("injected target TIF selection refresh failure")
            self.assertEqual(
                {name: getattr(workbench, name) for name in old_selection},
                old_selection,
            )

        workbench.close_project.side_effect = close_project
        workbench.refresh_project.side_effect = refresh_project
        owner._is_tif_project_file.return_value = True
        del owner._refresh_project_bound_views
        owner._apply_project_mode_tabs = Mock()
        owner._ensure_tif_workbench = Mock(return_value=workbench)

        with self.assertRaisesRegex(
            RuntimeError,
            "injected target TIF selection refresh failure",
        ):
            owner.open_project_path(target_path)

        self.assertEqual(refresh_attempts, 2)
        self.assertEqual(
            {name: getattr(workbench, name) for name in old_selection},
            old_selection,
        )
        self.assertEqual(
            owner.tif_project.current_project_path,
            canonical_path("old.tif_sqlite_manifest.json"),
        )

    def test_open_tif_config_failure_reloads_previous_tif_project(self):
        from AntSleap.core.path_identity import canonical_path
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        owner = type("LifecycleOwner", (MainWindowProjectLifecycleMixin,), {})()
        old_path = canonical_path("old.tif_sqlite_manifest.json")
        target_path = canonical_path("target.tif_sqlite_manifest.json")
        owner.current_lang = "en"
        owner.active_project_kind = "tif"
        owner.last_workbench_kind = "tif"
        owner.active_project_source_kind = "tif"
        owner.active_project_entry_path = old_path
        owner.tif_project = FakeTifProject(old_path)
        owner.tif_workbench = SimpleNamespace(
            close_project=Mock(return_value=True),
            refresh_project=Mock(),
        )
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._flush_pending_project_save = Mock()
        owner._is_project_sqlite_database_file = Mock(return_value=False)
        owner._read_project_probe_payload = Mock(return_value={})
        owner._is_legacy_2d_json_project_payload = Mock(return_value=False)
        owner._is_tif_project_file = Mock(return_value=True)
        owner._is_tif_workflow_enabled = Mock(return_value=True)
        owner._refresh_project_bound_views = Mock(side_effect=owner.tif_workbench.refresh_project)

        def set_last_project(_key, value):
            if value == target_path:
                raise RuntimeError("injected config failure")

        owner.config = SimpleNamespace(get=Mock(return_value=old_path), set=Mock(side_effect=set_last_project))
        owner.log = Mock()

        with self.assertRaisesRegex(RuntimeError, "injected config failure"):
            owner.open_project_path(target_path)

        self.assertEqual(owner.tif_project.load_calls, [target_path])
        self.assertEqual(owner.tif_project.current_project_path, old_path)
        self.assertEqual(owner.active_project_kind, "tif")
        self.assertEqual(owner.active_project_entry_path, old_path)
        owner.config.set.assert_any_call("last_project_path", old_path)
        owner.tif_workbench.refresh_project.assert_called_once_with()
        owner._refresh_project_bound_views.assert_called_once_with()

    def test_open_tif_log_failure_reloads_previous_tif_project(self):
        from AntSleap.core.path_identity import canonical_path
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        owner = type("LifecycleOwner", (MainWindowProjectLifecycleMixin,), {})()
        old_path = canonical_path("old.tif_sqlite_manifest.json")
        target_path = canonical_path("target.tif_sqlite_manifest.json")
        owner.current_lang = "en"
        owner.active_project_kind = "tif"
        owner.last_workbench_kind = "tif"
        owner.active_project_source_kind = "tif"
        owner.active_project_entry_path = old_path
        owner.tif_project = FakeTifProject(old_path)
        owner.tif_workbench = SimpleNamespace(
            close_project=Mock(return_value=True),
            refresh_project=Mock(),
        )
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._flush_pending_project_save = Mock()
        owner._is_project_sqlite_database_file = Mock(return_value=False)
        owner._read_project_probe_payload = Mock(return_value={})
        owner._is_legacy_2d_json_project_payload = Mock(return_value=False)
        owner._is_tif_project_file = Mock(return_value=True)
        owner._is_tif_workflow_enabled = Mock(return_value=True)
        owner._refresh_project_bound_views = Mock(side_effect=owner.tif_workbench.refresh_project)
        owner.config = SimpleNamespace(get=Mock(return_value=old_path), set=Mock())
        owner.log = Mock(side_effect=RuntimeError("injected log failure"))

        with self.assertRaisesRegex(RuntimeError, "injected log failure"):
            owner.open_project_path(target_path)

        self.assertEqual(owner.tif_project.load_calls, [target_path])
        self.assertEqual(owner.tif_project.current_project_path, old_path)
        self.assertEqual(owner.active_project_kind, "tif")
        self.assertEqual(owner.active_project_entry_path, old_path)
        owner.config.set.assert_any_call("last_project_path", old_path)
        owner.tif_workbench.refresh_project.assert_called_once_with()
        owner._refresh_project_bound_views.assert_called_once_with()

    def test_image_to_tif_config_failure_restores_source_manager_and_ui(self):
        from AntSleap.core.path_identity import canonical_path

        owner = self._make_open_switch_owner("image")
        target_path = canonical_path("target.tif_sqlite_manifest.json")
        old_project_data = owner.project.project_data
        owner._is_tif_project_file.return_value = True

        def config_set(key, value):
            owner.config_state[key] = value
            if value == target_path:
                raise RuntimeError("injected image source config failure")

        owner.config.set.side_effect = config_set

        with self.assertRaisesRegex(RuntimeError, "injected image source config failure"):
            owner.open_project_path(target_path)

        self.assertEqual(owner.active_project_kind, "image")
        self.assertEqual(owner.active_project_source_kind, "image")
        self.assertIs(owner.project.project_data, old_project_data)
        self.assertEqual(owner.tif_project.current_project_path, canonical_path("old.tif_sqlite_manifest.json"))
        self.assertEqual(owner.config_state["last_project_path"], canonical_path("old-project.json"))
        owner._refresh_project_bound_views.assert_called_once_with()
        self.assertEqual(owner.canvas.load_calls, [canonical_path("old-image.png")])
        self.assertIs(owner.tabs.currentWidget(), owner.old_tab)

    def test_image_to_tif_log_failure_restores_source_manager_and_ui(self):
        from AntSleap.core.path_identity import canonical_path

        owner = self._make_open_switch_owner("image")
        target_path = canonical_path("target.tif_sqlite_manifest.json")
        owner._is_tif_project_file.return_value = True
        owner.log.side_effect = RuntimeError("injected image source log failure")

        with self.assertRaisesRegex(RuntimeError, "injected image source log failure"):
            owner.open_project_path(target_path)

        self.assertEqual(owner.active_project_kind, "image")
        self.assertEqual(owner.active_project_entry_path, canonical_path("old-project.json"))
        self.assertEqual(owner.config_state["last_project_path"], canonical_path("old-project.json"))
        self.assertEqual(owner.tif_project.current_project_path, canonical_path("old.tif_sqlite_manifest.json"))
        owner._refresh_project_bound_views.assert_called_once_with()
        self.assertIs(owner.tabs.currentWidget(), owner.old_tab)

    def test_image_to_tif_refresh_failure_restores_empty_config_tab_canvas_and_cache(self):
        from AntSleap.core.path_identity import canonical_path

        owner = self._make_open_switch_owner("image", configured_last_project_path="")
        target_path = canonical_path("target.tif_sqlite_manifest.json")
        old_cache = owner._image_list_state_cache
        old_collapsed = dict(owner.image_list_group_collapsed)
        refresh_attempts = 0
        owner._is_tif_project_file.return_value = True

        def refresh_project_bound_views():
            nonlocal refresh_attempts
            refresh_attempts += 1
            if refresh_attempts == 1:
                owner.tabs.setCurrentWidget(owner.target_tab)
                owner.current_image = canonical_path("target-image.png")
                owner._image_list_state_cache = {"marker": "target-cache"}
                owner.image_list_group_collapsed = {"original": False}
                raise RuntimeError("injected image source refresh failure")
            self.assertEqual(owner.active_project_kind, "image")

        owner._refresh_project_bound_views.side_effect = refresh_project_bound_views

        with self.assertRaisesRegex(RuntimeError, "injected image source refresh failure"):
            owner.open_project_path(target_path)

        self.assertEqual(refresh_attempts, 2)
        self.assertEqual(owner.config_state["last_project_path"], "")
        self.assertEqual(owner.current_image, canonical_path("old-image.png"))
        self.assertIs(owner._image_list_state_cache, old_cache)
        self.assertEqual(owner.image_list_group_collapsed, old_collapsed)
        self.assertEqual(owner.canvas.load_calls, [canonical_path("old-image.png")])
        self.assertIs(owner.tabs.currentWidget(), owner.old_tab)

    def test_real_partial_tif_refresh_restores_source_after_nested_widget_failure(self):
        from AntSleap.core.path_identity import canonical_path

        owner = self._make_open_switch_owner("image")
        target_path = canonical_path("target.tif_sqlite_manifest.json")
        del owner._refresh_project_bound_views
        owner._is_tif_project_file.return_value = True

        def apply_project_mode_tabs():
            if owner.active_project_kind == "tif":
                owner.tabs.setCurrentWidget(owner.target_tab)

        def fail_nested_tif_refresh():
            owner.current_image = canonical_path("partially-refreshed.png")
            owner._image_list_state_cache = {"marker": "partial-cache"}
            raise RuntimeError("injected nested TIF refresh failure")

        owner._apply_project_mode_tabs = Mock(side_effect=apply_project_mode_tabs)
        owner._ensure_tif_workbench = Mock(return_value=owner.tif_workbench)
        owner.tif_workbench.refresh_project.side_effect = fail_nested_tif_refresh
        owner.refresh_file_list = Mock()
        owner.refresh_ui = Mock()
        owner.refresh_route_table = Mock()

        with self.assertRaisesRegex(RuntimeError, "injected nested TIF refresh failure"):
            owner.open_project_path(target_path)

        self.assertEqual(owner._apply_project_mode_tabs.call_count, 2)
        owner.refresh_file_list.assert_called_once_with()
        owner.refresh_ui.assert_called_once_with()
        owner.refresh_route_table.assert_called_once_with()
        self.assertEqual(owner.current_image, canonical_path("old-image.png"))
        self.assertEqual(owner._image_list_state_cache, {"marker": "old-cache"})
        self.assertEqual(owner.canvas.load_calls, [canonical_path("old-image.png")])
        self.assertIs(owner.tabs.currentWidget(), owner.old_tab)

    def test_start_to_tif_log_failure_restores_start_center_state(self):
        from AntSleap.core.path_identity import canonical_path

        owner = self._make_open_switch_owner("start")
        target_path = canonical_path("target.tif_sqlite_manifest.json")
        owner._is_tif_project_file.return_value = True
        owner.log.side_effect = RuntimeError("injected start source log failure")

        with self.assertRaisesRegex(RuntimeError, "injected start source log failure"):
            owner.open_project_path(target_path)

        self.assertEqual(owner.active_project_kind, "start")
        self.assertEqual(owner.last_workbench_kind, "image")
        self.assertEqual(owner.active_project_source_kind, "image")
        self.assertIs(owner.tabs.currentWidget(), owner.old_tab)

    def test_stl_to_tif_log_failure_restores_stl_source_state(self):
        from AntSleap.core.path_identity import canonical_path

        owner = self._make_open_switch_owner("stl")
        target_path = canonical_path("target.tif_sqlite_manifest.json")
        owner._is_tif_project_file.return_value = True
        owner.log.side_effect = RuntimeError("injected stl source log failure")

        with self.assertRaisesRegex(RuntimeError, "injected stl source log failure"):
            owner.open_project_path(target_path)

        self.assertEqual(owner.active_project_kind, "image")
        self.assertEqual(owner.active_project_source_kind, "stl")
        self.assertEqual(owner.active_project_entry_path, canonical_path("old-stl.json"))
        self.assertEqual(owner.stl_project.current_project_path, canonical_path("old-stl.json"))
        self.assertEqual(owner.tif_project.current_project_path, canonical_path("old.tif_sqlite_manifest.json"))

    def test_tif_to_2d_prepare_failure_restores_all_source_state(self):
        from AntSleap.core.path_identity import canonical_path

        owner = self._make_open_switch_owner("tif")
        target_path = canonical_path("target.sqlite_manifest.json")
        old_project_data = owner.project.project_data
        owner._prepare_image_list_for_project_open.side_effect = RuntimeError("injected 2d prepare failure")

        with self.assertRaisesRegex(RuntimeError, "injected 2d prepare failure"):
            owner.open_project_path(target_path)

        self.assertEqual(owner.project.load_calls, [target_path])
        self.assertEqual(owner.project.current_project_path, canonical_path("old-project.json"))
        self.assertIs(owner.project.project_data, old_project_data)
        self.assertEqual(owner.active_project_kind, "tif")
        self.assertEqual(owner.active_project_entry_path, canonical_path("old.tif_sqlite_manifest.json"))
        self.assertEqual(owner.config_state["last_project_path"], canonical_path("old.tif_sqlite_manifest.json"))
        owner.tif_workbench.close_project.assert_called_once_with(prompt_unsaved=True)
        owner._refresh_project_bound_views.assert_called_once_with()

    def test_stl_common_finalize_failure_rolls_back_staged_registration(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        owner = self._make_open_switch_owner("image")
        target_path = lifecycle_module.canonical_path("target-stl.json")
        rollback_token = FakeRollbackToken()
        refresh_attempts = 0
        owner._is_stl_project_file.return_value = True

        def refresh_project_bound_views():
            nonlocal refresh_attempts
            refresh_attempts += 1
            if refresh_attempts == 1:
                raise RuntimeError("injected stl common refresh failure")

        owner._refresh_project_bound_views.side_effect = refresh_project_bound_views
        result = {
            "registered_count": 1,
            "missing_count": 0,
            "rollback_token": rollback_token,
        }

        with patch.object(lifecycle_module, "register_stl_rendered_views_for_2d_review", return_value=result) as register:
            with self.assertRaisesRegex(RuntimeError, "injected stl common refresh failure"):
                owner.open_project_path(target_path)

        register.assert_called_once_with(owner.stl_project, owner.project, save=False)
        self.assertEqual(rollback_token.rollback_count, 1)
        self.assertEqual(owner.project.save_count, 0)
        self.assertEqual(owner.stl_project.current_project_path, lifecycle_module.canonical_path("old-stl.json"))
        self.assertEqual(owner.active_project_source_kind, "image")

    def test_stl_final_save_failure_rolls_back_staged_registration(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        owner = self._make_open_switch_owner("image")
        target_path = lifecycle_module.canonical_path("target-stl.json")
        rollback_token = FakeRollbackToken()
        owner._is_stl_project_file.return_value = True
        owner.project.save_error = RuntimeError("injected stl final save failure")
        result = {
            "registered_count": 1,
            "missing_count": 0,
            "rollback_token": rollback_token,
        }

        with patch.object(lifecycle_module, "register_stl_rendered_views_for_2d_review", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "injected stl final save failure"):
                owner.open_project_path(target_path)

        self.assertEqual(owner.project.save_count, 1)
        self.assertEqual(rollback_token.rollback_count, 1)
        self.assertEqual(owner.project.current_project_path, lifecycle_module.canonical_path("old-project.json"))
        self.assertEqual(owner.active_project_kind, "image")
        self.assertEqual(owner.active_project_entry_path, lifecycle_module.canonical_path("old-project.json"))

    def test_successful_stl_open_commits_once_then_finalizes_rollback_token(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        owner = self._make_open_switch_owner("image")
        target_path = lifecycle_module.canonical_path("target-stl.json")
        rollback_token = FakeRollbackToken()
        owner._is_stl_project_file.return_value = True
        result = {
            "registered_count": 1,
            "missing_count": 0,
            "rollback_token": rollback_token,
        }

        with patch.object(lifecycle_module, "register_stl_rendered_views_for_2d_review", return_value=result):
            owner.open_project_path(target_path)

        self.assertEqual(owner.project.save_count, 1)
        self.assertEqual(rollback_token.rollback_count, 0)
        self.assertEqual(rollback_token.finalize_count, 1)
        self.assertFalse(rollback_token.active)
        self.assertEqual(owner.active_project_source_kind, "stl")
        self.assertEqual(owner.active_project_entry_path, target_path)

    def test_stl_import_action_refresh_failure_rolls_back_and_restores_ui(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        owner = self._make_open_switch_owner("image")
        owner.workbench_widget = owner.target_tab
        owner.ensure_2d_stl_models_preloaded = Mock()
        rollback_token = FakeRollbackToken()
        refresh_attempts = 0

        def refresh_project_bound_views():
            nonlocal refresh_attempts
            refresh_attempts += 1
            if refresh_attempts == 1:
                owner.tabs.setCurrentWidget(owner.target_tab)
                raise RuntimeError("injected STL import refresh failure")

        owner._refresh_project_bound_views.side_effect = refresh_project_bound_views
        result = {
            "registered_count": 1,
            "specimen_count": 1,
            "unparsed_count": 0,
            "rollback_token": rollback_token,
        }

        with patch.object(
            lifecycle_module.QFileDialog,
            "getExistingDirectory",
            return_value="rendered-views",
        ), patch.object(
            lifecycle_module,
            "import_stl_rendered_views_into_2d_project",
            return_value=result,
        ) as import_views, patch.object(lifecycle_module.QMessageBox, "critical") as critical:
            owner.import_stl_rendered_views_action()

        import_views.assert_called_once_with(owner.project, "rendered-views", save=False)
        critical.assert_called_once()
        self.assertEqual(rollback_token.rollback_count, 1)
        self.assertEqual(rollback_token.finalize_count, 0)
        self.assertEqual(owner.project.save_count, 0)
        self.assertEqual(owner.active_project_source_kind, "image")
        self.assertIs(owner.tabs.currentWidget(), owner.old_tab)

    def test_tif_close_exception_rebuilds_workbench_and_aborts_switch(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module
        import AntSleap.ui.main_window_project_switch_support as switch_support_module

        owner = self._make_open_switch_owner("tif")
        workbench = owner.tif_workbench
        old_selection = {
            "current_specimen_id": "source-specimen",
            "current_volume_scope": "part",
            "current_part_id": "source-brain",
            "current_reslice_id": "source-axis",
        }
        for name, value in old_selection.items():
            setattr(workbench, name, value)

        def fail_partial_close(prompt_unsaved=True):
            self.assertTrue(prompt_unsaved)
            workbench.current_specimen_id = ""
            workbench.current_volume_scope = "full"
            workbench.current_part_id = ""
            workbench.current_reslice_id = ""
            raise RuntimeError("injected partial close failure")

        def assert_selection_before_refresh():
            self.assertEqual(
                {name: getattr(workbench, name) for name in old_selection},
                old_selection,
            )

        workbench.close_project.side_effect = fail_partial_close
        workbench.refresh_project.side_effect = assert_selection_before_refresh

        with patch.object(switch_support_module, "runtime_log_event") as log_event:
            owner.open_project_path("target-project.json")

        owner.tif_workbench.refresh_project.assert_called_once_with()
        self.assertEqual(owner.project.load_calls, [])
        self.assertEqual(owner.active_project_kind, "tif")
        self.assertEqual(
            {name: getattr(workbench, name) for name in old_selection},
            old_selection,
        )
        self.assertTrue(
            any(call.args and call.args[0] == "active_tif_close_failed" for call in log_event.call_args_list)
        )

    def test_new_tif_refresh_failure_reloads_previous_tif_project(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        owner = type("LifecycleOwner", (lifecycle_module.MainWindowProjectLifecycleMixin,), {})()
        old_path = lifecycle_module.canonical_path("old.tif_sqlite_manifest.json")
        owner.current_lang = "en"
        owner.active_project_kind = "tif"
        owner.last_workbench_kind = "tif"
        owner.active_project_source_kind = "tif"
        owner.active_project_entry_path = old_path
        owner.tif_project = FakeTifProject(old_path)
        owner.tif_workbench = SimpleNamespace(
            close_project=Mock(return_value=True),
            refresh_project=Mock(),
        )
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._is_tif_workflow_enabled = Mock(return_value=True)
        owner._default_project_dialog_dir = Mock(return_value="new-projects")
        owner._flush_pending_project_save = Mock()
        refresh_attempts = 0

        def refresh_project_bound_views():
            nonlocal refresh_attempts
            refresh_attempts += 1
            if refresh_attempts == 1:
                raise RuntimeError("injected refresh failure")
            owner.tif_workbench.refresh_project()

        owner._refresh_project_bound_views = Mock(side_effect=refresh_project_bound_views)
        owner.config = SimpleNamespace(get=Mock(return_value=old_path), set=Mock())
        owner.log = Mock()

        with patch.object(
            lifecycle_module.QFileDialog, "getExistingDirectory", return_value="new-projects"
        ), patch.object(
            lifecycle_module.QInputDialog, "getText", return_value=("new-tif", True)
        ):
            with self.assertRaisesRegex(RuntimeError, "injected refresh failure"):
                owner.new_tif_project()

        self.assertEqual(owner.tif_project.load_calls, [])
        self.assertEqual(owner.tif_project.current_project_path, old_path)
        self.assertEqual(owner.active_project_entry_path, old_path)
        owner.config.set.assert_any_call("last_project_path", old_path)
        owner.tif_workbench.refresh_project.assert_called_once_with()
        self.assertEqual(owner._refresh_project_bound_views.call_count, 2)

    def test_tif_recovery_refreshes_workbench_when_config_rollback_fails(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module
        import AntSleap.ui.main_window_project_switch_support as switch_support_module

        owner = type("LifecycleOwner", (lifecycle_module.MainWindowProjectLifecycleMixin,), {})()
        old_path = lifecycle_module.canonical_path("old.tif_sqlite_manifest.json")
        owner.active_project_kind = "image"
        owner.last_workbench_kind = "image"
        owner.active_project_source_kind = "image"
        owner.active_project_entry_path = "target.json"
        owner.tif_project = FakeTifProject(old_path)
        owner.tif_workbench = SimpleNamespace(refresh_project=Mock())
        owner._refresh_project_bound_views = Mock(side_effect=owner.tif_workbench.refresh_project)
        owner.config = SimpleNamespace(set=Mock(side_effect=RuntimeError("config locked")))
        state = {
            "active_project_kind": "tif",
            "last_workbench_kind": "tif",
            "active_project_source_kind": "tif",
            "active_project_entry_path": old_path,
            "project_path": old_path,
            "configured_last_project_path": old_path,
        }

        with patch.object(switch_support_module, "runtime_log_event") as log_event:
            self.assertFalse(owner._restore_active_tif_after_failed_switch(state))

        owner.tif_workbench.refresh_project.assert_called_once_with()
        self.assertEqual(owner.active_project_kind, "tif")
        self.assertEqual(owner.active_project_entry_path, old_path)
        self.assertTrue(
            any(call.args and call.args[0] == "active_project_switch_recovery_failed" for call in log_event.call_args_list)
        )

    def test_new_2d_project_does_not_flush_or_create_when_active_tif_close_is_cancelled(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        owner = type("LifecycleOwner", (lifecycle_module.MainWindowProjectLifecycleMixin,), {})()
        owner.current_lang = "en"
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._default_project_dialog_dir = Mock(return_value="projects")
        owner._choose_project_template = Mock(return_value={"template_id": "default"})
        owner._close_active_tif_workbench_for_project_switch = Mock(return_value=False)
        owner._flush_pending_project_save = Mock()
        owner.project = SimpleNamespace(create_project=Mock())

        with patch.object(lifecycle_module.QFileDialog, "getExistingDirectory", return_value="projects"), patch.object(
            lifecycle_module.QInputDialog, "getText", return_value=("new-2d", True)
        ):
            owner.new_project()

        owner._close_active_tif_workbench_for_project_switch.assert_called_once_with()
        owner._flush_pending_project_save.assert_not_called()
        owner.project.create_project.assert_not_called()

    def test_new_tif_project_does_not_flush_or_create_when_active_tif_close_is_cancelled(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        owner = type("LifecycleOwner", (lifecycle_module.MainWindowProjectLifecycleMixin,), {})()
        owner.current_lang = "en"
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._is_tif_workflow_enabled = Mock(return_value=True)
        owner._default_project_dialog_dir = Mock(return_value="tif-projects")
        owner._close_active_tif_workbench_for_project_switch = Mock(return_value=False)
        owner._flush_pending_project_save = Mock()
        owner.tif_project = SimpleNamespace(create_project=Mock())

        with patch.object(lifecycle_module.QFileDialog, "getExistingDirectory", return_value="tif-projects"), patch.object(
            lifecycle_module.QInputDialog, "getText", return_value=("new-tif", True)
        ):
            owner.new_tif_project()

        owner._close_active_tif_workbench_for_project_switch.assert_called_once_with()
        owner._flush_pending_project_save.assert_not_called()
        owner.tif_project.create_project.assert_not_called()

    def test_invalid_project_entry_does_not_close_active_tif(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        owner = type("LifecycleOwner", (lifecycle_module.MainWindowProjectLifecycleMixin,), {})()
        owner.current_lang = "en"
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._flush_pending_project_save = Mock()
        owner._is_project_sqlite_database_file = Mock(return_value=False)
        owner._read_project_probe_payload = Mock(return_value=None)
        owner._close_active_tif_workbench_for_project_switch = Mock(return_value=True)

        with patch.object(lifecycle_module.QMessageBox, "warning") as warning:
            owner.open_project_path(str(Path("invalid-project.json")))

        warning.assert_called_once()
        owner._close_active_tif_workbench_for_project_switch.assert_not_called()

    def test_legacy_migration_closes_active_tif_before_writing_outputs(self):
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        owner = type("LifecycleOwner", (MainWindowProjectLifecycleMixin,), {})()
        owner.current_lang = "en"
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._flush_pending_project_save = Mock()
        owner._is_project_sqlite_database_file = Mock(return_value=False)
        owner._read_project_probe_payload = Mock(return_value={"images": []})
        owner._is_legacy_2d_json_project_payload = Mock(return_value=True)
        owner._existing_sqlite_manifest_for_legacy_json = Mock(return_value="")
        owner._confirm_legacy_2d_json_migration = Mock(return_value=True)
        owner._close_active_tif_workbench_for_project_switch = Mock(return_value=False)
        owner._migrate_legacy_2d_project_with_progress = Mock()

        owner.open_project_path(str(Path("legacy-project.json")))

        owner._close_active_tif_workbench_for_project_switch.assert_called_once_with()
        owner._migrate_legacy_2d_project_with_progress.assert_not_called()

    def test_successful_legacy_migration_closes_active_tif_only_once(self):
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        owner = type("LifecycleOwner", (MainWindowProjectLifecycleMixin,), {})()
        owner.current_lang = "en"
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner._flush_pending_project_save = Mock()
        owner._is_project_sqlite_database_file = Mock(return_value=False)
        owner._read_project_probe_payload = Mock(return_value={"images": []})
        owner._is_legacy_2d_json_project_payload = Mock(return_value=True)
        owner._existing_sqlite_manifest_for_legacy_json = Mock(return_value="")
        owner._confirm_legacy_2d_json_migration = Mock(return_value=True)
        owner._close_active_tif_workbench_for_project_switch = Mock(return_value=True)
        owner._migrate_legacy_2d_project_with_progress = Mock(
            return_value=SimpleNamespace(
                manifest_path="migrated.sqlite_manifest.json",
                source_json_path="legacy-project.json",
                database_path="migrated.taxamask.sqlite",
                report_path="migration-report.json",
                stats={"image_count": 0, "label_count": 0},
            )
        )
        owner._is_tif_project_file = Mock(return_value=False)
        owner._is_stl_project_file = Mock(return_value=False)
        owner.project = SimpleNamespace(load_project=Mock(side_effect=RuntimeError("stop after load")))
        owner.log = Mock()

        with self.assertRaisesRegex(RuntimeError, "stop after load"):
            owner.open_project_path(str(Path("legacy-project.json")))

        owner._migrate_legacy_2d_project_with_progress.assert_called_once()
        owner._close_active_tif_workbench_for_project_switch.assert_called_once_with()

    def _make_real_new_project_failure_owner(
        self,
        root,
        project_kind,
        failure_stage,
        *,
        target_dir=None,
    ):
        from AntSleap.core.path_identity import canonical_path, path_identity
        from AntSleap.core.project import ProjectManager
        from AntSleap.core.tif_project import TifProjectManager

        is_tif = project_kind == "tif"
        owner = self._make_open_switch_owner("tif" if is_tif else "image")
        target_dir = Path(target_dir) if target_dir is not None else root / f"new-{project_kind}-{failure_stage}"
        old_dir = root / f"old-{project_kind}-{failure_stage}-{target_dir.name}"
        target_dir.mkdir(parents=True, exist_ok=True)
        sentinel = target_dir / "user-sentinel.txt"
        sentinel.write_text("keep", encoding="utf-8")

        if is_tif:
            manager = TifProjectManager()
            manager.create_project("old-tif", old_dir)
            owner.tif_project = manager
            owner.project = ProjectManager()
            manifest_path, database_path = manager._default_sqlite_paths_for_new_project(target_dir)
        else:
            manager = ProjectManager()
            manager.create_project("old-2d", old_dir)
            owner.project = manager
            owner.tif_project = TifProjectManager()
            manifest_path, database_path = manager._default_sqlite_paths_for_new_project("retry-project", target_dir)

        old_path = canonical_path(manager.current_project_path)
        old_data = copy.deepcopy(manager.project_data)
        owner.active_project_kind = "tif" if is_tif else "image"
        owner.last_workbench_kind = owner.active_project_kind
        owner.active_project_source_kind = owner.active_project_kind
        owner.active_project_entry_path = old_path
        owner._default_project_dialog_dir = Mock(return_value=str(target_dir))
        owner._choose_project_template = Mock(return_value={"template_id": "ant"})
        owner._flush_pending_project_save = Mock()

        manifest_path = canonical_path(manifest_path)
        database_path = canonical_path(database_path)
        target_identity = path_identity(manifest_path)
        failures = {failure_stage: 1}

        def fail_once(stage):
            if failures.get(stage, 0):
                failures[stage] -= 1
                return True
            return False

        config_state = {"last_project_path": old_path}

        def config_get(key, default=None):
            return config_state.get(key, default)

        def config_set(key, value):
            if key == "last_project_path" and path_identity(value) == target_identity and fail_once("config"):
                raise RuntimeError("injected config finalize failure")
            config_state[key] = value

        owner.config = SimpleNamespace(
            get=Mock(side_effect=config_get),
            set=Mock(side_effect=config_set),
        )
        owner.config_state = config_state

        def refresh_project_bound_views():
            current_path = manager.current_project_path or ""
            opening_target = path_identity(current_path) == target_identity
            owner.tabs.setCurrentWidget(owner.target_tab if opening_target else owner.old_tab)
            if opening_target and fail_once("refresh"):
                raise RuntimeError("injected refresh finalize failure")

        owner._refresh_project_bound_views = Mock(side_effect=refresh_project_bound_views)

        def preload_models():
            if fail_once("preload"):
                raise RuntimeError("injected preload finalize failure")

        owner.ensure_2d_stl_models_preloaded = Mock(side_effect=preload_models)
        if failure_stage == "canvas":
            owner.canvas.load_error = RuntimeError("injected canvas finalize failure")

        def log_message(_message):
            if path_identity(manager.current_project_path or "") == target_identity and fail_once("log"):
                raise RuntimeError("injected log finalize failure")

        owner.log = Mock(side_effect=log_message)
        return {
            "owner": owner,
            "manager": manager,
            "project_kind": project_kind,
            "old_path": old_path,
            "old_data": old_data,
            "target_dir": target_dir,
            "sentinel": sentinel,
            "manifest_path": Path(manifest_path),
            "database_path": Path(database_path),
            "artifact_paths": [
                Path(f"{database_path}-wal"),
                Path(f"{database_path}-shm"),
                Path(f"{database_path}-journal"),
                Path(database_path),
                Path(manifest_path),
            ],
            "marker_path": Path(owner._new_project_recovery_marker_path(manifest_path)),
        }

    def _write_valid_recovery_marker_for_fixture(
        self,
        fixture,
        *,
        state="preserved",
        created_at=None,
        expires_at=None,
    ):
        owner = fixture["owner"]
        project_kind = fixture["project_kind"]
        transaction = owner._new_project_artifact_transaction(
            fixture["manager"],
            project_kind,
            "retry-project",
            str(fixture["target_dir"]),
        )
        records = {}
        for path in transaction["artifacts"]:
            if not os.path.lexists(path):
                continue
            signature = owner._new_project_artifact_signature(path)
            self.assertIsNotNone(signature)
            records[path] = {**signature, "quarantine_path": ""}
        self.assertIn(transaction["manifest_path"], records)
        self.assertIn(transaction["database_path"], records)
        transaction["published_artifacts"] = records
        if created_at is not None:
            transaction["recovery_marker_created_at"] = int(created_at)
        if expires_at is not None:
            transaction["recovery_marker_expires_at"] = int(expires_at)
        payload = owner._new_project_marker_payload(transaction, state, "test marker")
        fixture["marker_path"].write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return transaction, payload

    def _assert_new_project_failure_restored_and_retry_succeeded(self, fixture, project_kind, failure_stage):
        from AntSleap.core.path_identity import canonical_path
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        owner = fixture["owner"]
        manager = fixture["manager"]
        manifest_path = fixture["manifest_path"]
        database_path = fixture["database_path"]
        artifact_paths = [
            manifest_path,
            database_path,
            Path(f"{database_path}-wal"),
            Path(f"{database_path}-shm"),
            Path(f"{database_path}-journal"),
        ]
        action = owner.new_tif_project if project_kind == "tif" else owner.new_project
        expected_error = f"injected {failure_stage} finalize failure"

        with patch.object(
            lifecycle_module.QFileDialog,
            "getExistingDirectory",
            return_value=str(fixture["target_dir"]),
        ), patch.object(
            lifecycle_module.QInputDialog,
            "getText",
            return_value=("retry-project", True),
        ):
            with self.assertRaisesRegex(RuntimeError, expected_error):
                action()

            self.assertTrue(fixture["target_dir"].is_dir())
            self.assertEqual(fixture["sentinel"].read_text(encoding="utf-8"), "keep")
            self.assertFalse(any(path.exists() for path in artifact_paths))
            self.assertEqual(list(fixture["target_dir"].glob("*.failed_new_project_*")), [])
            self.assertEqual(list(fixture["target_dir"].glob(".taxamask-new-project-quarantine-*.data")), [])
            self.assertEqual(list(fixture["target_dir"].glob(".taxamask-new-project-recovery-*.json")), [])
            self.assertEqual(canonical_path(manager.current_project_path), fixture["old_path"])
            self.assertEqual(manager.project_data, fixture["old_data"])
            self.assertEqual(owner.active_project_entry_path, fixture["old_path"])
            self.assertEqual(owner.config_state["last_project_path"], fixture["old_path"])
            self.assertIs(owner.tabs.currentWidget(), owner.old_tab)

            action()

        self.assertTrue(manifest_path.is_file())
        self.assertTrue(database_path.is_file())
        self.assertEqual(canonical_path(manager.current_project_path), canonical_path(manifest_path))
        self.assertEqual(owner.active_project_entry_path, canonical_path(manifest_path))
        self.assertEqual(owner.config_state["last_project_path"], canonical_path(manifest_path))
        self.assertIs(owner.tabs.currentWidget(), owner.target_tab)
        self.assertEqual(fixture["sentinel"].read_text(encoding="utf-8"), "keep")

    def test_new_2d_finalize_failures_rollback_disk_and_allow_same_name_retry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for failure_stage in ("config", "refresh", "preload", "canvas"):
                with self.subTest(failure_stage=failure_stage):
                    fixture = self._make_real_new_project_failure_owner(root, "image", failure_stage)
                    self._assert_new_project_failure_restored_and_retry_succeeded(
                        fixture,
                        "image",
                        failure_stage,
                    )

    def test_new_tif_finalize_failures_rollback_disk_and_allow_same_name_retry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for failure_stage in ("config", "refresh", "log"):
                with self.subTest(failure_stage=failure_stage):
                    fixture = self._make_real_new_project_failure_owner(root, "tif", failure_stage)
                    self._assert_new_project_failure_restored_and_retry_succeeded(
                        fixture,
                        "tif",
                        failure_stage,
                    )

    def test_new_project_preexisting_artifacts_are_never_removed_or_claimed_for_recovery(self):
        from AntSleap.core.path_identity import canonical_path
        from AntSleap.core.project import ProjectManager
        from AntSleap.core.tif_project import TifProjectManager
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for project_kind in ("image", "tif"):
                with self.subTest(project_kind=project_kind):
                    fixture = self._make_real_new_project_failure_owner(root, project_kind, "preexisting")
                    existing_manager = TifProjectManager() if project_kind == "tif" else ProjectManager()
                    if project_kind == "tif":
                        existing_manager.create_project("retry-project", fixture["target_dir"])
                        action = fixture["owner"].new_tif_project
                    else:
                        existing_manager.create_project("retry-project", fixture["target_dir"])
                        action = fixture["owner"].new_project
                    manifest_before = fixture["manifest_path"].read_bytes()
                    database_before = fixture["database_path"].read_bytes()

                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(fixture["target_dir"]),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ):
                        with self.assertRaisesRegex(RuntimeError, "new_project_creation_refused"):
                            action()

                    self.assertEqual(fixture["manifest_path"].read_bytes(), manifest_before)
                    self.assertEqual(fixture["database_path"].read_bytes(), database_before)
                    self.assertEqual(
                        canonical_path(fixture["manager"].current_project_path),
                        fixture["old_path"],
                    )
                    self.assertEqual(fixture["owner"].active_project_entry_path, fixture["old_path"])
                    self.assertIs(fixture["owner"].tabs.currentWidget(), fixture["owner"].old_tab)
                    self.assertEqual(getattr(fixture["owner"], "_pending_new_project_recoveries", {}), {})

    def test_preexisting_sqlite_journal_blocks_new_2d_and_tif_before_publication(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for project_kind in ("image", "tif"):
                with self.subTest(project_kind=project_kind):
                    fixture = self._make_real_new_project_failure_owner(root, project_kind, "journal")
                    journal = Path(f"{fixture['database_path']}-journal")
                    journal.write_bytes(b"preexisting-user-journal")
                    action = (
                        fixture["owner"].new_tif_project
                        if project_kind == "tif"
                        else fixture["owner"].new_project
                    )
                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(fixture["target_dir"]),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "preexisting_new_project_artifact",
                        ):
                            action()

                    self.assertEqual(journal.read_bytes(), b"preexisting-user-journal")
                    self.assertFalse(fixture["manifest_path"].exists())
                    self.assertFalse(fixture["database_path"].exists())
                    self.assertEqual(
                        list(fixture["target_dir"].glob(".taxamask-new-project-recovery-*.json")),
                        [],
                    )

    def test_new_2d_cleanup_move_failure_preserves_project_for_same_name_recovery(self):
        from AntSleap.core.path_identity import canonical_path, path_identity
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = self._make_real_new_project_failure_owner(Path(temp_dir), "image", "refresh")
            owner = fixture["owner"]
            manager = fixture["manager"]
            original_replace = lifecycle_module.os.replace
            database_identity = str(fixture["database_path"])
            move_failure_used = False

            def fail_database_quarantine(source, target):
                nonlocal move_failure_used
                if (
                    not move_failure_used
                    and canonical_path(source) == canonical_path(database_identity)
                    and ".taxamask-new-project-quarantine-" in str(target)
                ):
                    move_failure_used = True
                    raise PermissionError("injected locked database")
                return original_replace(source, target)

            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ):
                with patch.object(lifecycle_module.os, "replace", side_effect=fail_database_quarantine):
                    with self.assertRaisesRegex(RuntimeError, "injected refresh finalize failure"):
                        owner.new_project()

                self.assertTrue(fixture["manifest_path"].is_file())
                self.assertTrue(fixture["database_path"].is_file())
                self.assertEqual(canonical_path(manager.current_project_path), fixture["old_path"])
                with patch.object(manager, "load_project", wraps=manager.load_project) as load_project:
                    owner.new_project()

            load_project.assert_called_once_with(canonical_path(fixture["manifest_path"]))
            self.assertEqual(canonical_path(manager.current_project_path), canonical_path(fixture["manifest_path"]))
            self.assertNotIn(
                ("image", path_identity(fixture["manifest_path"])),
                getattr(owner, "_pending_new_project_recoveries", {}),
            )

    def test_successful_finalize_remove_failure_leaves_committed_marker(self):
        from AntSleap.core.path_identity import canonical_path
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for project_kind in ("image", "tif"):
                with self.subTest(project_kind=project_kind):
                    fixture = self._make_real_new_project_failure_owner(
                        root,
                        project_kind,
                        "success",
                    )
                    owner = fixture["owner"]
                    action = owner.new_tif_project if project_kind == "tif" else owner.new_project
                    original_remove = lifecycle_module.os.remove
                    marker_remove_failed = False

                    def fail_committed_marker_remove(path):
                        nonlocal marker_remove_failed
                        if (
                            not marker_remove_failed
                            and canonical_path(path) == canonical_path(fixture["marker_path"])
                        ):
                            marker_remove_failed = True
                            raise PermissionError("injected committed marker remove failure")
                        return original_remove(path)

                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(fixture["target_dir"]),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ), patch.object(
                        lifecycle_module.os,
                        "remove",
                        side_effect=fail_committed_marker_remove,
                    ):
                        action()

                    self.assertTrue(marker_remove_failed)
                    marker_payload = json.loads(fixture["marker_path"].read_text(encoding="utf-8"))
                    self.assertEqual(marker_payload["state"], "committed")
                    manifest_before = fixture["manifest_path"].read_bytes()
                    database_before = fixture["database_path"].read_bytes()
                    self.assertEqual(getattr(owner, "_pending_new_project_recoveries", {}), {})

                    fresh = self._make_real_new_project_failure_owner(
                        root,
                        project_kind,
                        "fresh-committed",
                        target_dir=fixture["target_dir"],
                    )
                    fresh_action = (
                        fresh["owner"].new_tif_project
                        if project_kind == "tif"
                        else fresh["owner"].new_project
                    )
                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(fixture["target_dir"]),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ), patch.object(
                        fresh["manager"],
                        "load_project",
                        wraps=fresh["manager"].load_project,
                    ) as load_project:
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "preexisting_new_project_artifact",
                        ):
                            fresh_action()

                    load_project.assert_not_called()
                    self.assertFalse(fixture["marker_path"].exists())
                    self.assertEqual(fixture["manifest_path"].read_bytes(), manifest_before)
                    self.assertEqual(fixture["database_path"].read_bytes(), database_before)
                    self.assertEqual(
                        list(
                            fixture["target_dir"].glob(
                                ".taxamask-new-project-quarantine-*.data"
                            )
                        ),
                        [],
                    )

    def test_structurally_valid_forged_marker_never_claims_existing_project(self):
        from AntSleap.core.project import ProjectManager
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = self._make_real_new_project_failure_owner(
                Path(temp_dir),
                "image",
                "forged-marker",
            )
            existing = ProjectManager()
            existing.create_project("retry-project", fixture["target_dir"])
            manifest_before = fixture["manifest_path"].read_bytes()
            database_before = fixture["database_path"].read_bytes()
            _transaction, payload = self._write_valid_recovery_marker_for_fixture(fixture)
            self.assertEqual(payload["state"], "preserved")

            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ), patch.object(
                fixture["manager"],
                "load_project",
                wraps=fixture["manager"].load_project,
            ) as load_project:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "recovery_marker_preserved_requires_manual_review",
                ):
                    fixture["owner"].new_project()

            load_project.assert_not_called()
            self.assertTrue(fixture["marker_path"].is_file())
            self.assertEqual(fixture["manifest_path"].read_bytes(), manifest_before)
            self.assertEqual(fixture["database_path"].read_bytes(), database_before)
            self.assertEqual(
                list(
                    fixture["target_dir"].glob(
                        ".taxamask-new-project-quarantine-*.data"
                    )
                ),
                [],
            )

    def test_expired_recovery_marker_never_claims_or_cleans_artifacts(self):
        from AntSleap.core.project import ProjectManager
        from AntSleap.ui.main_window_project_switch_support import (
            NEW_PROJECT_RECOVERY_TTL_SECONDS,
        )
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = self._make_real_new_project_failure_owner(
                Path(temp_dir),
                "image",
                "expired-marker",
            )
            existing = ProjectManager()
            existing.create_project("retry-project", fixture["target_dir"])
            manifest_before = fixture["manifest_path"].read_bytes()
            database_before = fixture["database_path"].read_bytes()
            now = int(time.time())
            self._write_valid_recovery_marker_for_fixture(
                fixture,
                created_at=now - NEW_PROJECT_RECOVERY_TTL_SECONDS,
                expires_at=now - 1,
            )

            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ), patch.object(
                fixture["manager"],
                "load_project",
                wraps=fixture["manager"].load_project,
            ) as load_project:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "recovery_marker_expired_manual_open_required",
                ):
                    fixture["owner"].new_project()

            load_project.assert_not_called()
            self.assertTrue(fixture["marker_path"].is_file())
            self.assertEqual(fixture["manifest_path"].read_bytes(), manifest_before)
            self.assertEqual(fixture["database_path"].read_bytes(), database_before)

    def test_recovery_marker_rooted_atomic_write_preserves_fixed_tmp_file(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module
        import AntSleap.ui.main_window_project_switch_support as support_module

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = self._make_real_new_project_failure_owner(
                Path(temp_dir),
                "image",
                "fixed-tmp-file",
            )
            fixed_tmp = Path(f"{fixture['marker_path']}.tmp")
            fixed_tmp.write_bytes(b"preexisting-fixed-temp")
            original_writer = support_module.atomic_write_json_in_root
            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ), patch.object(
                support_module,
                "atomic_write_json_in_root",
                wraps=original_writer,
            ) as rooted_writer:
                fixture["owner"].new_project()

            self.assertEqual(fixed_tmp.read_bytes(), b"preexisting-fixed-temp")
            self.assertGreaterEqual(rooted_writer.call_count, 2)
            for call in rooted_writer.call_args_list:
                self.assertEqual(call.kwargs["trusted_root"], str(fixture["target_dir"]))
                self.assertEqual(call.kwargs["max_bytes"], 64 * 1024)

    def test_recovery_marker_write_refuses_path_outside_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self._make_real_new_project_failure_owner(
                root,
                "image",
                "marker-outside-root",
            )
            transaction = fixture["owner"]._new_project_artifact_transaction(
                fixture["manager"],
                "image",
                "retry-project",
                str(fixture["target_dir"]),
            )
            outside = root / "outside-marker-sentinel.json"
            outside.write_bytes(b"outside-marker-sentinel")
            transaction["recovery_marker_path"] = str(outside)

            self.assertFalse(
                fixture["owner"]._write_new_project_recovery_marker(
                    transaction,
                    "published",
                    "must be refused",
                )
            )
            self.assertEqual(outside.read_bytes(), b"outside-marker-sentinel")

    def test_recovery_marker_rooted_atomic_write_preserves_fixed_tmp_link(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self._make_real_new_project_failure_owner(
                root,
                "image",
                "fixed-tmp-link",
            )
            link_target = root / "outside-fixed-temp-target.txt"
            link_target.write_bytes(b"outside-sentinel")
            fixed_tmp = Path(f"{fixture['marker_path']}.tmp")
            try:
                os.symlink(link_target, fixed_tmp)
            except (OSError, NotImplementedError) as exc:
                try:
                    os.link(link_target, fixed_tmp)
                except OSError as link_exc:
                    self.skipTest(
                        f"file links are unavailable: symlink={exc}; hardlink={link_exc}"
                    )

            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ):
                fixture["owner"].new_project()

            self.assertTrue(os.path.samefile(fixed_tmp, link_target))
            self.assertEqual(link_target.read_bytes(), b"outside-sentinel")

    def test_delete_marker_update_failure_deletes_nothing_and_memory_recovers(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = self._make_real_new_project_failure_owner(
                Path(temp_dir),
                "image",
                "refresh",
            )
            owner = fixture["owner"]
            original_write = owner._write_new_project_recovery_marker
            attempted_states = []

            def fail_delete_and_preserved_marker(transaction, state, reason=""):
                attempted_states.append(state)
                if state in {"delete_incomplete", "preserved"}:
                    return False
                return original_write(transaction, state, reason)

            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ), patch.object(
                owner,
                "_write_new_project_recovery_marker",
                side_effect=fail_delete_and_preserved_marker,
            ):
                with self.assertRaisesRegex(RuntimeError, "injected refresh finalize failure"):
                    owner.new_project()

            self.assertIn("delete_incomplete", attempted_states)
            self.assertIn("preserved", attempted_states)
            quarantines = list(
                fixture["target_dir"].glob(".taxamask-new-project-quarantine-*.data")
            )
            self.assertEqual(len(quarantines), 2)
            marker_payload = json.loads(fixture["marker_path"].read_text(encoding="utf-8"))
            self.assertEqual(marker_payload["state"], "rollback_in_progress")
            pending = getattr(owner, "_pending_new_project_recoveries", {})
            self.assertEqual(len(pending), 1)
            self.assertEqual(next(iter(pending.values()))["recovery_action"], "open_preserved")

            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ), patch.object(
                fixture["manager"],
                "load_project",
                wraps=fixture["manager"].load_project,
            ) as load_project:
                owner.new_project()

            load_project.assert_called_once()
            self.assertTrue(fixture["manifest_path"].is_file())
            self.assertTrue(fixture["database_path"].is_file())
            self.assertEqual(
                list(
                    fixture["target_dir"].glob(
                        ".taxamask-new-project-quarantine-*.data"
                    )
                ),
                [],
            )
            self.assertFalse(fixture["marker_path"].exists())
            self.assertEqual(getattr(owner, "_pending_new_project_recoveries", {}), {})

    def test_partial_quarantine_delete_failure_keeps_state_and_same_owner_finishes(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = self._make_real_new_project_failure_owner(
                Path(temp_dir),
                "image",
                "refresh",
            )
            owner = fixture["owner"]
            original_remove = lifecycle_module.os.remove
            quarantine_remove_count = 0

            def fail_second_quarantine_remove(path):
                nonlocal quarantine_remove_count
                if ".taxamask-new-project-quarantine-" in os.path.basename(str(path)):
                    quarantine_remove_count += 1
                    if quarantine_remove_count == 2:
                        raise PermissionError("injected second quarantine remove failure")
                return original_remove(path)

            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ), patch.object(
                lifecycle_module.os,
                "remove",
                side_effect=fail_second_quarantine_remove,
            ):
                with self.assertRaisesRegex(RuntimeError, "injected refresh finalize failure"):
                    owner.new_project()

            self.assertEqual(quarantine_remove_count, 2)
            self.assertFalse(fixture["manifest_path"].exists())
            self.assertFalse(fixture["database_path"].exists())
            self.assertEqual(
                len(
                    list(
                        fixture["target_dir"].glob(
                            ".taxamask-new-project-quarantine-*.data"
                        )
                    )
                ),
                1,
            )
            marker_payload = json.loads(fixture["marker_path"].read_text(encoding="utf-8"))
            self.assertEqual(marker_payload["state"], "delete_incomplete")
            pending = getattr(owner, "_pending_new_project_recoveries", {})
            self.assertEqual(next(iter(pending.values()))["recovery_action"], "finish_delete")

            fresh = self._make_real_new_project_failure_owner(
                Path(temp_dir),
                "image",
                "fresh-delete-incomplete",
                target_dir=fixture["target_dir"],
            )
            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ), patch.object(
                fresh["manager"],
                "load_project",
                wraps=fresh["manager"].load_project,
            ) as fresh_load:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "recovery_marker_delete_incomplete_requires_manual_review",
                ):
                    fresh["owner"].new_project()

            fresh_load.assert_not_called()
            self.assertEqual(
                len(
                    list(
                        fixture["target_dir"].glob(
                            ".taxamask-new-project-quarantine-*.data"
                        )
                    )
                ),
                1,
            )
            self.assertEqual(
                json.loads(fixture["marker_path"].read_text(encoding="utf-8"))["state"],
                "delete_incomplete",
            )

            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ), patch.object(
                fixture["manager"],
                "create_project",
                wraps=fixture["manager"].create_project,
            ) as create_project:
                owner.new_project()

            create_project.assert_called_once()
            self.assertTrue(fixture["manifest_path"].is_file())
            self.assertTrue(fixture["database_path"].is_file())
            self.assertFalse(fixture["marker_path"].exists())
            self.assertEqual(
                list(
                    fixture["target_dir"].glob(
                        ".taxamask-new-project-quarantine-*.data"
                    )
                ),
                [],
            )
            self.assertEqual(getattr(owner, "_pending_new_project_recoveries", {}), {})

    def test_preserved_new_project_marker_requires_manual_review_for_fresh_owner(self):
        from AntSleap.core.path_identity import canonical_path
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for project_kind in ("image", "tif"):
                with self.subTest(project_kind=project_kind):
                    fixture = self._make_real_new_project_failure_owner(root, project_kind, "refresh")
                    owner = fixture["owner"]
                    action = owner.new_tif_project if project_kind == "tif" else owner.new_project
                    original_replace = lifecycle_module.os.replace
                    move_failure_used = False

                    def fail_database_quarantine(source, target):
                        nonlocal move_failure_used
                        if (
                            not move_failure_used
                            and canonical_path(source) == canonical_path(fixture["database_path"])
                            and ".taxamask-new-project-quarantine-" in str(target)
                        ):
                            move_failure_used = True
                            raise PermissionError("injected locked database")
                        return original_replace(source, target)

                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(fixture["target_dir"]),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ), patch.object(lifecycle_module.os, "replace", side_effect=fail_database_quarantine):
                        with self.assertRaisesRegex(RuntimeError, "injected refresh finalize failure"):
                            action()

                    markers = list(fixture["target_dir"].glob(".taxamask-new-project-recovery-*.json"))
                    self.assertEqual(len(markers), 1)
                    self.assertTrue(fixture["manifest_path"].is_file())
                    self.assertTrue(fixture["database_path"].is_file())

                    fresh = self._make_real_new_project_failure_owner(
                        root,
                        project_kind,
                        "fresh-owner",
                        target_dir=fixture["target_dir"],
                    )
                    fresh_action = fresh["owner"].new_tif_project if project_kind == "tif" else fresh["owner"].new_project
                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(fixture["target_dir"]),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ), patch.object(
                        fresh["manager"],
                        "load_project",
                        wraps=fresh["manager"].load_project,
                    ) as load_project:
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "recovery_marker_preserved_requires_manual_review",
                        ):
                            fresh_action()

                    load_project.assert_not_called()
                    self.assertEqual(
                        canonical_path(fresh["manager"].current_project_path),
                        fresh["old_path"],
                    )
                    self.assertTrue(fixture["manifest_path"].is_file())
                    self.assertTrue(fixture["database_path"].is_file())
                    self.assertEqual(
                        len(
                            list(
                                fixture["target_dir"].glob(
                                    ".taxamask-new-project-recovery-*.json"
                                )
                            )
                        ),
                        1,
                    )

    def test_new_project_sidecar_toctou_is_preserved_and_refused(self):
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for mode in ("appeared_after_capture", "replaced_after_capture"):
                with self.subTest(mode=mode):
                    target_dir = root / mode
                    fixture = self._make_real_new_project_failure_owner(
                        root,
                        "image",
                        "refresh",
                        target_dir=target_dir,
                    )
                    owner = fixture["owner"]
                    sidecar = Path(f"{fixture['database_path']}-wal")
                    if mode == "appeared_after_capture":
                        original_restore = owner._restore_active_project_after_failed_switch

                        def restore_then_add_sidecar(state):
                            result = original_restore(state)
                            sidecar.write_bytes(b"late-unowned-sidecar")
                            return result

                        owner._restore_active_project_after_failed_switch = restore_then_add_sidecar
                    else:
                        original_capture = owner._capture_new_project_publication

                        def capture_then_replace_sidecar(transaction, manager):
                            sidecar.write_bytes(b"captured-sidecar")
                            result = original_capture(transaction, manager)
                            sidecar.unlink()
                            sidecar.write_bytes(b"replacement-sidecar")
                            return result

                        owner._capture_new_project_publication = capture_then_replace_sidecar

                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(target_dir),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ):
                        with self.assertRaisesRegex(RuntimeError, "injected refresh finalize failure"):
                            owner.new_project()

                    self.assertTrue(fixture["manifest_path"].is_file())
                    self.assertTrue(fixture["database_path"].is_file())
                    self.assertTrue(sidecar.is_file())
                    self.assertEqual(len(list(target_dir.glob(".taxamask-new-project-recovery-*.json"))), 1)

                    fresh = self._make_real_new_project_failure_owner(
                        root,
                        "image",
                        f"fresh-{mode}",
                        target_dir=target_dir,
                    )
                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(target_dir),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ), patch.object(
                        fresh["manager"],
                        "load_project",
                        wraps=fresh["manager"].load_project,
                    ) as load_project:
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "recovery_marker_preserved_requires_manual_review",
                        ):
                            fresh["owner"].new_project()

                    load_project.assert_not_called()
                    self.assertTrue(fixture["manifest_path"].is_file())
                    self.assertTrue(fixture["database_path"].is_file())
                    self.assertTrue(sidecar.is_file())

    def test_bad_recovery_marker_and_modified_preserved_project_are_never_claimed(self):
        from AntSleap.core.path_identity import canonical_path
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bad_fixture = self._make_real_new_project_failure_owner(root, "image", "bad-marker")
            bad_marker = Path(
                bad_fixture["owner"]._new_project_recovery_marker_path(bad_fixture["manifest_path"])
            )
            bad_marker.write_text("{broken", encoding="utf-8")
            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(bad_fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ):
                with self.assertRaisesRegex(RuntimeError, "recovery_marker_json_invalid"):
                    bad_fixture["owner"].new_project()
            self.assertFalse(bad_fixture["manifest_path"].exists())
            self.assertFalse(bad_fixture["database_path"].exists())
            self.assertEqual(bad_marker.read_text(encoding="utf-8"), "{broken")

            fixture = self._make_real_new_project_failure_owner(root, "image", "refresh")
            original_replace = lifecycle_module.os.replace

            def fail_database_quarantine(source, target):
                if (
                    canonical_path(source) == canonical_path(fixture["database_path"])
                    and ".taxamask-new-project-quarantine-" in str(target)
                ):
                    raise PermissionError("injected locked database")
                return original_replace(source, target)

            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ), patch.object(lifecycle_module.os, "replace", side_effect=fail_database_quarantine):
                with self.assertRaisesRegex(RuntimeError, "injected refresh finalize failure"):
                    fixture["owner"].new_project()

            fixture["manifest_path"].write_bytes(fixture["manifest_path"].read_bytes() + b"\n")
            fresh = self._make_real_new_project_failure_owner(
                root,
                "image",
                "fresh-modified",
                target_dir=fixture["target_dir"],
            )
            with patch.object(
                lifecycle_module.QFileDialog,
                "getExistingDirectory",
                return_value=str(fixture["target_dir"]),
            ), patch.object(
                lifecycle_module.QInputDialog,
                "getText",
                return_value=("retry-project", True),
            ), patch.object(
                fresh["manager"],
                "load_project",
                wraps=fresh["manager"].load_project,
            ) as load_project:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "recovery_marker_preserved_requires_manual_review",
                ):
                    fresh["owner"].new_project()
            load_project.assert_not_called()

    def test_partial_quarantine_requires_same_owner_recovery(self):
        from AntSleap.core.path_identity import canonical_path
        import AntSleap.ui.main_window_project_lifecycle as lifecycle_module

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for project_kind in ("image", "tif"):
                with self.subTest(project_kind=project_kind):
                    fixture = self._make_real_new_project_failure_owner(root, project_kind, "refresh")
                    action = (
                        fixture["owner"].new_tif_project
                        if project_kind == "tif"
                        else fixture["owner"].new_project
                    )
                    original_replace = lifecycle_module.os.replace
                    manifest_move_failed = False
                    database_restore_failed = False

                    def fail_manifest_move_and_database_restore(source, target):
                        nonlocal manifest_move_failed, database_restore_failed
                        source_text = canonical_path(source)
                        target_text = canonical_path(target)
                        if (
                            not manifest_move_failed
                            and source_text == canonical_path(fixture["manifest_path"])
                            and ".taxamask-new-project-quarantine-" in target_text
                        ):
                            manifest_move_failed = True
                            raise PermissionError("injected manifest quarantine failure")
                        if (
                            not database_restore_failed
                            and target_text == canonical_path(fixture["database_path"])
                            and ".taxamask-new-project-quarantine-" in source_text
                        ):
                            database_restore_failed = True
                            raise PermissionError("injected database restore failure")
                        return original_replace(source, target)

                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(fixture["target_dir"]),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ), patch.object(
                        lifecycle_module.os,
                        "replace",
                        side_effect=fail_manifest_move_and_database_restore,
                    ):
                        with self.assertRaisesRegex(RuntimeError, "injected refresh finalize failure"):
                            action()

                    self.assertTrue(fixture["manifest_path"].is_file())
                    self.assertFalse(fixture["database_path"].exists())
                    quarantines = list(fixture["target_dir"].glob(".taxamask-new-project-quarantine-*.data"))
                    self.assertEqual(len(quarantines), 1)
                    self.assertEqual(len(list(fixture["target_dir"].glob(".taxamask-new-project-recovery-*.json"))), 1)

                    fresh = self._make_real_new_project_failure_owner(
                        root,
                        project_kind,
                        "fresh-double-failure",
                        target_dir=fixture["target_dir"],
                    )
                    fresh_action = (
                        fresh["owner"].new_tif_project
                        if project_kind == "tif"
                        else fresh["owner"].new_project
                    )
                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(fixture["target_dir"]),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ), patch.object(
                        fresh["manager"],
                        "load_project",
                        wraps=fresh["manager"].load_project,
                    ) as load_project:
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "recovery_marker_preserved_requires_manual_review",
                        ):
                            fresh_action()

                    load_project.assert_not_called()
                    self.assertFalse(fixture["database_path"].exists())
                    self.assertEqual(
                        len(
                            list(
                                fixture["target_dir"].glob(
                                    ".taxamask-new-project-quarantine-*.data"
                                )
                            )
                        ),
                        1,
                    )
                    with patch.object(
                        lifecycle_module.QFileDialog,
                        "getExistingDirectory",
                        return_value=str(fixture["target_dir"]),
                    ), patch.object(
                        lifecycle_module.QInputDialog,
                        "getText",
                        return_value=("retry-project", True),
                    ), patch.object(
                        fixture["manager"],
                        "load_project",
                        wraps=fixture["manager"].load_project,
                    ) as same_owner_load:
                        action()

                    same_owner_load.assert_called_once_with(
                        canonical_path(fixture["manifest_path"])
                    )
                    self.assertTrue(fixture["database_path"].is_file())
                    self.assertEqual(list(fixture["target_dir"].glob(".taxamask-new-project-quarantine-*.data")), [])
                    self.assertEqual(list(fixture["target_dir"].glob(".taxamask-new-project-recovery-*.json")), [])


if __name__ == "__main__":
    unittest.main()
