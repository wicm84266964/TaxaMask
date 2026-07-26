import copy
import os
import re
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QProgressDialog

try:
    from AntSleap.app_runtime import runtime_log_event, runtime_log_exception
    from AntSleap.core.path_identity import path_identity
    from AntSleap.ui.main_window_i18n import tr
    from AntSleap.ui.main_window_workers import (
        BatchPanelSplitThread,
        discard_staged_panel_crops,
        promote_staged_panel_crops,
    )
    from AntSleap.ui.style import BUTTON_ROLE_COMMIT, themed_yes_no_question
except ImportError:
    from app_runtime import runtime_log_event, runtime_log_exception
    from core.path_identity import path_identity
    from ui.main_window_i18n import tr
    from ui.main_window_workers import (
        BatchPanelSplitThread,
        discard_staged_panel_crops,
        promote_staged_panel_crops,
    )
    from ui.style import BUTTON_ROLE_COMMIT, themed_yes_no_question


def _panel_split_inventory_identity(path):
    if not path:
        return ""
    # ProjectManager canonicalizes image paths at load/import time. Candidate
    # inventory can therefore stay filesystem-free even for very large projects.
    return os.path.normcase(os.path.abspath(os.path.normpath(str(path))))


class MainWindowPanelSplitMixin:
    def _candidate_panel_split_sources(self):
        images = [path for path in self.project.project_data.get("images", []) if path]
        provenance_items = self.project.project_data.get("image_provenance", {})
        provenance_by_identity = {
            _panel_split_inventory_identity(path): provenance
            for path, provenance in provenance_items.items()
            if path and isinstance(provenance, dict)
        }
        identities_by_location = {}
        image_identity = {}
        for path in images:
            identity = _panel_split_inventory_identity(path)
            image_identity[path] = identity
            directory = _panel_split_inventory_identity(os.path.dirname(str(path)))
            stem = os.path.normcase(os.path.splitext(os.path.basename(str(path)))[0])
            identities_by_location.setdefault((directory, stem), set()).add(identity)

        crop_identities = set()
        completed_source_identities = set()
        for path in images:
            identity = image_identity[path]
            provenance = provenance_by_identity.get(identity, {})
            derived_from = provenance.get("derived_from") if isinstance(provenance, dict) else {}
            parent_path = derived_from.get("image_path") if isinstance(derived_from, dict) else ""
            if parent_path:
                crop_identities.add(identity)
                completed_source_identities.add(path_identity(parent_path))
                continue

            base_name = os.path.basename(str(path))
            if not re.search(r"__(?:panel|crop)_\d{3}(?:_\d+)?\.(?:png|jpe?g|tif|tiff)$", base_name, re.IGNORECASE):
                continue
            crop_stem = os.path.splitext(base_name)[0]
            parent_stem = os.path.normcase(
                re.sub(r"__(?:panel|crop)_\d{3}(?:_\d+)?$", "", crop_stem, flags=re.IGNORECASE)
            )
            directory = _panel_split_inventory_identity(os.path.dirname(str(path)))
            parent_identities = identities_by_location.get((directory, parent_stem), set())
            if parent_identities:
                crop_identities.add(identity)
                completed_source_identities.update(parent_identities)

        terminal_statuses = {
            "auto_split",
            "candidate_split",
            "manual_required",
            "manual_done",
            "skipped",
        }
        sources = []
        seen_source_identities = set()
        for path in images:
            identity = image_identity[path]
            if not identity or identity in seen_source_identities:
                continue
            seen_source_identities.add(identity)
            if identity in crop_identities:
                continue
            provenance = provenance_by_identity.get(identity, {})
            review = provenance.get("panel_split_review") if isinstance(provenance, dict) else {}
            status = str(review.get("status") or "") if isinstance(review, dict) else ""
            rerun_requested = bool(provenance.get("panel_split_rerun_requested")) if isinstance(provenance, dict) else False
            if status == "retryable_error":
                sources.append(path)
                continue
            if identity in completed_source_identities and not rerun_requested:
                continue
            if status in terminal_statuses:
                continue
            sources.append(path)
        return sources

    def batch_split_panel_images(self):
        running_thread = getattr(self, "batch_panel_split_thread", None)
        if running_thread is not None:
            QMessageBox.information(
                self,
                tr("Batch Split Plates", self.current_lang),
                tr("Panel splitting is already running.", self.current_lang),
            )
            return
        active_task = self._active_project_bound_background_task()
        if active_task:
            QMessageBox.information(
                self,
                tr("Project is busy", self.current_lang),
                tr(
                    "{0} is still running. Wait for it to finish before starting panel splitting.",
                    self.current_lang,
                ).format(active_task),
            )
            return
        source_images = self._candidate_panel_split_sources()
        if not source_images:
            QMessageBox.information(
                self,
                tr("Batch Split Plates", self.current_lang),
                tr(
                    "All original images have already been checked for panel splitting. Clear the split status on specific images before running them again.",
                    self.current_lang,
                ),
            )
            return
        reply = themed_yes_no_question(
            self,
            tr("Batch Split Plates", self.current_lang),
            tr(
                "Run automatic panel splitting on {0} original image(s)?\n\nDetected crops will be added after the original images. Please review the generated crops before training.",
                self.current_lang,
            ).format(len(source_images)),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply != QMessageBox.Yes:
            return

        self._flush_pending_project_save(defer_for_navigation=False)
        progress = QProgressDialog(
            tr("Preparing panel splitting...", self.current_lang),
            tr("Cancel", self.current_lang),
            0,
            len(source_images),
            self,
        )
        progress.setWindowTitle(tr("Batch Split Plates", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        self._prepare_progress_dialog(progress)
        progress.show()
        self._set_image_import_controls_enabled(False)

        thread = BatchPanelSplitThread(
            source_images,
            reserved_output_paths=list(self.project.project_data.get("images", []) or []),
            wait_for_result_ack=True,
        )
        task_context = self._capture_project_task_context()
        self.batch_panel_split_thread = thread
        self.batch_panel_split_progress_dialog = progress
        self.batch_panel_split_project_context = task_context
        self.batch_panel_split_state = {
            "thread": thread,
            "context": task_context,
            "progress": progress,
            "processed_results": 0,
            "crop_records": [],
            "pending_crop_records": [],
            "manual_required": 0,
            "skipped": 0,
            "failed": 0,
            "failed_sources": [],
            "checkpoint_pending": 0,
            "pending_source_provenance": {},
            "pending_generated_crop_paths": [],
            "changed": False,
            "cancel_requested": False,
            "apply_error": "",
        }

        progress.canceled.connect(lambda worker=thread: self._cancel_batch_panel_split(worker))
        thread.progress_signal.connect(
            lambda done, total, path, worker=thread: self._on_batch_panel_split_progress(worker, done, total, path)
        )
        thread.image_result_signal.connect(
            lambda result, worker=thread: self._on_batch_panel_split_image_result(worker, result)
        )
        thread.error_signal.connect(
            lambda path, message, worker=thread: self._on_batch_panel_split_error(worker, path, message)
        )
        thread.finished.connect(
            lambda worker=thread: self._finish_batch_panel_split(
                worker,
                getattr(worker, "summary", {}),
            )
        )
        runtime_log_event(
            "batch_panel_split_started",
            project=str(task_context.get("project_path") or ""),
            total=len(source_images),
        )
        thread.start()

    def _batch_panel_split_is_current(self, thread, workflow):
        state = getattr(self, "batch_panel_split_state", {}) or {}
        context = state.get("context") or {}
        if getattr(self, "batch_panel_split_thread", None) is not thread or state.get("thread") is not thread:
            return False
        if not self._project_task_context_matches(context):
            self._log_stale_project_task_result(workflow, context)
            return False
        return True

    def _cancel_batch_panel_split(self, thread):
        if not self._batch_panel_split_is_current(thread, "batch_panel_split_cancel"):
            return
        state = self.batch_panel_split_state
        if state.get("cancel_requested"):
            return
        state["cancel_requested"] = True
        thread.cancel()
        progress = state.get("progress")
        if progress is not None:
            progress.setCancelButton(None)
            progress.setLabelText(tr("Stopping after the current image...", self.current_lang))
            progress.show()
        runtime_log_event("batch_panel_split_cancel_requested")

    def _on_batch_panel_split_progress(self, thread, done, total, source_image):
        if not self._batch_panel_split_is_current(thread, "batch_panel_split_progress"):
            return
        progress = self.batch_panel_split_state.get("progress")
        if progress is None:
            return
        total = max(0, int(total))
        done = max(0, int(done))
        if total > 0 and progress.maximum() != total:
            progress.setRange(0, total)
        if total > 0:
            progress.setValue(min(done, total))
        progress.setLabelText(
            tr("Processing panel images: {0}/{1}\n{2}", self.current_lang).format(
                min(done, total),
                total,
                self._short_progress_path(source_image, limit=72),
            )
        )

    def _on_batch_panel_split_image_result(self, thread, result):
        result = result if isinstance(result, dict) else {}
        raw_crop_records = [
            record for record in list(result.get("crop_records") or []) if isinstance(record, dict)
        ]
        if not self._batch_panel_split_is_current(thread, "batch_panel_split_image_result"):
            discard_staged_panel_crops(raw_crop_records)
            if hasattr(thread, "cancel"):
                thread.cancel()
            if hasattr(thread, "acknowledge_result"):
                thread.acknowledge_result()
            return
        source_image = str(result.get("source_image") or "")
        if not source_image:
            discard_staged_panel_crops(raw_crop_records)
            if hasattr(thread, "acknowledge_result"):
                thread.acknowledge_result()
            return
        state = self.batch_panel_split_state
        detections = list(result.get("detections") or [])
        review_status = str(result.get("review_status") or "skipped")
        review_reason = str(result.get("review_reason") or "no_split_detected")
        crop_records = []

        try:
            source_image = self.project._image_data_key(source_image)
            crop_records = promote_staged_panel_crops(
                raw_crop_records,
                getattr(thread, "reserved_output_identities", None),
            )
            promoted_paths = [
                promoted.get("path")
                for original, promoted in zip(raw_crop_records, crop_records)
                if original.get("staged_path") and promoted.get("path")
            ]
            # Record newly promoted files before touching project metadata so any
            # later exception can remove files that were never committed.
            state["pending_generated_crop_paths"].extend(promoted_paths)
            for record in crop_records:
                record["source_image"] = source_image
            provenance = self.project.project_data.setdefault("image_provenance", {})
            snapshots = state.setdefault("pending_source_provenance", {})
            if source_image not in snapshots:
                snapshots[source_image] = {
                    "existed": source_image in provenance,
                    "value": copy.deepcopy(provenance.get(source_image, {})),
                }
            self._set_panel_split_review(
                source_image,
                review_status,
                reason=review_reason,
                detections=detections,
            )
            if crop_records:
                state["crop_records"].extend(crop_records)
                state["pending_crop_records"].extend(crop_records)
            state["processed_results"] += 1
            state["changed"] = True
            state["checkpoint_pending"] += 1
            if review_status == "candidate_split":
                state["manual_required"] += 1
            if review_status == "skipped":
                state["skipped"] += 1
            if review_status == "retryable_error":
                state["failed"] += 1
                state["failed_sources"].append(source_image)
            runtime_log_event(
                "batch_panel_split_image_finished",
                crop_count=len(crop_records),
                image=os.path.basename(source_image),
                status=review_status,
            )
            if crop_records or state["checkpoint_pending"] >= 25:
                self._save_batch_panel_split_checkpoint(state)
                runtime_log_event(
                    "batch_panel_split_checkpoint_saved",
                    processed=state["processed_results"],
                )
        except Exception as exc:
            state["apply_error"] = str(exc)
            runtime_log_exception("batch_panel_split_project_update_failed", *sys.exc_info())
            discard_staged_panel_crops(raw_crop_records)
            self._rollback_batch_panel_split_checkpoint(state)
            thread.cancel()
        finally:
            if hasattr(thread, "acknowledge_result"):
                thread.acknowledge_result()

    def _save_batch_panel_split_checkpoint(self, state):
        pending_records = list(state.get("pending_crop_records") or [])
        if pending_records:
            self.project.add_images(
                [record.get("path") for record in pending_records if record.get("path")],
                save=False,
            )
            self._inherit_crop_provenance(pending_records, save=False)
        self.project.save_project()
        state["pending_crop_records"] = []
        state["pending_source_provenance"] = {}
        state["pending_generated_crop_paths"] = []
        state["checkpoint_pending"] = 0

    def _rollback_batch_panel_split_checkpoint(self, state):
        generated_paths = [
            str(path) for path in list(state.get("pending_generated_crop_paths") or []) if path
        ]
        generated_identities = {
            identity for identity in (path_identity(path) for path in generated_paths) if identity
        }
        project_data = self.project.project_data
        if generated_identities:
            project_data["images"] = [
                path
                for path in list(project_data.get("images", []) or [])
                if path_identity(path) not in generated_identities
            ]
            for key in ("image_uids", "labels", "scales", "image_provenance"):
                mapping = project_data.get(key)
                if not isinstance(mapping, dict):
                    continue
                for stored_path in list(mapping):
                    if path_identity(stored_path) in generated_identities:
                        del mapping[stored_path]

        provenance = project_data.setdefault("image_provenance", {})
        for source_image, snapshot in dict(state.get("pending_source_provenance") or {}).items():
            if snapshot.get("existed"):
                provenance[source_image] = copy.deepcopy(snapshot.get("value") or {})
            else:
                provenance.pop(source_image, None)

        for attribute in ("_sqlite_dirty_images", "_sqlite_label_dirty_images"):
            dirty_paths = getattr(self.project, attribute, None)
            if not isinstance(dirty_paths, set):
                continue
            for dirty_path in list(dirty_paths):
                if path_identity(dirty_path) in generated_identities:
                    dirty_paths.discard(dirty_path)

        for path in generated_paths:
            try:
                if os.path.isfile(path):
                    os.unlink(path)
            except OSError:
                runtime_log_exception("batch_panel_split_rollback_file_failed", *sys.exc_info())

        if generated_identities:
            state["crop_records"] = [
                record
                for record in list(state.get("crop_records") or [])
                if path_identity(record.get("path")) not in generated_identities
            ]
        state["pending_crop_records"] = []
        state["pending_source_provenance"] = {}
        state["pending_generated_crop_paths"] = []
        state["checkpoint_pending"] = 0

    def _on_batch_panel_split_error(self, thread, source_image, message):
        if not self._batch_panel_split_is_current(thread, "batch_panel_split_error"):
            return
        label = os.path.basename(str(source_image or "")) or tr("Batch Split Plates", self.current_lang)
        self.log(f"Panel split will retry {label}: {message}")
        runtime_log_event(
            "batch_panel_split_image_failed",
            image=label,
            error=str(message or ""),
        )

    def _finish_batch_panel_split(self, thread, summary):
        state = getattr(self, "batch_panel_split_state", {}) or {}
        if getattr(self, "batch_panel_split_thread", None) is not thread or state.get("thread") is not thread:
            return
        context = state.get("context") or {}
        context_matches = self._project_task_context_matches(context)
        summary = summary if isinstance(summary, dict) else {}
        save_error = str(state.get("apply_error") or summary.get("fatal_error") or "")
        if context_matches and save_error:
            self._rollback_batch_panel_split_checkpoint(state)
        elif context_matches and state.get("changed"):
            try:
                self._save_batch_panel_split_checkpoint(state)
            except Exception as exc:
                save_error = str(exc)
                runtime_log_exception("batch_panel_split_final_save_failed", *sys.exc_info())
                self._rollback_batch_panel_split_checkpoint(state)
        elif not context_matches:
            self._log_stale_project_task_result("batch_panel_split_finished", context)

        progress = state.get("progress")
        if progress is not None:
            try:
                progress.canceled.disconnect()
            except (RuntimeError, TypeError):
                pass
            progress.close()
            progress.deleteLater()
        if getattr(self, "batch_panel_split_progress_dialog", None) is progress:
            self.batch_panel_split_progress_dialog = None
        if getattr(self, "batch_panel_split_thread", None) is thread:
            self.batch_panel_split_thread = None
        self.batch_panel_split_project_context = {}
        self.batch_panel_split_state = {}
        if hasattr(thread, "deleteLater"):
            thread.deleteLater()
        self._set_image_import_controls_enabled(True)

        if not context_matches:
            return
        self.refresh_file_list()
        crop_records = list(state.get("crop_records") or [])
        crop_count = len(crop_records)
        source_count = len({record.get("source_image") for record in crop_records if record.get("source_image")})
        manual_required = int(state.get("manual_required") or 0)
        skipped = int(state.get("skipped") or 0)
        failed = int(state.get("failed") or summary.get("failed") or 0)
        cancelled = bool(summary.get("cancelled") or state.get("cancel_requested"))
        processed = int(summary.get("processed", state.get("processed_results", 0)) or 0)
        total = int(summary.get("total", processed) or processed)
        runtime_log_event(
            "batch_panel_split_finished",
            cancelled=cancelled,
            crop_count=crop_count,
            processed=processed,
            skipped=skipped,
            failed=failed,
            total=total,
        )

        if save_error:
            QMessageBox.critical(
                self,
                tr("Batch Split Plates", self.current_lang),
                tr("Panel splitting stopped because project results could not be saved: {0}", self.current_lang).format(save_error),
            )
            return
        if not crop_records and not manual_required and not cancelled and not failed:
            QMessageBox.information(
                self,
                tr("Batch Split Plates", self.current_lang),
                tr("No panel crops were detected.", self.current_lang),
            )
            return

        message = tr(
            "Panel splitting finished: {0} crop(s) from {1} image(s); hard-joined candidate plates needing review: {2}; no split detected: {3}; retryable failures: {4}.",
            self.current_lang,
        ).format(crop_count, source_count, manual_required, skipped, failed)
        if failed:
            failed_names = [os.path.basename(path) for path in list(state.get("failed_sources") or [])[:5]]
            message += "\n" + tr(
                "Failed files remain eligible for the next run: {0}",
                self.current_lang,
            ).format(", ".join(failed_names))
        if cancelled:
            message = (
                f"{message}\n"
                + tr("Panel splitting stopped after {0}/{1} image(s).", self.current_lang).format(processed, total)
            )
        QMessageBox.information(self, tr("Batch Split Plates", self.current_lang), message)


__all__ = ["MainWindowPanelSplitMixin"]
