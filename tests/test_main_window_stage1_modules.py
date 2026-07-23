import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FakeWheelEvent:
    def __init__(self):
        self.ignored = False

    def ignore(self):
        self.ignored = True


class MainWindowStage1ModuleTests(unittest.TestCase):
    def test_runtime_module_has_no_qt_cv2_or_torch_import_side_effects(self):
        command = [
            sys.executable,
            "-c",
            (
                "import sys; import AntSleap.app_runtime; "
                "print(int('PySide6' in sys.modules), int('cv2' in sys.modules), int('torch' in sys.modules))"
            ),
        ]
        completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30)

        self.assertEqual(completed.stdout.strip(), "0 0 0")

    def test_main_prepares_qt_environment_before_heavy_imports(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")

        self.assertLess(source.index("_prepare_qt_runtime_environment()"), source.index("import cv2"))
        self.assertLess(source.index("_prepare_qt_runtime_environment()"), source.index("from PySide6.QtWidgets"))

    def test_runtime_flag_setup_is_idempotent(self):
        from AntSleap import app_runtime

        with patch.dict(os.environ, {"QTWEBENGINE_CHROMIUM_FLAGS": "--disable-gpu"}, clear=False):
            app_runtime.ensure_qtwebengine_quiet_cpu_flags()
            app_runtime.ensure_qtwebengine_quiet_cpu_flags()
            flags = os.environ["QTWEBENGINE_CHROMIUM_FLAGS"].split()

        self.assertEqual(flags.count("--disable-gpu"), 1)
        self.assertIn("--disable-webgl", flags)
        self.assertIn("--log-level=3", flags)

    def test_runtime_log_stops_at_configured_session_capacity(self):
        from AntSleap import app_runtime

        handle = io.StringIO()
        with patch.dict(
            os.environ,
            {"TAXAMASK_RUNTIME_LOG_MAX_BYTES": "1024"},
            clear=False,
        ), patch.multiple(
            app_runtime,
            _RUNTIME_LOG_FILE=handle,
            _RUNTIME_LOG_BYTES_WRITTEN=0,
            _RUNTIME_LOG_LIMIT_REACHED=False,
        ):
            for index in range(100):
                app_runtime.runtime_log_event(
                    "capacity_test",
                    index=index,
                    payload="x" * 180,
                )
            size_at_limit = len(handle.getvalue().encode("utf-8"))
            app_runtime.runtime_log_event("must_not_grow", payload="y" * 500)
            final_size = len(handle.getvalue().encode("utf-8"))
            limit_reached = app_runtime._RUNTIME_LOG_LIMIT_REACHED

        self.assertTrue(limit_reached)
        self.assertLessEqual(size_at_limit, 1024)
        self.assertEqual(final_size, size_at_limit)

    def test_main_reexports_stage1_classes(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import AntSleap.main as main_module
        from AntSleap.ui import main_window_widgets, main_window_workers

        self.assertIs(main_module.InferenceThread, main_window_workers.InferenceThread)
        self.assertIs(main_module.TrainingThread, main_window_workers.TrainingThread)
        self.assertIs(main_module.NoWheelComboBox, main_window_widgets.NoWheelComboBox)
        self.assertIs(main_module.ImageGroupListWidget, main_window_widgets.ImageGroupListWidget)

    def test_no_wheel_controls_ignore_wheel_events(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from AntSleap.ui.main_window_widgets import NoWheelComboBox, NoWheelSlider, NoWheelSpinBox

        app = QApplication.instance() or QApplication([])
        controls = [NoWheelComboBox(), NoWheelSpinBox(), NoWheelSlider()]
        try:
            for control in controls:
                event = FakeWheelEvent()
                control.wheelEvent(event)
                self.assertTrue(event.ignored)
        finally:
            for control in controls:
                control.deleteLater()
            app.processEvents()

    def test_image_import_worker_preserves_progress_and_result_contract(self):
        from AntSleap.ui.main_window_workers import ImageImportThread

        class Project:
            def add_images(self, image_paths, progress_callback=None):
                progress_callback(1, len(image_paths), image_paths[0])
                return len(image_paths)

        progress = []
        success = []
        worker = ImageImportThread(Project(), ["a.png", "b.png"])
        worker.progress_signal.connect(lambda done, total, label: progress.append((done, total, label)))
        worker.success_signal.connect(lambda added, total: success.append((added, total)))
        worker.run()

        self.assertEqual(progress, [(1, 2, "a.png")])
        self.assertEqual(success, [(2, 2)])

    def test_training_worker_uses_injected_translation_without_main_import(self):
        from AntSleap.ui.main_window_workers import TrainingThread

        class Engine:
            locator_resolution = (512, 512)
            history = {}

            def save_weights(self, **_kwargs):
                return "demo"

            def generate_report(self, _loader, num_samples, training_context):
                return {"dir": tempfile.gettempdir(), "num_samples": num_samples, "context": training_context}

        logs = []
        worker = TrainingThread(
            Engine(),
            {},
            [],
            [],
            lang="zh",
            train_segmenter=False,
            translate=lambda text, lang: f"{lang}:{text}",
        )
        worker.log_signal.connect(logs.append)
        worker.run()

        self.assertIn("zh:Locator stage skipped: no eligible locator samples.", logs)
        self.assertIn("zh:SAM stage skipped: locator-only training is enabled.", logs)
        self.assertTrue(any(text.startswith("zh:Training Finished!") for text in logs))


if __name__ == "__main__":
    unittest.main()
