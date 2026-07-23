from __future__ import annotations

import os
import re
import secrets
import sys
import tempfile
import time

import torch
from PySide6.QtCore import QThread, Signal
from torch.utils.data import DataLoader

try:
    from AntSleap.app_runtime import runtime_log_event, runtime_log_exception
    from AntSleap.core.dataset import TwoStageDataset
    from AntSleap.core.external_backend import ExternalBackendRunner, sanitize_external_backend_config
    from AntSleap.core.training_preflight import format_size_pair
    from AntSleap.core.training_weight_publisher import TrainingWeightPublisher
    from AntSleap.core.vlm_preannotation import (
        VLM_PREANNOTATION_SCHEMA_VERSION,
        run_vlm_preannotation,
        sanitize_vlm_prompt_profile,
    )
except ImportError:
    from app_runtime import runtime_log_event, runtime_log_exception
    from core.dataset import TwoStageDataset
    from core.external_backend import ExternalBackendRunner, sanitize_external_backend_config
    from core.training_preflight import format_size_pair
    from core.training_weight_publisher import TrainingWeightPublisher
    from core.vlm_preannotation import VLM_PREANNOTATION_SCHEMA_VERSION, run_vlm_preannotation, sanitize_vlm_prompt_profile


def _identity_translate(text, _lang="en"):
    return text


class InferenceThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    result_signal = Signal(str, dict)
    error_signal = Signal(str, str)
    finished_signal = Signal()

    def __init__(self, engine, img_paths, taxonomy, locator_scope, inf_params, project_route_manifest=None, model_profile_context=None, lang="en", translate=None):
        super().__init__()
        self.engine = engine
        self.img_paths = img_paths
        self.taxonomy = taxonomy
        self.locator_scope = locator_scope
        self.inf_params = inf_params
        self.project_route_manifest = dict(project_route_manifest or {})
        self.model_profile_context = dict(model_profile_context or {})
        self.prediction_batch_id = f"batch_{secrets.token_hex(6)}"
        self.lang = lang
        self.translate = translate or _identity_translate

    def run(self):
        self.log_signal.emit(self.translate("Starting batch inference on {0} images...", self.lang).format(len(self.img_paths)))
        count = 0
        try:
            for index, img_path in enumerate(self.img_paths, start=1):
                prediction_context = dict(self.model_profile_context)
                prediction_context["prediction_run_id"] = (
                    f"{self.prediction_batch_id}_{index:06d}"
                )
                try:
                    preds = self.engine.predict_full_pipeline(
                        img_path,
                        current_taxonomy=self.taxonomy,
                        locator_scope=self.locator_scope,
                        conf_thresh=self.inf_params["conf"],
                        adapt_thresh=self.inf_params["adapt"],
                        box_pad=self.inf_params["pad"],
                        noise_floor=self.inf_params["noise_floor"],
                        poly_epsilon=self.inf_params["poly_epsilon"],
                        project_route_manifest=self.project_route_manifest,
                        model_profile_context=prediction_context,
                    )
                except Exception as exc:
                    self.error_signal.emit(str(img_path), str(exc))
                    break
                if preds:
                    self.result_signal.emit(img_path, preds)
                    self.log_signal.emit(self.translate("Processed {0}", self.lang).format(os.path.basename(img_path)))
                count += 1
                self.progress_signal.emit(int(count / len(self.img_paths) * 100))
        finally:
            self.finished_signal.emit()


