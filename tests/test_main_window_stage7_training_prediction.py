import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FakeProject:
    def __init__(self, path):
        self.current_project_path = path
        self.profile_updates = []

    def update_active_model_profile_parent_weights(self, **kwargs):
        self.profile_updates.append(kwargs)


class FakeRunningThread:
    def isRunning(self):
        return True


class FakeButton:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)


class MainWindowStage7TrainingPredictionTests(unittest.TestCase):
    def test_parent_training_uses_verified_sam_bytes_after_path_swap(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        original = b"registered-base-sam"
        observed = {
            "entry_kind": "file",
            "size_bytes": len(original),
            "hash_algorithm": "sha256",
            "digest": hashlib.sha256(original).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as tmp:
            weight_path = Path(tmp) / "sam_b.pt"
            weight_path.write_bytes(original)
            configured = []

            class FakeEngine:
                def configure_verified_base_sam(
                    self,
                    checkpoint_bytes,
                    *,
                    reference="",
                    fingerprint=None,
                ):
                    configured.append(
                        (checkpoint_bytes, reference, dict(fingerprint or {}))
                    )
                    return {
                        **dict(fingerprint or {}),
                        "reference": reference,
                    }

            owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
            owner.project = object()
            owner.engine = FakeEngine()
            owner._current_training_initial_weights = lambda _enabled: [
                {"slot": "parent.sam_base", "path": weight_path}
            ]

            def read_then_swap(_project, entry):
                weight_path.write_bytes(b"replacement-after-verification")
                return {
                    "slot": entry["slot"],
                    "path": str(weight_path),
                    "status": "verified",
                    "observed": observed,
                    "payload": original,
                }

            with patch(
                "AntSleap.ui.main_window_training.read_verified_initial_weight",
                side_effect=read_then_swap,
            ):
                evidence = owner._configure_parent_training_verified_sam(True)

            self.assertEqual(weight_path.read_bytes(), b"replacement-after-verification")
            self.assertEqual(configured, [(original, str(weight_path), observed)])
            self.assertTrue(evidence["loaded_from_verified_bytes"])
            self.assertNotIn("payload", evidence)

    def test_parent_training_replaces_mismatched_preloaded_sam_runtime(self):
        from AntSleap.core.engine import AntEngine
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        payload = b"verified-base-sam"
        observed = {
            "entry_kind": "file",
            "size_bytes": len(payload),
            "hash_algorithm": "sha256",
            "digest": hashlib.sha256(payload).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as tmp:
            weight_path = Path(tmp) / "sam_b.pt"
            weight_path.write_bytes(payload)
            engine = AntEngine.__new__(AntEngine)
            engine.base_sam_path = str(weight_path)
            engine.parts_model = type(
                "PreloadedSAM",
                (),
                {"loaded_checkpoint_identity": {"digest": "wrong-base"}},
            )()
            engine.opt_parts = object()
            engine.base_sam_predictor = object()
            engine.loaded_sam_decoder_reference = "stale-decoder.pth"
            engine.loaded_sam_decoder_identity = {"digest": "stale"}
            engine.verified_base_sam_identity = {"digest": "wrong-base"}

            owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
            owner.project = object()
            owner.engine = engine
            owner._current_training_initial_weights = lambda _enabled: [
                {"slot": "parent.sam_base", "path": weight_path}
            ]
            verified = {
                "slot": "parent.sam_base",
                "path": str(weight_path),
                "status": "verified",
                "observed": observed,
                "payload": payload,
            }

            with patch(
                "AntSleap.ui.main_window_training.read_verified_initial_weight",
                return_value=verified,
            ):
                evidence = owner._configure_parent_training_verified_sam(True)

            self.assertIsNone(engine.parts_model)
            self.assertIsNone(engine.opt_parts)
            self.assertIsNone(engine.base_sam_predictor)
            self.assertEqual(engine.loaded_sam_decoder_reference, "")
            self.assertEqual(engine._verified_base_sam_bytes, payload)
            self.assertEqual(engine.verified_base_sam_identity["digest"], observed["digest"])
            self.assertEqual(evidence["runtime_identity"], engine.verified_base_sam_identity)

    def test_locator_only_parent_training_does_not_read_base_sam(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
        with patch(
            "AntSleap.ui.main_window_training.read_verified_initial_weight"
        ) as reader:
            self.assertEqual(
                owner._configure_parent_training_verified_sam(False),
                {},
            )
        reader.assert_not_called()

    def test_parent_training_binds_verified_decoder_and_locator_after_base(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        payloads = {
            "parent.sam_base": b"base-sam",
            "parent.sam_decoder": b"sam-decoder",
            "parent.locator": b"locator",
        }
        with tempfile.TemporaryDirectory() as tmp:
            paths = {
                slot: Path(tmp) / f"{slot.replace('.', '-')}.pth"
                for slot in payloads
            }
            for slot, path in paths.items():
                path.write_bytes(payloads[slot])

            entries = [
                {"slot": "parent.sam_base", "path": paths["parent.sam_base"]},
                {
                    "slot": "parent.sam_decoder",
                    "path": paths["parent.sam_decoder"],
                    "selection": "decoder-run",
                },
                {
                    "slot": "parent.locator",
                    "path": paths["parent.locator"],
                    "selection": "locator-run",
                },
            ]

            class FakeEngine:
                def __init__(self):
                    self.events = []
                    self.loaded_sam_decoder_identity = {}
                    self.loaded_locator_identity = {}

                @staticmethod
                def _identity(checkpoint_bytes, reference):
                    return {
                        "source": "memory",
                        "reference": reference,
                        "size_bytes": len(checkpoint_bytes),
                        "hash_algorithm": "sha256",
                        "digest": hashlib.sha256(checkpoint_bytes).hexdigest(),
                    }

                def configure_verified_base_sam(
                    self,
                    checkpoint_bytes,
                    *,
                    reference="",
                    fingerprint=None,
                ):
                    self.events.append(("base", checkpoint_bytes, reference))
                    return self._identity(checkpoint_bytes, reference)

                def load_sam_decoder(
                    self,
                    selection,
                    *,
                    checkpoint_path=None,
                    checkpoint_bytes=None,
                ):
                    self.events.append(("decoder", checkpoint_bytes, selection))
                    self.loaded_sam_decoder_identity = self._identity(
                        checkpoint_bytes,
                        str(checkpoint_path),
                    )

                def load_locator(
                    self,
                    selection,
                    *,
                    checkpoint_path=None,
                    checkpoint_bytes=None,
                    expected_locator_scope=None,
                ):
                    self.events.append(
                        (
                            "locator",
                            checkpoint_bytes,
                            selection,
                            list(expected_locator_scope or []),
                        )
                    )
                    self.loaded_locator_identity = self._identity(
                        checkpoint_bytes,
                        str(checkpoint_path),
                    )

            owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
            owner.project = object()
            owner.engine = FakeEngine()
            owner._current_training_initial_weights = lambda enabled: [
                dict(item)
                for item in entries
                if enabled or item["slot"] == "parent.locator"
            ]

            def verified_then_swap(_project, entry):
                slot = entry["slot"]
                payload = payloads[slot]
                paths[slot].write_bytes(b"replacement-" + payload)
                return {
                    "slot": slot,
                    "path": str(paths[slot]),
                    "status": "verified",
                    "observed": {
                        "entry_kind": "file",
                        "size_bytes": len(payload),
                        "hash_algorithm": "sha256",
                        "digest": hashlib.sha256(payload).hexdigest(),
                    },
                    "payload": payload,
                }

            with patch(
                "AntSleap.ui.main_window_training.read_verified_initial_weight",
                side_effect=verified_then_swap,
            ):
                evidence = owner._load_parent_training_verified_models(
                    True,
                    ["Head"],
                )

            self.assertEqual(
                [event[0] for event in owner.engine.events],
                ["base", "decoder", "locator"],
            )
            self.assertEqual(owner.engine.events[1][1], payloads["parent.sam_decoder"])
            self.assertEqual(owner.engine.events[2][1], payloads["parent.locator"])
            self.assertEqual(owner.engine.events[2][3], ["Head"])
            for slot, key in (
                ("parent.sam_base", "base_sam"),
                ("parent.sam_decoder", "sam_decoder"),
                ("parent.locator", "locator"),
            ):
                self.assertEqual(
                    evidence[key]["fingerprint"]["digest"],
                    evidence[key]["runtime_identity"]["digest"],
                )
                self.assertNotIn("payload", evidence[key])
                self.assertEqual(
                    paths[slot].read_bytes(),
                    b"replacement-" + payloads[slot],
                )

    def test_locator_only_model_binding_never_loads_sam_decoder(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        payload = b"verified-locator"
        observed = {
            "entry_kind": "file",
            "size_bytes": len(payload),
            "hash_algorithm": "sha256",
            "digest": hashlib.sha256(payload).hexdigest(),
        }

        class FakeEngine:
            loaded_locator_identity = {}

            def load_sam_decoder(self, *_args, **_kwargs):
                raise AssertionError("locator-only training loaded SAM decoder")

            def load_locator(
                self,
                _selection,
                *,
                checkpoint_path=None,
                checkpoint_bytes=None,
                expected_locator_scope=None,
            ):
                self.loaded_locator_identity = {
                    **observed,
                    "source": "memory",
                    "reference": str(checkpoint_path),
                }

        owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
        owner.project = object()
        owner.engine = FakeEngine()
        owner._current_training_initial_weights = lambda _enabled: [
            {
                "slot": "parent.locator",
                "path": ROOT / "locator.pth",
                "selection": "locator-run",
            }
        ]
        verified = {
            "slot": "parent.locator",
            "path": str(ROOT / "locator.pth"),
            "status": "verified",
            "observed": observed,
            "payload": payload,
        }
        with patch(
            "AntSleap.ui.main_window_training.read_verified_initial_weight",
            return_value=verified,
        ) as reader:
            evidence = owner._load_parent_training_verified_models(False, ["Head"])

        self.assertEqual(reader.call_count, 1)
        self.assertEqual(evidence["base_sam"], {})
        self.assertEqual(evidence["sam_decoder"], {})
        self.assertEqual(evidence["locator"]["fingerprint"], observed)

    def test_parent_model_binding_failure_clears_runtimes_and_fails_run(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        class FakeRun:
            status = "running"

            def __init__(self):
                self.failures = []

            def fail(self, error, *, stage):
                self.failures.append((str(error), stage))
                self.status = "failed"

        class FakeEngine:
            def __init__(self):
                self.parts_cleared = 0
                self.locator_cleared = 0

            def _clear_failed_parts_load(self):
                self.parts_cleared += 1

            def _clear_failed_locator_load(self):
                self.locator_cleared += 1

        owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
        owner.engine = FakeEngine()
        owner.current_lang = "en"
        owner.btn_train = FakeButton()
        owner.btn_stop_training = FakeButton()
        owner._set_training_progress = lambda *_args: None
        owner._refresh_blink_refine_state = lambda: None
        run = FakeRun()
        prepared = type("Prepared", (), {"run": run})()
        request = {
            "preflight": {},
            "train_segmenter": True,
            "active_profile": {},
            "parent_backend": {},
            "effective_loss_config": {},
            "scope_id": "__all__",
            "scope_label": "All Images",
            "scope_image_count": 1,
            "locator_scope": ["Head"],
        }

        with patch.object(
            MainWindowTrainingMixin,
            "_load_parent_training_verified_models",
            side_effect=ValueError("initial_weight_not_verified"),
        ), patch(
            "AntSleap.ui.main_window_training.QMessageBox.critical"
        ):
            owner._start_parent_training_thread(prepared, request)

        self.assertEqual(owner.engine.parts_cleared, 1)
        self.assertEqual(owner.engine.locator_cleared, 1)
        self.assertEqual(
            run.failures,
            [("initial_weight_not_verified", "initial_weight_load")],
        )
        self.assertTrue(owner.parent_training_failed)
        self.assertTrue(owner.btn_train.enabled)
        self.assertFalse(owner.btn_stop_training.enabled)

    def test_main_window_inherits_stage7_workflow_contracts(self):
        import AntSleap.main as main_module
        from AntSleap.ui.main_window_export import MainWindowExportMixin
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
        from AntSleap.ui.main_window_prediction import MainWindowPredictionMixin
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin
        from AntSleap.ui.main_window_vlm import MainWindowVlmMixin

        self.assertIs(main_module.MainWindow.refresh_model_list, MainWindowModelManagementMixin.refresh_model_list)
        self.assertIs(main_module.MainWindow.run_training, MainWindowTrainingMixin.run_training)
        self.assertIs(main_module.MainWindow.run_prediction, MainWindowPredictionMixin.run_prediction)
        self.assertIs(
            main_module.MainWindow.run_vlm_preannotation_from_settings,
            MainWindowVlmMixin.run_vlm_preannotation_from_settings,
        )
        self.assertIs(main_module.MainWindow.export_dataset, MainWindowExportMixin.export_dataset)

    def test_stage7_modules_do_not_import_main_window(self):
        for filename in (
            "main_window_model_management.py",
            "main_window_training.py",
            "main_window_prediction.py",
            "main_window_vlm.py",
            "main_window_export.py",
        ):
            source = (ROOT / "AntSleap" / "ui" / filename).read_text(encoding="utf-8")
            self.assertNotIn("AntSleap.main", source)
            self.assertNotIn("from main import", source)

    def test_project_task_context_requires_same_manager_and_path(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        owner = type("ContextOwner", (MainWindowModelManagementMixin,), {})()
        first_project = FakeProject(str(ROOT / "first.sqlite_manifest.json"))
        owner.project = first_project
        context = owner._capture_project_task_context()

        self.assertTrue(owner._project_task_context_matches(context))
        first_project.current_project_path = str(ROOT / "second.sqlite_manifest.json")
        self.assertFalse(owner._project_task_context_matches(context))
        owner.project = FakeProject(str(ROOT / "first.sqlite_manifest.json"))
        self.assertFalse(owner._project_task_context_matches(context))

    def test_stale_training_success_does_not_update_new_project_profile(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowModelManagementMixin, MainWindowTrainingMixin), {})()
        old_project = FakeProject(str(ROOT / "old.sqlite_manifest.json"))
        owner.project = old_project
        owner.parent_training_project_context = owner._capture_project_task_context()
        new_project = FakeProject(str(ROOT / "new.sqlite_manifest.json"))
        owner.project = new_project
        owner.stale_events = []
        owner._log_stale_project_task_result = lambda workflow, context: owner.stale_events.append(workflow)
        owner.trainer = type(
            "Trainer",
            (),
            {"training_context": {"locator_weights": "locator.pth", "segmenter_weights": "segmenter.pth"}},
        )()

        owner._on_training_success()

        self.assertEqual(new_project.profile_updates, [])
        self.assertEqual(owner.stale_events, ["parent_training_success"])

    def test_stale_vlm_worker_run_is_ignored(self):
        from AntSleap.ui.main_window_vlm import MainWindowVlmMixin

        owner = type("VlmOwner", (MainWindowVlmMixin,), {})()
        owner.vlm_preannotation_run_id = "current-run"
        owner.vlm_preannotation_records = []
        worker = type("Worker", (), {"run_id": "old-run"})()

        owner._on_vlm_preannotation_image_result({"image_path": "specimen.png"}, worker=worker)

        self.assertEqual(owner.vlm_preannotation_records, [])

    def test_stale_project_vlm_result_is_cancelled_without_project_write(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
        from AntSleap.ui.main_window_vlm import MainWindowVlmMixin

        owner = type("VlmContextOwner", (MainWindowModelManagementMixin, MainWindowVlmMixin), {})()
        old_project = FakeProject(str(ROOT / "old.sqlite_manifest.json"))
        owner.project = old_project
        owner.vlm_preannotation_project_context = owner._capture_project_task_context()
        owner.project = FakeProject(str(ROOT / "new.sqlite_manifest.json"))
        owner.vlm_preannotation_run_id = "run-1"
        owner.vlm_preannotation_records = []
        owner.vlm_preannotation_queue = ["queued.png"]
        owner.completed = []
        owner._log_stale_project_task_result = lambda workflow, context: owner.completed.append(workflow)
        owner._complete_current_vlm_image_steps = lambda step, image_path=None: owner.completed.append(step)
        owner._mark_current_vlm_image_done = lambda step, image_path=None: owner.completed.append(step)
        worker = type("Worker", (), {"run_id": "run-1"})()

        owner._on_vlm_preannotation_image_result({"image_path": "old.png"}, worker=worker)

        self.assertTrue(owner.vlm_preannotation_cancel_requested)
        self.assertEqual(owner.vlm_preannotation_queue, [])
        self.assertEqual(owner.vlm_preannotation_records[0]["status"], "stale_project")
        self.assertIn("vlm_image_result", owner.completed)

    def test_dataset_export_blocks_project_switch(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        owner = type("BusyOwner", (MainWindowModelManagementMixin,), {})()
        owner.current_lang = "en"
        owner.dataset_export_thread = FakeRunningThread()

        self.assertEqual(owner._active_project_bound_background_task(), "Export")

    def test_child_training_and_sam_block_project_switch(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        owner = type("BusyOwner", (MainWindowModelManagementMixin,), {})()
        owner.current_lang = "en"
        owner.blink_lab = type("BlinkLab", (), {"training_thread": FakeRunningThread()})()
        owner.sam_busy = False

        self.assertEqual(owner._active_project_bound_background_task(), "Training")

        owner.blink_lab.training_thread = None
        owner.sam_busy = True

        self.assertEqual(owner._active_project_bound_background_task(), "SAM Auto-Annotation")

    def test_sam_base_reload_blocks_project_switch(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        owner = type("BusyOwner", (MainWindowModelManagementMixin,), {})()
        owner.current_lang = "en"
        owner.sam_base_reload_pending = True

        self.assertEqual(
            owner._active_project_bound_background_task(),
            "SAM Auto-Annotation",
        )

    def test_refresh_model_list_without_engine_restores_signal_states(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        class ComboStub:
            def __init__(self, blocked):
                self.blocked = blocked

            def count(self):
                return 0

            def blockSignals(self, blocked):
                previous = self.blocked
                self.blocked = bool(blocked)
                return previous

            def clear(self):
                pass

        owner = type("ModelListOwner", (MainWindowModelManagementMixin,), {})()
        owner.engine = None
        owner.combo_locator = ComboStub(blocked=False)
        owner.combo_segmenter = ComboStub(blocked=True)

        owner.refresh_model_list()

        self.assertFalse(owner.combo_locator.blocked)
        self.assertTrue(owner.combo_segmenter.blocked)

    def test_parent_and_blink_preflight_block_project_switch(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        owner = type("BusyOwner", (MainWindowModelManagementMixin,), {})()
        owner.current_lang = "en"
        owner.training_preflight_thread = FakeRunningThread()

        self.assertEqual(owner._active_project_bound_background_task(), "Training")

        owner.training_preflight_thread = None
        owner.blink_lab = type(
            "BlinkLab",
            (),
            {
                "training_thread": None,
                "training_preflight_thread": FakeRunningThread(),
            },
        )()

        self.assertEqual(owner._active_project_bound_background_task(), "Training")

    def test_tif_write_threads_block_project_switch(self):
        from types import SimpleNamespace

        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        cases = (
            ("auto_save_thread", "annotation"),
            ("manual_save_thread", "annotation"),
            ("promote_thread", "annotation"),
            ("_tif_import_thread", "workbench"),
            ("_tif_backend_thread", "workbench"),
        )
        for attribute, owner_kind in cases:
            with self.subTest(attribute=attribute):
                owner = type("BusyOwner", (MainWindowModelManagementMixin,), {})()
                owner.current_lang = "en"
                annotation = SimpleNamespace()
                workbench = SimpleNamespace(annotation_workflow_controller=annotation)
                setattr(annotation if owner_kind == "annotation" else workbench, attribute, object())
                owner.tif_workbench = workbench

                self.assertTrue(owner._active_project_bound_background_task())

        owner = type("BusyOwner", (MainWindowModelManagementMixin,), {})()
        owner.current_lang = "en"
        owner.tif_workbench = SimpleNamespace(
            annotation_workflow_controller=SimpleNamespace(saving_working_edit=True)
        )
        self.assertTrue(owner._active_project_bound_background_task())

    def test_stale_parent_preflight_restores_training_controls(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type(
            "TrainingOwner",
            (MainWindowModelManagementMixin, MainWindowTrainingMixin),
            {},
        )()
        owner.current_lang = "en"
        owner.project = FakeProject(str(ROOT / "new.sqlite_manifest.json"))
        worker = object()
        owner.training_preflight_thread = worker
        owner.training_preflight_dialog = None
        owner.btn_train = FakeButton()
        owner.btn_stop_training = FakeButton()
        owner.parent_training_failed = False
        owner.progress_updates = []
        owner.stale_events = []
        owner._set_training_progress = (
            lambda *args: owner.progress_updates.append(args)
        )
        owner._refresh_blink_refine_state = lambda: None
        owner._log_stale_project_task_result = (
            lambda workflow, _context: owner.stale_events.append(workflow)
        )
        interrupted = []
        run = type(
            "PreparedRun",
            (),
            {
                "status": "running",
                "interrupt": lambda self, **kwargs: interrupted.append(kwargs),
            },
        )()
        prepared = type("Prepared", (), {"run": run})()
        request = {
            "project_context": {
                "project": FakeProject(str(ROOT / "old.sqlite_manifest.json")),
                "project_path": str(ROOT / "old.sqlite_manifest.json"),
            }
        }

        owner._on_parent_preflight_ready(prepared, request, worker)

        self.assertTrue(owner.parent_training_failed)
        self.assertTrue(owner.btn_train.enabled)
        self.assertFalse(owner.btn_stop_training.enabled)
        self.assertEqual(interrupted, [{"stage": "stale_project_context"}])
        self.assertEqual(owner.stale_events, ["parent_training_preflight"])
        self.assertEqual(owner.progress_updates[-1][0], "parent")

    def test_stale_training_error_is_ignored(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowModelManagementMixin, MainWindowTrainingMixin), {})()
        owner.project = FakeProject(str(ROOT / "old.sqlite_manifest.json"))
        owner.parent_training_project_context = owner._capture_project_task_context()
        owner.project.current_project_path = str(ROOT / "new.sqlite_manifest.json")
        stale_events = []
        owner._log_stale_project_task_result = lambda workflow, _context: stale_events.append(workflow)

        owner._on_training_error({"type": "runtime", "message": "old failure"})

        self.assertEqual(stale_events, ["parent_training_error"])

    def test_final_integrity_recovery_retries_once_with_original_configuration(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
        owner.current_lang = "en"
        owner.project = FakeProject(str(ROOT / "project.sqlite_manifest.json"))
        owner.parent_training_project_context = {}
        owner.training_retry_requested = False
        owner.integrity_recovery_retry_used = False
        owner.parent_training_failed = False
        owner.progress = type("Progress", (), {"value": lambda self: 70})()
        owner.pending_training_preflight = {
            "preflight": {"selected_locator_size": (512, 512)},
            "taxonomy": ["Head"],
            "locator_scope": ["Head"],
            "train_segmenter": True,
            "training_scope": {
                "scope_id": "__all__",
                "label": "All Images",
                "images": ["ant.png"],
            },
        }
        owner.trainer = type(
            "Trainer",
            (),
            {
                "training_run": type(
                    "Run", (), {"run_id": "training_run_failed_integrity"}
                )()
            },
        )()
        owner._set_training_progress = lambda *_args: None
        owner.log_messages = []
        owner.log = owner.log_messages.append
        owner._offer_training_integrity_recovery = lambda _message: True
        launched = []
        owner._launch_training_with_preflight = (
            lambda *args, **kwargs: launched.append((args, kwargs))
        )

        with patch(
            "AntSleap.ui.main_window_training.QMessageBox.critical"
        ), patch(
            "AntSleap.ui.main_window_training.QTimer.singleShot",
            side_effect=lambda _delay, callback: callback(),
        ):
            owner._on_training_error(
                {
                    "type": "error",
                    "message": "registry_verified_source_changed",
                }
            )
            owner._on_training_error(
                {
                    "type": "error",
                    "message": "registry_verified_source_changed",
                }
            )

        self.assertTrue(owner.integrity_recovery_retry_used)
        self.assertEqual(len(launched), 1)
        args, kwargs = launched[0]
        self.assertEqual(args[1], ["Head"])
        self.assertEqual(args[2], ["Head"])
        self.assertTrue(args[3])
        self.assertEqual(kwargs["retry_of"], "training_run_failed_integrity")
        self.assertTrue(owner.parent_training_failed)

    def test_preflight_integrity_recovery_keeps_failed_run_id(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
        owner.current_lang = "en"
        owner.btn_train = FakeButton()
        owner.btn_stop_training = FakeButton()
        owner._clear_parent_preflight = lambda _worker: True
        owner._set_training_progress = lambda *_args: None
        owner._offer_training_integrity_recovery = lambda _error: True
        owner._refresh_blink_refine_state = lambda: None
        launched = []
        owner._launch_training_with_preflight = (
            lambda *args, **kwargs: launched.append((args, kwargs))
        )
        request = {
            "preflight": {"selected_locator_size": (512, 512)},
            "taxonomy": ["Head"],
            "locator_scope": ["Head"],
            "train_segmenter": True,
            "training_scope": {"scope_id": "__all__", "images": ["ant.png"]},
        }
        error = RuntimeError("registry_verified_source_changed")
        error.training_run_id = "preflight_failed_run"

        with patch(
            "AntSleap.ui.main_window_training.QMessageBox.critical"
        ), patch(
            "AntSleap.ui.main_window_training.QTimer.singleShot",
            side_effect=lambda _delay, callback: callback(),
        ):
            owner._on_parent_preflight_error(error, request, object())

        self.assertEqual(len(launched), 1)
        self.assertEqual(launched[0][1]["retry_of"], "preflight_failed_run")

    def test_training_recovery_uses_shared_integrity_error_markers(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
        owner.project = FakeProject(str(ROOT / "project.sqlite_manifest.json"))

        class FakeRecovery:
            instances = []

            def __init__(self, *_args, **_kwargs):
                self.report = {"status": "verified"}
                self.exec_calls = 0
                self.instances.append(self)

            def exec(self):
                self.exec_calls += 1

        with patch(
            "AntSleap.ui.main_window_training.TrainingIntegrityRecoveryDialog",
            FakeRecovery,
        ):
            self.assertTrue(owner._offer_training_integrity_recovery("source_read_denied"))
            self.assertTrue(owner._offer_training_integrity_recovery("manual_truth_not_reviewed"))
            self.assertTrue(owner._offer_training_integrity_recovery("runtime_target_outside_root"))
            self.assertFalse(owner._offer_training_integrity_recovery("network_timeout"))

        self.assertEqual(len(FakeRecovery.instances), 3)
        self.assertTrue(all(item.exec_calls == 1 for item in FakeRecovery.instances))

    def test_stale_parent_finished_signal_does_not_clear_replacement_worker(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
        old_worker = object()
        replacement = object()
        owner.trainer = replacement
        owner.btn_train = FakeButton()
        owner.btn_stop_training = FakeButton()
        refreshes = []
        owner._refresh_blink_refine_state = lambda: refreshes.append(True)

        owner._on_training_finished(worker=old_worker)

        self.assertIs(owner.trainer, replacement)
        self.assertIsNone(owner.btn_train.enabled)
        self.assertIsNone(owner.btn_stop_training.enabled)
        self.assertEqual(refreshes, [])

    def test_integrity_retry_keeps_run_id_when_modal_dialog_finishes_worker(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
        owner.current_lang = "en"
        owner.parent_training_project_context = {}
        owner.training_retry_requested = False
        owner.integrity_recovery_retry_used = False
        owner.parent_training_failed = False
        owner.progress = type("Progress", (), {"value": lambda self: 70})()
        owner.pending_training_preflight = {
            "preflight": {"selected_locator_size": (512, 512)},
            "taxonomy": ["Head"],
            "locator_scope": ["Head"],
            "train_segmenter": True,
            "training_scope": {"scope_id": "__all__", "images": ["ant.png"]},
        }
        worker = type(
            "Trainer",
            (),
            {
                "training_run": type(
                    "Run", (), {"run_id": "run_before_modal_finish"}
                )()
            },
        )()
        owner.trainer = worker
        owner._set_training_progress = lambda *_args: None
        owner.log = lambda *_args: None

        def recover(_message):
            owner.trainer = None
            return True

        owner._offer_training_integrity_recovery = recover
        launched = []
        owner._launch_training_with_preflight = (
            lambda *args, **kwargs: launched.append((args, kwargs))
        )

        with patch(
            "AntSleap.ui.main_window_training.QMessageBox.critical"
        ), patch(
            "AntSleap.ui.main_window_training.QTimer.singleShot",
            side_effect=lambda _delay, callback: callback(),
        ):
            owner._on_training_error(
                {"type": "error", "message": "registry_verified_source_changed"},
                worker=worker,
            )

        self.assertEqual(len(launched), 1)
        self.assertEqual(launched[0][1]["retry_of"], "run_before_modal_finish")

    def test_oom_retry_keeps_run_id_when_resolution_dialog_finishes_worker(self):
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowTrainingMixin,), {})()
        owner.parent_training_project_context = {}
        owner.training_retry_requested = False
        owner.parent_training_failed = False
        owner.pending_training_preflight = {
            "preflight": {
                "selected_locator_size": (512, 512),
                "lower_locator_size_options": [(256, 256)],
            },
            "taxonomy": ["Head"],
            "locator_scope": ["Head"],
            "train_segmenter": False,
            "training_scope": {"scope_id": "__all__"},
        }
        worker = type(
            "Trainer",
            (),
            {"training_run": type("Run", (), {"run_id": "oom_run"})()},
        )()
        owner.trainer = worker

        def choose_resolution(*_args):
            owner.trainer = None
            return (256, 256)

        owner._ask_locator_oom_retry_resolution = choose_resolution
        launched = []
        owner._launch_training_with_preflight = (
            lambda *args, **kwargs: launched.append((args, kwargs))
        )

        with patch(
            "AntSleap.ui.main_window_training.QTimer.singleShot",
            side_effect=lambda _delay, callback: callback(),
        ):
            owner._on_training_error(
                {
                    "type": "oom",
                    "stage": "locator",
                    "current_resolution": (512, 512),
                    "lower_options": [(256, 256)],
                },
                worker=worker,
            )

        self.assertEqual(len(launched), 1)
        self.assertEqual(launched[0][1]["retry_of"], "oom_run")


if __name__ == "__main__":
    unittest.main()
