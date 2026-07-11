import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FakePixmap:
    def isNull(self):
        return False


class FakeCanvas:
    def __init__(self):
        self.original_pixmap = FakePixmap()
        self.loaded_paths = []
        self.polygons = []
        self.boxes = []

    def load_image(self, path):
        self.loaded_paths.append(path)

    def set_polygons(self, labels):
        self.polygons.append(labels)

    def set_boxes(self, *boxes, **named_boxes):
        self.boxes.append((boxes, named_boxes))


class FakeCombo:
    def __init__(self):
        self.values = []

    def blockSignals(self, _blocked):
        return None

    def setCurrentText(self, value):
        self.values.append(value)


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self.callbacks):
            callback(*args)


class FakeProgressDialog:
    def __init__(self, *_args):
        self.maximum_value = int(_args[3])
        self.closed = False

    def setWindowTitle(self, _title):
        pass

    def setWindowModality(self, _modality):
        pass

    def setMinimumDuration(self, _duration):
        pass

    def setAutoClose(self, _enabled):
        pass

    def setAutoReset(self, _enabled):
        pass

    def setCancelButton(self, _button):
        pass

    def show(self):
        pass

    def maximum(self):
        return self.maximum_value

    def setMaximum(self, value):
        self.maximum_value = int(value)

    def setRange(self, _minimum, maximum):
        self.maximum_value = int(maximum)

    def setValue(self, _value):
        pass

    def setLabelText(self, _text):
        pass

    def close(self):
        self.closed = True


class FakeImportThread:
    def __init__(self, project, paths):
        self.project = project
        self.paths = list(paths)
        self.progress_signal = FakeSignal()
        self.success_signal = FakeSignal()
        self.error_signal = FakeSignal()
        self.finished_signal = FakeSignal()
        self.deleted = False

    def isRunning(self):
        return False

    def start(self):
        pass

    def deleteLater(self):
        self.deleted = True


class FakeItem:
    def __init__(self, path, qt):
        self.path = path
        self.qt = qt

    def data(self, role):
        if role == self.qt.UserRole:
            return self.path
        if role == self.qt.UserRole + 1:
            return None
        return None

    def text(self):
        return Path(self.path).name


class FakeProject:
    def __init__(self, path):
        self.path = path
        self.project_data = {"images": [path]}
        self.group_updates = []

    def get_labels(self, _path):
        return {"Head": [[1, 1], [2, 1], [2, 2]]}

    def get_boxes(self, _path):
        return {"Head": [1, 1, 2, 2]}

    def get_genus(self, _path):
        return "Aphaenogaster"

    def get_image_provenance(self, _path):
        return {}

    def set_image_provenance(self, path, provenance, save=False):
        self.group_updates.append((path, provenance, save))