class VlmPreannotationThread(QThread):
    log_signal = Signal(str)
    image_result_signal = Signal(dict)
    progress_signal = Signal(int, int, str)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, image_path, target_parts, artifacts_dir, api_config, run_id, grid_cols=None, grid_rows=None, min_confidence=0.25, prompt_profile=None):
        super().__init__()
        self.image_path = image_path
        self.target_parts = list(target_parts or [])
        self.artifacts_dir = artifacts_dir
        self.api_config = dict(api_config or {})
        self.run_id = str(run_id or time.strftime("%Y%m%d_%H%M%S"))
        self.grid_cols = int(grid_cols) if grid_cols else None
        self.grid_rows = int(grid_rows) if grid_rows else None
        self.min_confidence = float(min_confidence)
        self.prompt_profile = sanitize_vlm_prompt_profile(prompt_profile)

    def run(self):
        def mark_step(step_name):
            self.progress_signal.emit(1, 1, str(step_name))

        try:
            runtime_log_event("vlm_worker_run_begin", image=os.path.basename(str(self.image_path)), run_id=self.run_id, target_count=len(self.target_parts))
            self.log_signal.emit(f"VLM first-mile preannotation started: {os.path.basename(self.image_path)}")
            result = run_vlm_preannotation(
                self.image_path,
                self.target_parts,
                self.artifacts_dir,
                api_config=self.api_config,
                grid_cols=self.grid_cols,
                grid_rows=self.grid_rows,
                min_confidence=self.min_confidence,
                prompt_profile=self.prompt_profile,
                run_id=self.run_id,
                progress_callback=mark_step,
            )
            runtime_log_event("vlm_worker_run_ok", image=os.path.basename(str(self.image_path)), run_id=self.run_id, candidate_count=len(result.get("candidates", []) or []), report=result.get("report_path", ""))
            self.image_result_signal.emit(result)
        except Exception as exc:
            message = str(exc)
            runtime_log_exception("vlm_worker_run_failed", *sys.exc_info())
            report_match = re.search(r"report=([^;]+)$", message)
            raw_match = re.search(r"raw_response=([^;]+);", message)
            self.image_result_signal.emit(
                {
                    "schema_version": VLM_PREANNOTATION_SCHEMA_VERSION,
                    "status": "failed",
                    "image_path": self.image_path,
                    "target_parts": self.target_parts,
                    "candidates": [],
                    "rejected": [{"part": "", "reason": message}],
                    "error": message,
                    "raw_response_path": raw_match.group(1).strip() if raw_match else "",
                    "report_path": report_match.group(1).strip() if report_match else "",
                }
            )
        finally:
            runtime_log_event("vlm_worker_run_end", image=os.path.basename(str(self.image_path)), run_id=self.run_id)
            self.finished_signal.emit()


class DatasetExportThread(QThread):
    progress_signal = Signal(int, int, str)
    success_signal = Signal(int, str, str)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, project, output_dir, export_format, lang="en"):
        super().__init__()
        self.project = project
        self.output_dir = output_dir
        self.export_format = export_format
        self.lang = lang

    def run(self):
        def progress(done, total, label):
            self.progress_signal.emit(int(done), int(total), str(label or ""))

        try:
            if self.export_format == "multimodal":
                count = self.project.export_multimodal_dataset(self.output_dir, progress_callback=progress)
            elif self.export_format == "coco":
                count = self.project.export_coco(self.output_dir, progress_callback=progress)
            else:
                count = self.project.export_yolo(self.output_dir, progress_callback=progress)
            if hasattr(self.project, "write_model_profile_export_summary"):
                self.project.write_model_profile_export_summary(self.output_dir, export_format=self.export_format)
            self.success_signal.emit(int(count), self.output_dir, self.export_format)
        except Exception as exc:
            self.error_signal.emit(str(exc))
        finally:
            self.finished_signal.emit()


class ImageImportThread(QThread):
    progress_signal = Signal(int, int, str)
    success_signal = Signal(int, int)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, project, image_paths):
        super().__init__()
        self.project = project
        self.image_paths = list(image_paths or [])

    def run(self):
        def progress(done, total, label):
            self.progress_signal.emit(int(done), int(total), str(label or ""))

        try:
            added = self.project.add_images(self.image_paths, progress_callback=progress)
            self.success_signal.emit(int(added), len(self.image_paths))
        except Exception as exc:
            self.error_signal.emit(str(exc))
        finally:
            self.finished_signal.emit()


class ExternalBatchInferenceThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int, int, str)
    result_signal = Signal(str, dict)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, project, backend_config, image_paths, model_manifest="", lang="en", translate=None):
        super().__init__()
        self.project = project
        self.backend_config = sanitize_external_backend_config(backend_config)
        self.image_paths = list(image_paths or [])
        self.model_manifest = str(model_manifest or "")
        self.lang = lang
        self.translate = translate or _identity_translate

    def run(self):
        total = len(self.image_paths)
        self.log_signal.emit(self.translate("Starting batch inference on {0} images...", self.lang).format(total))
        runner = ExternalBackendRunner(self.project, self.backend_config)
        for index, image_path in enumerate(self.image_paths, start=1):
            try:
                self.progress_signal.emit(index - 1, total, str(image_path))
                result = runner.run_predict(image_path, model_manifest=self.model_manifest)
                self.result_signal.emit(str(image_path), result)
                self.log_signal.emit(self.translate("Processed {0}", self.lang).format(os.path.basename(str(image_path))))
                self.progress_signal.emit(index, total, str(image_path))
            except Exception as exc:
                self.error_signal.emit(str(exc))
                break
        self.finished_signal.emit()


class ExternalTrainingThread(QThread):
    log_signal = Signal(str)
    success_signal = Signal(dict)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, project, backend_config):
        super().__init__()
        self.project = project
        self.backend_config = sanitize_external_backend_config(backend_config)

    def run(self):
        try:
            self.log_signal.emit("External backend training started.")
            summary = ExternalBackendRunner(self.project, self.backend_config).run_prepare_and_train()
            self.success_signal.emit(dict(summary or {}))
        except Exception as exc:
            self.error_signal.emit(str(exc))
        finally:
            self.finished_signal.emit()


class TrainingThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    report_signal = Signal(dict)
    success_signal = Signal()
    error_signal = Signal(dict)
    finished_signal = Signal()

    def __init__(self, engine, preflight, taxonomy, locator_scope, epochs=5, batch_size=4, lang="en", train_segmenter=True, training_context=None, translate=None, training_run=None, model_output_root=None):
        super().__init__()
        self.engine = engine
        self.preflight = dict(preflight or {})
        self.taxonomy = taxonomy
        self.locator_scope = locator_scope
        self.epochs = epochs
        self.batch_size = batch_size
        self.lang = lang
        self.translate = translate or _identity_translate
        self.train_segmenter = bool(train_segmenter)
        self.training_context = dict(training_context or {})
        self.locator_train_data = list(self.preflight.get("locator_train_data", []))
        self.locator_val_data = list(self.preflight.get("locator_val_data", []))
        self.parts_train_data = list(self.preflight.get("parts_train_data", []))
        self.parts_val_data = list(self.preflight.get("parts_val_data", []))
        self.locator_resolution = tuple(self.preflight.get("selected_locator_size") or (512, 512))
        self.has_locator_stage = bool(self.locator_train_data and self.locator_val_data)
        self.has_parts_stage = bool(self.train_segmenter and self.parts_train_data and self.parts_val_data)
        self.saved_weights_timestamp = None
        self.training_run = training_run
        self.model_output_root = os.path.abspath(
            model_output_root or getattr(engine, "weights_dir", "")
        )

    def _run_active(self):
        return self.training_run is not None and self.training_run.status in {
            "pending",
            "running",
        }

    def _cancel_run(self):
        if self._run_active():
            self.training_run.cancel(stage="training")

    def _fail_run(self, exc):
        if self._run_active():
            self.training_run.fail(exc, stage="training")

    def _publish_weights(self):
        run = self.training_run
        if run is None:
            return self.engine.save_weights(
                save_locator=self.has_locator_stage,
                save_segmenter=self.has_parts_stage,
            )
        publisher = TrainingWeightPublisher(self.model_output_root)
        specs = []
        if self.has_locator_stage:
            specs.append(
                {
                    "artifact_id": "locator_checkpoint",
                    "role": "output_weights",
                    "relative_path": f"locator_{run.run_id}.pth",
                    "media_type": "application/octet-stream",
                }
            )
        if self.has_parts_stage:
            specs.append(
                {
                    "artifact_id": "sam_decoder_checkpoint",
                    "role": "output_weights",
                    "relative_path": f"sam_decoder_lora_{run.run_id}.pth",
                    "media_type": "application/octet-stream",
                }
            )
        output_root = os.path.join(run.run_dir, "outputs")
        os.makedirs(output_root, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".weight-staging-", dir=output_root
        ) as staging_dir:
            self.engine.save_weights(
                save_locator=self.has_locator_stage,
                save_segmenter=self.has_parts_stage,
                output_dir=staging_dir,
                artifact_key=run.run_id,
            )
            publication = publisher.publish_pending(run.run_id, staging_dir, specs)
        run.register_path_base("managed_model_root", self.model_output_root)
        for artifact in publication.get("artifacts", []):
            path = os.path.join(
                self.model_output_root,
                *artifact["relative_path"].split("/"),
            )
            observed = run.add_artifact(
                artifact_id=artifact["artifact_id"],
                role="output_weights",
                path=path,
                path_base="managed_model_root",
                media_type=artifact["media_type"],
            )
            if observed.get("digest") != artifact.get("digest"):
                raise ValueError("published_weight_artifact_mismatch")
        return run.run_id, publisher

    def _tr(self, text):
        return self.translate(text, self.lang)

    def run(self):
        try:
            self.log_signal.emit("Starting training on active compute device...")
            self.engine.locator_resolution = tuple(self.locator_resolution)
            self.log_signal.emit(self._tr("Locator training size set to {0}").format(format_size_pair(self.engine.locator_resolution)))
            self.engine.history["locator_train"] = []
            self.engine.history["locator_val"] = []
            self.engine.history["pixel_error"] = []
            self.engine.history["parts_train"] = []
            self.engine.history["parts_val"] = []
            self.engine.history["iou"] = []
            dl_loc_val = None

            if self.has_locator_stage:
                locator = self.engine.ensure_locator_loaded()
                opt_loc = self.engine.opt_loc
                ds_loc_train = TwoStageDataset(self.locator_train_data, self.locator_scope, mode="locator", input_size=tuple(self.engine.locator_resolution))
                ds_loc_val = TwoStageDataset(self.locator_val_data, self.locator_scope, mode="locator", input_size=tuple(self.engine.locator_resolution))
                dl_loc_train = DataLoader(ds_loc_train, batch_size=max(1, self.batch_size * 2), shuffle=True)
                dl_loc_val = DataLoader(ds_loc_val, batch_size=max(1, self.batch_size * 2), shuffle=False)
                self.log_signal.emit("Training Locator...")
                try:
                    for epoch in range(self.epochs):
                        if self.isInterruptionRequested():
                            self.log_signal.emit(self._tr("Training cancelled."))
                            self._cancel_run()
                            return
                        loss_t = self.engine.train_epoch(dl_loc_train, locator, opt_loc, None, stop_callback=self.isInterruptionRequested)
                        if loss_t is None or self.isInterruptionRequested():
                            self.log_signal.emit(self._tr("Training cancelled."))
                            self._cancel_run()
                            return
                        metrics_v = self.engine.validate_epoch(dl_loc_val, locator, stop_callback=self.isInterruptionRequested)
                        if metrics_v is None:
                            self.log_signal.emit(self._tr("Training cancelled."))
                            self._cancel_run()
                            return
                        self.engine.history["locator_train"].append(loss_t)
                        self.engine.history["locator_val"].append(metrics_v["loss"])
                        self.engine.history["pixel_error"].append(metrics_v["pixel_error"])
                        self.log_signal.emit(self._tr("Loc Ep {0}: Train {1:.4f} | Val {2:.4f} | Err {3:.1f}px").format(epoch, loss_t, metrics_v["loss"], metrics_v["pixel_error"]))
                        self.progress_signal.emit(int((epoch + 1) / (self.epochs * 2) * 100))
                except RuntimeError as exc:
                    if "out of memory" in str(exc).lower():
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        self._fail_run(exc)
                        self.error_signal.emit({"type": "oom", "stage": "locator", "current_resolution": tuple(self.engine.locator_resolution), "lower_options": list(self.preflight.get("lower_locator_size_options", [])), "message": str(exc)})
                        return
                    raise
            else:
                self.log_signal.emit(self._tr("Locator stage skipped: no eligible locator samples."))
                self.progress_signal.emit(50)

            if self.has_parts_stage:
                ds_parts_train = TwoStageDataset(self.parts_train_data, self.taxonomy, mode="parts")
                ds_parts_val = TwoStageDataset(self.parts_val_data, self.taxonomy, mode="parts")
                dl_parts_train = DataLoader(ds_parts_train, batch_size=1, shuffle=True)
                dl_parts_val = DataLoader(ds_parts_val, batch_size=1, shuffle=False)
                parts_model = self.engine.ensure_parts_model_loaded()
                opt_parts = self.engine.opt_parts
                self.log_signal.emit(self._tr("Training SAM... (BS=1)"))
                for epoch in range(self.epochs):
                    if self.isInterruptionRequested():
                        self.log_signal.emit(self._tr("Training cancelled."))
                        self._cancel_run()
                        return
                    loss_t = self.engine.train_epoch(dl_parts_train, parts_model, opt_parts, self.engine.crit_parts, stop_callback=self.isInterruptionRequested)
                    if loss_t is None or self.isInterruptionRequested():
                        self.log_signal.emit(self._tr("Training cancelled."))
                        self._cancel_run()
                        return
                    metrics_v = self.engine.validate_epoch(dl_parts_val, parts_model, stop_callback=self.isInterruptionRequested)
                    if metrics_v is None:
                        self.log_signal.emit(self._tr("Training cancelled."))
                        self._cancel_run()
                        return
                    self.engine.history["parts_train"].append(loss_t)
                    self.engine.history["parts_val"].append(metrics_v["loss"])
                    self.engine.history["iou"].append(metrics_v["iou"])
                    self.log_signal.emit(self._tr("SAM Ep {0}: Train {1:.4f} | Val {2:.4f} | IoU {3:.2%}").format(epoch, loss_t, metrics_v["loss"], metrics_v["iou"]))
                    self.progress_signal.emit(50 + int((epoch + 1) / (self.epochs * 2) * 100))
            else:
                message = "SAM stage skipped: no eligible SAM/parts samples." if self.train_segmenter else "SAM stage skipped: locator-only training is enabled."
                self.log_signal.emit(self._tr(message))
                self.progress_signal.emit(100)

            if self.isInterruptionRequested():
                self.log_signal.emit(self._tr("Training cancelled."))
                self._cancel_run()
                return
            publication = self._publish_weights()
            publisher = None
            if self.training_run is None:
                self.saved_weights_timestamp = publication
            else:
                self.saved_weights_timestamp, publisher = publication
            if self.saved_weights_timestamp:
                self.training_context["saved_weights_timestamp"] = self.saved_weights_timestamp
                if self.training_run is None:
                    self.training_context["locator_weights"] = f"locator_{self.saved_weights_timestamp}.pth" if self.has_locator_stage else ""
                    self.training_context["segmenter_weights"] = f"sam_decoder_lora_{self.saved_weights_timestamp}.pth" if self.has_parts_stage else ""
                else:
                    bundle = f"training_runs/{self.training_run.run_id}"
                    self.training_context["locator_weights"] = f"{bundle}/locator_{self.training_run.run_id}.pth" if self.has_locator_stage else ""
                    self.training_context["segmenter_weights"] = f"{bundle}/sam_decoder_lora_{self.training_run.run_id}.pth" if self.has_parts_stage else ""
            self.log_signal.emit(self._tr("Generating Report..."))
            report = self.engine.generate_report(dl_loc_val, num_samples=6, training_context=self.training_context)
            if self.training_run is not None:
                report_dir = str(report.get("dir") or "")
                if report_dir and os.path.isdir(report_dir):
                    self.training_run.register_path_base(
                        "export_root", os.path.dirname(report_dir)
                    )
                    self.training_run.add_artifact(
                        artifact_id="training_report",
                        role="training_report",
                        path=report_dir,
                        path_base="export_root",
                        media_type="application/x-directory",
                    )
                successful = self.training_run.succeed()
                try:
                    publisher.activate(self.training_run.run_id, successful)
                    self.training_context["weight_publication_status"] = "active"
                except Exception:
                    self.training_context["weight_publication_status"] = "pending_recovery"
            self.report_signal.emit(report)
            self.log_signal.emit(self._tr("Training Finished! All validation results saved to {0}/val_details").format(report["dir"]))
            self.success_signal.emit()
        except Exception as exc:
            self._fail_run(exc)
            self.error_signal.emit({"type": "error", "message": str(exc)})
        finally:
            self.finished_signal.emit()
