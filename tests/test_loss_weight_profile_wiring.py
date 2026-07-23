# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

import os
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from AntSleap.core.engine import AntEngine
from AntSleap.core.model_profiles import DEFAULT_BLINK_OUTER_LOSS_WEIGHTS, PARENT_BACKEND_BUILTIN
from AntSleap.ui import main_window_training as training_module
from AntSleap.ui.blink_lab import BlinkLabWidget
from AntSleap.ui.main_window_blink_context import MainWindowBlinkContextMixin
from AntSleap.ui.main_window_training import MainWindowTrainingMixin


class _Signal:
    def connect(self, _callback):
        return None


class _Button:
    def setEnabled(self, _enabled):
        return None


class _TrainingThread:
    last_kwargs = None

    def __init__(self, *_args, **kwargs):
        type(self).last_kwargs = dict(kwargs)
        self.log_signal = _Signal()
        self.progress_signal = _Signal()
        self.report_signal = _Signal()
        self.success_signal = _Signal()
        self.error_signal = _Signal()
        self.finished_signal = _Signal()

    def start(self):
        return None


class LossWeightProfileWiringTests(unittest.TestCase):
    def test_parent_profile_weights_reach_gui_engine_and_training_context(self):
        custom_weights = {"heatmap": 1.6, "wh": 0.7}
        engine = AntEngine.__new__(AntEngine)
        engine.set_locator_loss_weights(None)
        engine.locator_resolution = (512, 512)
        engine.weights_dir = os.getcwd()
        project = types.SimpleNamespace(
            current_project_path=os.path.join(os.getcwd(), "project.sqlite_manifest.json"),
            get_active_model_profile=lambda: {
                "profile_id": "custom_parent_loss",
                "parent_backend": {
                    "backend_type": PARENT_BACKEND_BUILTIN,
                    "loss_weights": custom_weights,
                },
            }
        )
        window = types.SimpleNamespace(
            engine=engine,
            project=project,
            current_lang="en",
            train_epochs=2,
            train_batch=1,
            train_lr=1e-4,
            train_wd=1e-4,
            btn_train=_Button(),
            btn_stop_training=_Button(),
            _is_child_training_running=lambda: False,
            _ensure_training_initial_weights_registered=lambda _train_segmenter: True,
            _current_training_initial_weights=lambda _train_segmenter: [],
            _capture_project_task_context=lambda: {},
            _refresh_blink_refine_state=lambda: None,
            _set_training_progress=lambda *_args: None,
            log=lambda *_args: None,
            show_training_report=lambda *_args: None,
            _on_training_success=lambda: None,
            _on_training_error=lambda *_args: None,
            _on_training_finished=lambda: None,
        )

        prepared = types.SimpleNamespace(
            dataset={
                "taxonomy": ["Head"],
                "locator_scope": ["Head"],
                "locator_records": [],
                "parts_records": [],
            },
            locator_train_records=[],
            locator_validation_records=[],
            parts_train_records=[],
            parts_validation_records=[],
            run=object(),
        )
        with patch.object(training_module, "TrainingThread", _TrainingThread), patch.object(
            training_module, "prepare_2d_training_run", return_value=prepared
        ):
            MainWindowTrainingMixin._launch_training_with_preflight(
                window,
                {"selected_locator_size": [640, 384]},
                ["Head"],
                ["Head"],
            )

        expected_snapshot = {"locator": custom_weights}
        self.assertEqual(engine.loss_config_snapshot, expected_snapshot)
        self.assertEqual(_TrainingThread.last_kwargs["training_context"]["loss_config"], expected_snapshot)

    def test_child_profile_weights_reach_blink_lab_defaults(self):
        custom_weights = {"final": 1.25, "step": 0.5, "view": 0.3, "consistency": 0.2}

        class Lab:
            kwargs = None

            def set_training_defaults(self, *_args, **kwargs):
                self.kwargs = dict(kwargs)

        lab = Lab()
        project = types.SimpleNamespace(
            get_active_model_profile=lambda: {
                "child_backend_defaults": {
                    "backend_type": "vit_b_blink",
                    "loss_weights": custom_weights,
                }
            }
        )
        window = types.SimpleNamespace(
            blink_lab=lab,
            project=project,
            blink_train_epochs=5,
            blink_train_batch=2,
            blink_train_lr=1e-3,
            blink_train_weight_decay=1e-4,
            blink_train_input_size=224,
            blink_auto_shrink_steps=20,
            runtime_device="cpu",
        )

        MainWindowBlinkContextMixin._sync_blink_lab_model_profile_defaults(window)

        self.assertEqual(lab.kwargs["outer_loss_weights"], custom_weights)

    def test_missing_legacy_child_weights_reset_stale_custom_defaults(self):
        holder = types.SimpleNamespace(default_outer_loss_weights={"final": 9.0})

        BlinkLabWidget.set_training_defaults(
            holder,
            outer_loss_weights=None,
            apply_to_controls=False,
        )

        self.assertEqual(holder.default_outer_loss_weights, DEFAULT_BLINK_OUTER_LOSS_WEIGHTS)


if __name__ == "__main__":
    unittest.main()
