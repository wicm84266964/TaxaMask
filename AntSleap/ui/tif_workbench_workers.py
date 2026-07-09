import os
import time

import numpy as np
from PySide6.QtCore import QObject, Signal

try:
    from AntSleap.core.tif_backend import TifBackendRunner
    from AntSleap.core.tif_part_extraction import build_preview_mask_from_contours, crop_volume_to_part
    from AntSleap.core.tif_roi_preview import DEFAULT_ROI_TEXTURE_BUDGET_BYTES, build_roi_mask_preview, build_roi_volume_preview
    from AntSleap.core.tif_stack_import import import_tif_stack, materialize_registered_tif_stack, register_tif_stack_metadata
    from AntSleap.core.tif_volume_io import flush_volume_array, load_volume_sidecar
    from AntSleap.core.tif_volume_preview import build_mask_preview, build_volume_preview
    from AntSleap.core.tif_local_axis_reslice import export_part_reslice
    from AntSleap.ui.tif_gpu_volume_canvas import GPU_VOLUME_MAX_TEXTURE_DIM
    from AntSleap.ui.tif_workbench_helpers import (
        _tif_initialize_part_mask_from_full_volume_contours,
        _tif_initialize_part_mask_from_roi_shell,
    )
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_backend import TifBackendRunner
    from core.tif_part_extraction import build_preview_mask_from_contours, crop_volume_to_part
    from core.tif_roi_preview import DEFAULT_ROI_TEXTURE_BUDGET_BYTES, build_roi_mask_preview, build_roi_volume_preview
    from core.tif_stack_import import import_tif_stack, materialize_registered_tif_stack, register_tif_stack_metadata
    from core.tif_volume_io import flush_volume_array, load_volume_sidecar
    from core.tif_volume_preview import build_mask_preview, build_volume_preview
    from core.tif_local_axis_reslice import export_part_reslice
    from ui.tif_gpu_volume_canvas import GPU_VOLUME_MAX_TEXTURE_DIM
    from ui.tif_workbench_helpers import (
        _tif_initialize_part_mask_from_full_volume_contours,
        _tif_initialize_part_mask_from_roi_shell,
    )


class TifImportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, project_manager, tif_path, specimen_id):
        super().__init__()
        self.project_manager = project_manager
        self.tif_path = tif_path
        self.specimen_id = specimen_id

    def run(self):
        try:
            result = import_tif_stack(
                self.project_manager,
                self.tif_path,
                self.specimen_id,
                copy_source=False,
                create_working_edit=False,
                progress_callback=self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class TifBatchImportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)

    def __init__(self, project_manager, jobs):
        super().__init__()
        self.project_manager = project_manager
        self.jobs = [dict(job or {}) for job in jobs]

    def run(self):
        results = []
        total_jobs = max(1, len(self.jobs))
        for job_index, job in enumerate(self.jobs):
            tif_path = str(job.get("tif_path") or "")
            specimen_id = str(job.get("specimen_id") or "")
            base_progress = job_index * 100

            def emit_job_progress(current, total, message):
                total = max(1, int(total or 100))
                current = max(0, min(total, int(current or 0)))
                normalized = int(round((current / float(total)) * 100.0))
                self.progress.emit(base_progress + normalized, total_jobs * 100, f"{job_index + 1}/{total_jobs} {message}")

            try:
                emit_job_progress(0, 100, f"Importing {os.path.basename(tif_path)}")
                result = register_tif_stack_metadata(
                    self.project_manager,
                    tif_path,
                    specimen_id,
                    progress_callback=emit_job_progress,
                )
                results.append(
                    {
                        "ok": True,
                        "tif_path": tif_path,
                        "specimen_id": specimen_id,
                        "result": result,
                        "report_path": result.get("report_path", "") if isinstance(result, dict) else "",
                    }
                )
            except Exception as exc:
                if specimen_id:
                    try:
                        self.project_manager.discard_specimen_scaffold(specimen_id, save=False)
                    except Exception:
                        pass
                results.append(
                    {
                        "ok": False,
                        "tif_path": tif_path,
                        "specimen_id": specimen_id,
                        "error": str(exc),
                    }
                )
        self.progress.emit(total_jobs * 100, total_jobs * 100, "Finalizing TIF batch import")
        self.finished.emit({"results": results})


class TifMaterializeWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, project_manager, specimen_id):
        super().__init__()
        self.project_manager = project_manager
        self.specimen_id = str(specimen_id or "")

    def run(self):
        specimen = self.project_manager.get_specimen(self.specimen_id, default=None)
        if specimen is None:
            self.failed.emit(f"unknown_specimen:{self.specimen_id}")
            return
        source_path = str((specimen.get("metadata") or {}).get("source_tif") or (specimen.get("source") or {}).get("raw_tif") or "")
        if not source_path:
            self.failed.emit(f"metadata_only_source_missing:{self.specimen_id}")
            return
        metadata_snapshot = dict(specimen.get("metadata") or {})
        try:
            result = materialize_registered_tif_stack(
                self.project_manager,
                self.specimen_id,
                progress_callback=self.progress.emit,
            )
            restored = self.project_manager.get_specimen(self.specimen_id, default=None)
            if restored is not None:
                restored.setdefault("metadata", {}).update(
                    {
                        key: value
                        for key, value in metadata_snapshot.items()
                        if key not in {"import_status"}
                    }
                )
                restored.setdefault("metadata", {})["import_status"] = "materialized"
                self.project_manager.save_project()
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.progress.emit(100, 100, "Working volume ready")
        self.finished.emit(result)


class TifVolumePreviewBuildWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, token, volume=None, volume_request=None, mask=None, mask_request=None):
        super().__init__()
        self.token = int(token)
        self.volume = volume
        self.volume_request = dict(volume_request or {})
        self.mask = mask
        self.mask_request = dict(mask_request or {})
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        result = {
            "token": self.token,
            "cancelled": False,
            "preview": None,
            "mask_preview": None,
            "volume_request": dict(self.volume_request),
            "mask_request": dict(self.mask_request),
            "build_ms": 0.0,
        }
        started = time.perf_counter()
        try:
            if self.volume_request and self.volume is not None:
                self.progress.emit(str(self.volume_request.get("message") or "Preparing full-volume 3D preview..."))
                if self._cancelled:
                    result["cancelled"] = True
                    self.finished.emit(result)
                    return
                roi_bbox = self.volume_request.get("roi_bbox")
                if roi_bbox is not None:
                    preview = build_roi_volume_preview(
                        self.volume,
                        roi_bbox,
                        int(self.volume_request.get("max_dim", 1024)),
                        mode=str(self.volume_request.get("algorithm", "hybrid")),
                        preserve_source=bool(self.volume_request.get("preserve_source", False)),
                        texture_budget_bytes=int(self.volume_request.get("texture_budget_bytes", DEFAULT_ROI_TEXTURE_BUDGET_BYTES)),
                        max_texture_dim=GPU_VOLUME_MAX_TEXTURE_DIM,
                    )
                else:
                    preview = build_volume_preview(
                        self.volume,
                        int(self.volume_request.get("max_dim", 1024)),
                        mode=str(self.volume_request.get("algorithm", "hybrid")),
                        preserve_source=bool(self.volume_request.get("preserve_source", False)),
                    )
                result["preview"] = preview
            if self.mask_request and self.mask is not None:
                self.progress.emit(str(self.mask_request.get("message") or "Preparing mask preview..."))
                if self._cancelled:
                    result["cancelled"] = True
                    self.finished.emit(result)
                    return
                roi_bbox = self.mask_request.get("roi_bbox")
                if roi_bbox is not None:
                    mask_preview = build_roi_mask_preview(
                        self.mask,
                        roi_bbox,
                        int(self.mask_request.get("max_dim", 1024)),
                        mode=str(self.mask_request.get("algorithm", "occupancy")),
                        max_texture_dim=GPU_VOLUME_MAX_TEXTURE_DIM,
                    )
                else:
                    mask_preview = build_mask_preview(
                        self.mask,
                        int(self.mask_request.get("max_dim", 1024)),
                        mode=str(self.mask_request.get("algorithm", "occupancy")),
                    )
                result["mask_preview"] = mask_preview
            result["cancelled"] = bool(self._cancelled)
            result["build_ms"] = max(0.0, (time.perf_counter() - started) * 1000.0)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit({"token": self.token, "error": str(exc)})


class TifPartMaskPreviewWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, token, contours, shape_zyx, context=None):
        super().__init__()
        self.token = int(token)
        self.contours = dict(contours or {})
        self.shape_zyx = tuple(int(value) for value in (shape_zyx or ()))
        self.context = dict(context or {})
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        started = time.perf_counter()
        try:
            self.progress.emit(0, 0, "Preview auto fill is running...")
            if self._cancelled:
                self.finished.emit({"token": self.token, "cancelled": True, "context": self.context})
                return
            mask = build_preview_mask_from_contours(self.contours, self.shape_zyx)
            self.progress.emit(100, 100, "Preview auto fill finished")
            self.finished.emit(
                {
                    "token": self.token,
                    "cancelled": bool(self._cancelled),
                    "mask": mask,
                    "contours": self.contours,
                    "shape_zyx": self.shape_zyx,
                    "context": self.context,
                    "build_ms": max(0.0, (time.perf_counter() - started) * 1000.0),
                }
            )
        except Exception as exc:
            self.failed.emit({"token": self.token, "error": str(exc), "context": self.context})


class TifLabelAutoSaveWorker(QObject):
    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, token, edit_path, slices, slice_revisions):
        super().__init__()
        self.token = int(token)
        self.edit_path = str(edit_path or "")
        self.slices = {int(key): np.asarray(value).copy() for key, value in (slices or {}).items()}
        self.slice_revisions = {int(key): int(value) for key, value in (slice_revisions or {}).items()}
        self.last_result = None
        self.last_error = None

    def run(self):
        try:
            if not self.edit_path:
                raise ValueError("label_auto_save_path_missing")
            result = _tif_write_label_slice_snapshots(self.token, self.edit_path, self.slices, self.slice_revisions)
            self.last_result = result
            self.finished.emit(result)
        except Exception as exc:
            self.last_error = {"token": self.token, "edit_path": self.edit_path, "error": str(exc)}
            self.failed.emit(self.last_error)


class TifLabelManualSaveWorker(QObject):
    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, token, edit_path, slices, slice_revisions, context=None):
        super().__init__()
        self.token = int(token)
        self.edit_path = str(edit_path or "")
        self.slices = {int(key): np.asarray(value).copy() for key, value in (slices or {}).items()}
        self.slice_revisions = {int(key): int(value) for key, value in (slice_revisions or {}).items()}
        self.context = dict(context or {})
        self.last_result = None
        self.last_error = None

    def run(self):
        try:
            if not self.edit_path:
                raise ValueError("label_save_path_missing")
            result = _tif_write_label_slice_snapshots(self.token, self.edit_path, self.slices, self.slice_revisions)
            result["context"] = self.context
            self.last_result = result
            self.finished.emit(result)
        except Exception as exc:
            self.last_error = {"token": self.token, "edit_path": self.edit_path, "context": self.context, "error": str(exc)}
            self.failed.emit(self.last_error)


