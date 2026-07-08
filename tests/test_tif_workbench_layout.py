import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QSizePolicy, QWidget, QVBoxLayout
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.ui.tif_workbench_control_panels import build_right_control_panel
    from AntSleap.ui.tif_workbench_layout import (
        make_panel,
        make_right_sidebar_responsive,
        make_section,
        make_task_page,
    )
    from AntSleap.ui.tif_workbench_pages import build_task_pages


@unittest.skipUnless(QApplication is not None, "PySide6 is required for TIF workbench layout tests")
class TifWorkbenchLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_and_section_register_titles_without_business_state(self):
        panel_titles = {}
        panel, panel_layout = make_panel("Specimens", "tifSpecimenPanel", panel_titles)
        section_titles = {}
        section, section_layout = make_section("Data import", "tifImportSection", section_titles)

        self.assertEqual(panel.objectName(), "tifSpecimenPanel")
        self.assertEqual(section.objectName(), "tifImportSection")
        self.assertEqual(panel_titles["tifSpecimenPanel"][0], "Specimens")
        self.assertEqual(section_titles["tifImportSection"][0], "Data import")
        self.assertGreaterEqual(panel_layout.count(), 1)
        self.assertGreaterEqual(section_layout.count(), 1)

    def test_task_page_uses_stable_scroll_area_contract(self):
        page, layout = make_task_page("tifPartTaskPage")
        body = page.widget()

        self.assertEqual(page.objectName(), "tifInspectorScroll")
        self.assertTrue(page.widgetResizable())
        self.assertEqual(page.horizontalScrollBarPolicy(), Qt.ScrollBarAsNeeded)
        self.assertIs(body.layout(), layout)
        self.assertEqual(body.objectName(), "tifPartTaskPage")
        self.assertEqual(body.sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)

    def test_right_sidebar_responsive_relaxes_visible_controls(self):
        right_panel, right_layout = make_panel("Volume controls", "tifControlPanel")
        page, page_layout = make_task_page("tifTrainingTaskPage")
        long_button = QPushButton("Very long localized training button text that should not force the sidebar wider")
        long_label = QLabel("Long explanation that wraps instead of widening the right sidebar")
        long_label.setWordWrap(True)
        line_edit = QLineEdit("C:/very/long/path/to/backend/python.exe")
        page_layout.addWidget(long_button)
        page_layout.addWidget(long_label)
        page_layout.addWidget(line_edit)
        right_layout.addWidget(page)

        make_right_sidebar_responsive(right_panel, [page])

        self.assertEqual(right_panel.minimumWidth(), 360)
        self.assertEqual(right_panel.maximumWidth(), 520)
        self.assertEqual(page.sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)
        self.assertEqual(page.widget().sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)
        self.assertEqual(long_button.minimumWidth(), 0)
        self.assertEqual(long_button.sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)
        self.assertEqual(long_button.toolTip(), long_button.text())
        self.assertEqual(long_label.sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)
        self.assertEqual(line_edit.minimumWidth(), 0)
        self.assertEqual(line_edit.sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)

    def test_task_pages_preserve_tab_contract(self):
        parts = build_task_pages("zh", lambda text, lang: f"{lang}:{text}")

        self.assertEqual(parts["task_tabs"].objectName(), "tifTaskTabs")
        self.assertEqual(parts["training_mode_tabs"].objectName(), "tifTrainingModeTabs")
        self.assertEqual(parts["part_task_page"].widget().objectName(), "tifPartTaskPage")
        self.assertEqual(parts["display_task_page"].widget().objectName(), "tifDisplayTaskPage")
        self.assertEqual(parts["annotation_task_page"].widget().objectName(), "tifAnnotationTaskPage")
        self.assertEqual(parts["training_task_page"].widget().objectName(), "tifTrainingTaskPage")
        self.assertEqual(parts["result_compare_page"].widget().objectName(), "tifResultCompareTaskPage")
        self.assertEqual(parts["task_tabs"].count(), 3)
        self.assertEqual(parts["training_mode_tabs"].count(), 3)

    def test_right_control_panel_preserves_operation_section(self):
        panel_titles = {}
        section_titles = {}
        parts = build_right_control_panel(panel_titles, section_titles)

        self.assertEqual(parts["panel"].objectName(), "tifControlPanel")
        self.assertEqual(parts["panel"].minimumWidth(), 360)
        self.assertEqual(parts["panel"].maximumWidth(), 520)
        self.assertEqual(parts["operation_status_section"].objectName(), "tifOperationStatusSection")
        self.assertIn("tifControlPanel", panel_titles)
        self.assertIn("tifOperationStatusSection", section_titles)


if __name__ == "__main__":
    unittest.main()