class MainWindowStage5NavigationTests(unittest.TestCase):
    def test_main_window_inherits_stage5_workflow_contracts(self):
        import AntSleap.main as main_module
        from AntSleap.ui.main_window_image_navigation import MainWindowImageNavigationMixin
        from AntSleap.ui.main_window_literature_bridge import MainWindowLiteratureBridgeMixin
        from AntSleap.ui.main_window_part_tree import MainWindowPartTreeMixin

        self.assertIs(main_module.MainWindow.refresh_file_list, MainWindowImageNavigationMixin.refresh_file_list)
        self.assertIs(main_module.MainWindow.on_file_selected, MainWindowPartTreeMixin.on_file_selected)
        self.assertIs(
            main_module.MainWindow._resolve_current_literature_context,
            MainWindowLiteratureBridgeMixin._resolve_current_literature_context,
        )

    def test_stage5_modules_do_not_import_main_window(self):
        for filename in (
            "main_window_part_tree.py",
            "main_window_image_navigation.py",
            "main_window_literature_bridge.py",
        ):
            source = (ROOT / "AntSleap" / "ui" / filename).read_text(encoding="utf-8")
            self.assertNotIn("AntSleap.main", source)
            self.assertNotIn("from main import", source)

    def test_same_image_selection_skips_pixmap_reload_and_navigation_save(self):
        from AntSleap.ui.main_window_navigation_dependencies import Qt
        from AntSleap.ui.main_window_part_tree import MainWindowPartTreeMixin

        image_path = str(ROOT / "same-image.png")
        owner = type("NavigationOwner", (MainWindowPartTreeMixin,), {})()
        owner.current_image = image_path
        owner.project = FakeProject(image_path)
        owner.canvas = FakeCanvas()
        owner.genus_combo = FakeCombo()
        owner.deferred_saves = 0
        owner.blink_refreshes = 0
        owner._same_project_image_path = lambda left, right: Path(left) == Path(right)
        owner._defer_project_save_for_active_navigation = lambda: setattr(
            owner, "deferred_saves", owner.deferred_saves + 1
        )
        owner._auto_boxes_for_canvas = lambda _path: ({}, {})
        owner._current_shrink_loose_boxes = lambda: {}
        owner.on_enhancement_changed = lambda: None
        owner._refresh_blink_refine_state = lambda: setattr(
            owner, "blink_refreshes", owner.blink_refreshes + 1
        )

        owner.on_file_selected(FakeItem(image_path, Qt), None)

        self.assertEqual(owner.canvas.loaded_paths, [])
        self.assertEqual(owner.deferred_saves, 0)
        self.assertEqual(owner.blink_refreshes, 1)

    def test_group_move_defers_one_save_without_direct_project_write(self):
        from AntSleap.ui.main_window_image_navigation import MainWindowImageNavigationMixin

        image_path = str(ROOT / "group-image.png")
        owner = type("GroupOwner", (MainWindowImageNavigationMixin,), {})()
        owner.project = FakeProject(image_path)
        owner.current_lang = "en"
        owner.save_requests = 0
        owner.file_refreshes = 0
        owner.vlm_refreshes = 0
        owner._all_image_group_definitions = lambda: [("review", "Review")]
        owner._remove_empty_custom_image_groups = lambda: None
        owner._schedule_project_save = lambda: setattr(owner, "save_requests", owner.save_requests + 1)
        owner.refresh_file_list = lambda: setattr(owner, "file_refreshes", owner.file_refreshes + 1)
        owner._refresh_vlm_image_group_combo = lambda: setattr(owner, "vlm_refreshes", owner.vlm_refreshes + 1)
        owner._image_group_display_name = lambda key: key
        owner.log = lambda _message: None

        owner.move_images_to_group([image_path], "review")

        self.assertEqual(owner.project.group_updates, [(image_path, {"manual_image_group": "review"}, False)])
        self.assertEqual(owner.save_requests, 1)
        self.assertEqual(owner.file_refreshes, 1)
        self.assertEqual(owner.vlm_refreshes, 1)

    def test_stale_background_import_callback_does_not_touch_new_project(self):
        from AntSleap.ui.main_window_image_navigation import MainWindowImageNavigationMixin
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
        import AntSleap.ui.main_window_image_navigation as navigation_module

        owner = type(
            "ImportOwner",
            (MainWindowImageNavigationMixin, MainWindowModelManagementMixin),
            {},
        )()
        owner.current_lang = "en"
        owner.project = type("ImportProject", (), {"current_project_path": "old-project.json"})()
        owner.image_import_thread = None
        owner.image_import_progress_dialog = None
        owner._flush_pending_project_save = lambda **_kwargs: None
        owner._prepare_progress_dialog = lambda *_args, **_kwargs: None
        owner._set_image_import_controls_enabled = lambda _enabled: None
        owner._short_progress_path = lambda path, limit=64: str(path)[:limit]
        provenance_writes = []
        refreshes = []
        stale_events = []
        owner._inherit_crop_provenance = lambda records: provenance_writes.extend(records)
        owner.refresh_file_list = lambda: refreshes.append("refresh")
        owner.log = lambda _message: None
        owner._log_stale_project_task_result = lambda workflow, _context: stale_events.append(workflow)

        with patch.object(navigation_module, "QProgressDialog", FakeProgressDialog), patch.object(
            navigation_module,
            "ImageImportThread",
            FakeImportThread,
        ):
            self.assertTrue(
                owner._start_image_import(
                    [f"image-{index}.png" for index in range(20)],
                    crop_records=[{"crop": "old"}],
                )
            )

        thread = owner.image_import_thread
        owner.project.current_project_path = "new-project.json"
        thread.success_signal.emit(20, 20)
        thread.finished_signal.emit()

        self.assertEqual(provenance_writes, [])
        self.assertEqual(refreshes, [])
        self.assertEqual(stale_events, ["image_import_success"])
        self.assertTrue(thread.deleted)
        self.assertIsNone(owner.image_import_thread)


if __name__ == "__main__":
    unittest.main()