class TifPromoteWorkingEditWorker(QObject):
    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, project_manager, request):
        super().__init__()
        self.project_manager = project_manager
        self.request = dict(request or {})

    def run(self):
        try:
            scope = str(self.request.get("scope") or "")
            specimen_id = str(self.request.get("specimen_id") or "")
            part_id = str(self.request.get("part_id") or "")
            reslice_id = str(self.request.get("reslice_id") or "")
            started = time.perf_counter()
            if scope == "part":
                report = self.project_manager.evaluate_part_editable_result_review_ready(specimen_id, part_id, reslice_id)
                if not report.get("review_ready"):
                    raise ValueError("part_review_not_ready:" + ",".join(str(item) for item in (report.get("reasons") or [])))
                if reslice_id:
                    manual = self.project_manager.promote_part_reslice_editable_result_to_manual_truth(specimen_id, part_id, reslice_id)
                else:
                    manual = self.project_manager.promote_part_editable_result_to_manual_truth(specimen_id, part_id)
                result = {
                    "scope": scope,
                    "specimen_id": specimen_id,
                    "part_id": part_id,
                    "reslice_id": reslice_id,
                    "manual_truth": manual,
                    "review_report": report,
                }
            else:
                manual = self.project_manager.promote_working_edit_to_manual_truth(specimen_id)
                result = {
                    "scope": scope,
                    "specimen_id": specimen_id,
                    "manual_truth": manual,
                }
            result["promote_ms"] = max(0.0, (time.perf_counter() - started) * 1000.0)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit({"request": self.request, "error": str(exc)})


def _tif_write_label_slice_snapshots(token, edit_path, slices, slice_revisions):
    started = time.perf_counter()
    if not edit_path:
        raise ValueError("label_auto_save_path_missing")
    target = load_volume_sidecar(edit_path, mmap_mode="r+")
    try:
        saved = []
        for z_index, slice_array in sorted((slices or {}).items()):
            z_index = int(z_index)
            if 0 <= z_index < int(target.shape[0]):
                snapshot = np.asarray(slice_array)
                if tuple(snapshot.shape) != tuple(target[z_index].shape):
                    raise ValueError(f"label_auto_save_slice_shape_mismatch:{z_index}:{snapshot.shape}:{target[z_index].shape}")
                target[z_index] = snapshot
                saved.append(z_index)
        metadata = flush_volume_array(edit_path, target)
    finally:
        mmap_handle = getattr(target, "_mmap", None)
        if mmap_handle is not None:
            mmap_handle.close()
    return {
        "token": int(token),
        "edit_path": str(edit_path),
        "saved_slices": saved,
        "slice_revisions": {int(key): int(value) for key, value in (slice_revisions or {}).items()},
        "metadata": metadata,
        "save_ms": max(0.0, (time.perf_counter() - started) * 1000.0),
    }


class TifConfirmPartRoiWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, project_manager, request):
        super().__init__()
        self.project_manager = project_manager
        self.request = dict(request or {})

    def run(self):
        try:
            specimen_id = str(self.request.get("specimen_id") or "")
            part_id = str(self.request.get("part_id") or "")
            display_name = str(self.request.get("display_name") or part_id)
            bbox = self.request.get("bbox_zyx") or []
            source_shape = tuple(int(value) for value in (self.request.get("source_shape_zyx") or ()))
            roi_keyframes = list(self.request.get("roi_keyframes") or [])
            mask_contours = dict(self.request.get("mask_contours") or {})
            mask_bbox = self.request.get("mask_bbox_zyx") or []
            accepted_preview_mask = self.request.get("accepted_preview_mask")

            self.progress.emit(0, 0, "Creating part volume...")
            part = crop_volume_to_part(self.project_manager, specimen_id, part_id, bbox, display_name=display_name)
            self.progress.emit(60, 100, "Writing part image and empty mask...")

            mask_initialized = False
            mask_message = ""
            if mask_bbox:
                self.progress.emit(75, 100, "Initializing accepted/freehand part mask...")
                mask_initialized, mask_message = _tif_initialize_part_mask_from_full_volume_contours(
                    self.project_manager,
                    specimen_id,
                    part,
                    mask_contours,
                    bbox,
                    source_shape,
                    accepted_preview_mask=accepted_preview_mask,
                )
            elif roi_keyframes:
                self.progress.emit(75, 100, "Initializing ROI shell part mask...")
                mask_initialized, mask_message = _tif_initialize_part_mask_from_roi_shell(
                    self.project_manager,
                    specimen_id,
                    part,
                    roi_keyframes,
                    source_shape,
                )
            if mask_initialized:
                part.setdefault("view_settings", {})["volume_mask_mode"] = "masked_image"
                self.project_manager.save_project()

            roi_id = str(self.request.get("roi_id") or "")
            roi_metadata = dict(self.request.get("roi_metadata") or {})
            if roi_id:
                self.project_manager.update_part_roi(
                    specimen_id,
                    roi_id,
                    bbox_zyx=bbox,
                    status="part_created",
                    linked_part_id=part.get("part_id", ""),
                    metadata=roi_metadata,
                    save=True,
                )
            else:
                part_roi_id = f"{part.get('part_id', part_id)}_roi"
                try:
                    self.project_manager.add_part_roi(
                        specimen_id,
                        part_roi_id,
                        display_name=display_name or part.get("display_name") or part_roi_id,
                        bbox_zyx=bbox,
                        status="part_created",
                        linked_part_id=part.get("part_id", ""),
                        metadata=roi_metadata,
                        save=True,
                    )
                except ValueError:
                    pass
            self.progress.emit(100, 100, "Finalizing ROI...")
            self.finished.emit(
                {
                    "part": part,
                    "part_id": part.get("part_id", part_id),
                    "specimen_id": specimen_id,
                    "bbox_zyx": bbox,
                    "mask_bbox_zyx": mask_bbox,
                    "mask_initialized": bool(mask_initialized),
                    "mask_message": str(mask_message or ""),
                    "mask_keyframe_count": len((mask_contours.get("keyframes") or []) if isinstance(mask_contours, dict) else []),
                    "roi_keyframe_count": len(roi_keyframes),
                }
            )
        except Exception as exc:
            self.failed.emit({"error": str(exc), "request": self.request})


class TifLocalAxisResliceExportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, project_manager, specimen_id, part_id, payload):
        super().__init__()
        self.project_manager = project_manager
        self.specimen_id = specimen_id
        self.part_id = part_id
        self.payload = dict(payload or {})

    def run(self):
        try:
            self.progress.emit(0, 0, "Preparing Local Axis Reslice export...")
            result = export_part_reslice(self.project_manager, self.specimen_id, self.part_id, self.payload, progress_callback=self.progress.emit)
            self.progress.emit(100, 100, "Finalizing Local Axis Reslice export...")
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class TifBackendActionWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str, object)

    def __init__(self, project_manager, backend_config, action, part_refs=None, specimen_ids=None, input_scope="auto", model_manifest=""):
        super().__init__()
        self.project_manager = project_manager
        self.backend_config = dict(backend_config or {})
        self.action = str(action or "")
        self.part_refs = [dict(ref or {}) for ref in (part_refs or [])]
        self.specimen_ids = [str(item) for item in (specimen_ids or []) if str(item or "").strip()]
        self.input_scope = str(input_scope or "auto")
        self.model_manifest = str(model_manifest or "")
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def _is_cancelled(self):
        return bool(self._cancel_requested)

    def run(self):
        runner = None
        try:
            runner = TifBackendRunner(self.project_manager, self.backend_config)
            result = runner.run_action(
                self.action,
                specimen_ids=self.specimen_ids or None,
                part_refs=self.part_refs,
                input_scope=self.input_scope,
                model_manifest=self.model_manifest,
                progress_callback=self.progress.emit,
                cancel_check=self._is_cancelled,
            )
        except Exception as exc:
            context = {
                "run_id": getattr(runner, "last_run_id", ""),
                "run_dir": getattr(runner, "last_run_dir", ""),
                "result_json": getattr(runner, "last_result_json", ""),
                "action": self.action,
            }
            self.failed.emit(str(exc), context)
            return
        self.finished.emit(result)
