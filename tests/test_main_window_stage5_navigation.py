import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
