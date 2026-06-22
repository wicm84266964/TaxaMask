import json
import os
import subprocess
from datetime import datetime

from .tif_project import TifProjectManager


LOCAL_AXIS_BACKEND_CONTRACT_SCHEMA_VERSION = "taxamask_tif_local_axis_backend_contract_v1"
LOCAL_AXIS_BACKEND_RESULT_SCHEMA_VERSION = "taxamask_tif_local_axis_backend_result_v1"
LOCAL_AXIS_MODEL_MANIFEST_SCHEMA_VERSION = "taxamask_tif_local_axis_model_manifest_v1"
LOCAL_AXIS_TRAINING_MANIFEST_SCHEMA_VERSION = "taxamask_tif_local_axis_training_manifest_v1"
GLOBAL_ROI_PROPOSALS_SCHEMA_VERSION = "taxamask_tif_local_axis_global_roi_proposals_v1"
LOCAL_FRAME_PROPOSALS_SCHEMA_VERSION = "taxamask_tif_local_axis_frame_proposals_v1"

LOCAL_AXIS_BACKEND_ACTIONS = {"prepare_dataset", "train", "predict_global_roi", "predict_local_frame", "predict"}

DEFAULT_LOCAL_AXIS_BACKEND_CONFIG = {
    "backend_id": "external_local_axis",
    "display_name": "Local Axis Backend",
    "python_executable": "python",
    "prepare_dataset_command": "",
    "train_command": "",
    "predict_command": "",
    "predict_global_roi_command": "",
    "predict_local_frame_command": "",
    "model_manifest": "",
}


def _now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_id(value, fallback="local_axis"):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    clean = clean.strip("_")
    return clean or str(fallback or "local_axis")


def _write_json(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return payload


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return payload


def _normalize_bbox_zyx(bbox):
    if not isinstance(bbox, (list, tuple)):
        return []
    if len(bbox) == 6:
        try:
            return [[int(bbox[0]), int(bbox[3])], [int(bbox[1]), int(bbox[4])], [int(bbox[2]), int(bbox[5])]]
        except (TypeError, ValueError):
            return []
    if len(bbox) != 3:
        return []
    clean = []
    try:
        for pair in bbox:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                return []
            clean.append([int(pair[0]), int(pair[1])])
    except (TypeError, ValueError):
        return []
    return clean


def _normalize_point_zyx(point):
    if not isinstance(point, (list, tuple)) or len(point) != 3:
        return []
    try:
        return [float(point[0]), float(point[1]), float(point[2])]
    except (TypeError, ValueError):
        return []


def _normalize_status(status):
    clean = str(status or "proposed").strip()
    return clean if clean in {"proposed", "needs_review", "accepted", "rejected", "exported"} else "proposed"


def sanitize_local_axis_backend_config(config):
    clean = dict(DEFAULT_LOCAL_AXIS_BACKEND_CONFIG)
    if isinstance(config, dict):
        for key in clean.keys():
            value = config.get(key)
            if value is not None:
                clean[key] = str(value)
    clean["backend_id"] = _safe_id(clean.get("backend_id") or "external_local_axis")
    clean["display_name"] = clean.get("display_name") or clean["backend_id"]
    clean["python_executable"] = clean.get("python_executable") or "python"
    return clean


def normalize_global_proposal(payload):
    source = payload if isinstance(payload, dict) else {}
    bbox = _normalize_bbox_zyx(source.get("bbox_zyx"))
    center = _normalize_point_zyx(source.get("center_zyx"))
    if not bbox or not center:
        raise ValueError("global_proposal_requires_bbox_zyx_and_center_zyx")
    specimen_id = str(source.get("specimen_id") or "").strip()
    if not specimen_id:
        raise ValueError("global_proposal_requires_specimen_id")
    proposal_id = _safe_id(source.get("global_proposal_id") or source.get("proposal_id") or source.get("id") or f"global_proposal_{_now_stamp()}", "global_proposal")
    return {
        "global_proposal_id": proposal_id,
        "specimen_id": specimen_id,
        "template_id": str(source.get("template_id") or ""),
        "coordinate_space": str(source.get("coordinate_space") or "full_volume_voxel_zyx"),
        "bbox_zyx": bbox,
        "center_zyx": center,
        "confidence": float(source.get("confidence", 0.0) or 0.0),
        "model_id": str(source.get("model_id") or ""),
        "model_version": str(source.get("model_version") or ""),
        "status": _normalize_status(source.get("status")),
        "hard_case_flags": list(source.get("hard_case_flags", []) or []) if isinstance(source.get("hard_case_flags", []), list) else [],
        "reviewer_notes": str(source.get("reviewer_notes") or ""),
        "provenance": dict(source.get("provenance") or {}),
        "created_at": str(source.get("created_at") or _now_iso()),
        "updated_at": str(source.get("updated_at") or source.get("created_at") or _now_iso()),
    }


def normalize_frame_proposal(payload):
    source = payload if isinstance(payload, dict) else {}
    origin = _normalize_point_zyx(source.get("origin_zyx"))
    start = _normalize_point_zyx(source.get("output_axis_start_zyx"))
    end = _normalize_point_zyx(source.get("output_axis_end_zyx"))
    if not origin or not start or not end:
        raise ValueError("local_frame_proposal_requires_origin_and_output_axis")
    specimen_id = str(source.get("specimen_id") or "").strip()
    part_id = str(source.get("part_id") or "").strip()
    if not specimen_id or not part_id:
        raise ValueError("local_frame_proposal_requires_specimen_id_and_part_id")
    proposal_id = _safe_id(source.get("frame_proposal_id") or source.get("proposal_id") or source.get("id") or f"frame_proposal_{_now_stamp()}", "frame_proposal")
    return {
        "frame_proposal_id": proposal_id,
        "specimen_id": specimen_id,
        "part_id": part_id,
        "template_id": str(source.get("template_id") or ""),
        "coordinate_space": str(source.get("coordinate_space") or "part_volume_voxel_zyx"),
        "origin_zyx": origin,
        "output_axis_start_zyx": start,
        "output_axis_end_zyx": end,
        "roll_reference": dict(source.get("roll_reference") or {}),
        "local_frame": dict(source.get("local_frame") or {}),
        "confidence": float(source.get("confidence", 0.0) or 0.0),
        "landmark_scores": dict(source.get("landmark_scores") or {}),
        "missing_landmarks": list(source.get("missing_landmarks", []) or []) if isinstance(source.get("missing_landmarks", []), list) else [],
        "model_id": str(source.get("model_id") or ""),
        "model_version": str(source.get("model_version") or ""),
        "status": _normalize_status(source.get("status")),
        "hard_case_flags": list(source.get("hard_case_flags", []) or []) if isinstance(source.get("hard_case_flags", []), list) else [],
        "reviewer_notes": str(source.get("reviewer_notes") or ""),
        "provenance": dict(source.get("provenance") or {}),
        "created_at": str(source.get("created_at") or _now_iso()),
        "updated_at": str(source.get("updated_at") or source.get("created_at") or _now_iso()),
    }


def _proposal_list_from_payload(payload, expected_schema_version=None):
    if isinstance(payload, dict):
        schema_version = payload.get("schema_version")
        if expected_schema_version and schema_version != expected_schema_version:
            raise ValueError(f"invalid_local_axis_proposal_schema:{schema_version}")
        proposals = payload.get("proposals")
        if isinstance(proposals, list):
            return proposals
    if isinstance(payload, list):
        return payload
    raise ValueError("proposal_json_must_have_proposals_list")


def load_global_roi_proposals(path):
    payload = _read_json(path)
    return [normalize_global_proposal(item) for item in _proposal_list_from_payload(payload, GLOBAL_ROI_PROPOSALS_SCHEMA_VERSION)]


def load_local_frame_proposals(path):
    payload = _read_json(path)
    return [normalize_frame_proposal(item) for item in _proposal_list_from_payload(payload, LOCAL_FRAME_PROPOSALS_SCHEMA_VERSION)]


def import_local_axis_proposals(project_manager, global_proposals=None, local_frame_proposals=None, save=True):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    imported = {"global_roi_proposals": [], "local_frame_proposals": []}
    for proposal in global_proposals or []:
        record = normalize_global_proposal(proposal)
        imported["global_roi_proposals"].append(project_manager.add_global_axis_proposal(record["specimen_id"], record, save=False))
    for proposal in local_frame_proposals or []:
        record = normalize_frame_proposal(proposal)
        imported["local_frame_proposals"].append(project_manager.add_local_frame_proposal(record["specimen_id"], record["part_id"], record, save=False))
    if save:
        project_manager.save_project()
    return imported


def validate_local_axis_backend_command(command):
    text = str(command or "").strip()
    if not text:
        return True
    return "{contract}" in text or "{contract_json}" in text


def local_axis_model_record_from_manifest(manifest, manifest_path, result_context=None):
    source = manifest if isinstance(manifest, dict) else {}
    context = result_context if isinstance(result_context, dict) else {}
    if source.get("schema_version") != LOCAL_AXIS_MODEL_MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"invalid_local_axis_model_manifest_schema:{source.get('schema_version')}")
    model_id = str(source.get("model_id") or "").strip()
    if not model_id and context.get("backend_id") and context.get("run_id"):
        model_id = f"{context.get('backend_id')}/{context.get('run_id')}"
    if not model_id:
        model_id = f"local_axis_model_{_now_stamp()}"
    return {
        "model_id": model_id,
        "model_version": source.get("model_version") or "",
        "template_id": source.get("template_id") or "",
        "model_type": source.get("model_type") or "local_frame",
        "backend_type": "external_local_axis",
        "backend_id": source.get("backend_id") or context.get("backend_id") or "",
        "input_contract": source.get("input_contract") or {},
        "output_contract": source.get("output_contract") or {},
        "model_manifest": os.path.abspath(manifest_path),
        "training_manifest_path": (source.get("trained_from") or {}).get("training_manifest", ""),
        "notes": source.get("notes") or "",
    }


def register_local_axis_model_manifest(project_manager, manifest_path, result_context=None, save=True):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    path = os.path.abspath(str(manifest_path or ""))
    manifest = _read_json(path)
    model = local_axis_model_record_from_manifest(manifest, path, result_context)
    return project_manager.register_local_axis_model(model, save=save)


def export_local_axis_training_manifest(project_manager, output_dir, filters=None):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    filters = filters if isinstance(filters, dict) else {}
    include_unconfirmed = bool(filters.get("include_unconfirmed", False))
    template_filter = filters.get("template_id")
    samples = []
    for specimen in project_manager.project_data.get("specimens", []) or []:
        specimen_id = specimen.get("specimen_id", "")
        full_volume = specimen.get("working_volume") or {}
        for part in specimen.get("parts", []) or []:
            part_id = part.get("part_id", "")
            for reslice in (part.get("metadata") or {}).get("local_axis_reslices", []) or []:
                training = reslice.get("training") or {}
                if template_filter and reslice.get("template_id") != template_filter:
                    continue
                if not include_unconfirmed:
                    if not bool(training.get("human_confirmed")) or not bool(training.get("usable_for_training", True)):
                        continue
                sample = {
                    "sample_id": f"{specimen_id}:{part_id}:{reslice.get('reslice_id', '')}",
                    "specimen_id": specimen_id,
                    "part_id": part_id,
                    "reslice_id": reslice.get("reslice_id", ""),
                    "template_id": reslice.get("template_id", ""),
                    "full_volume": {
                        "path": project_manager.to_absolute(full_volume.get("path", "")),
                        "shape_zyx": full_volume.get("shape_zyx", []),
                        "spacing_zyx": full_volume.get("spacing_zyx") or [1.0, 1.0, 1.0],
                    },
                    "part_image": {
                        "path": project_manager.to_absolute((part.get("image") or {}).get("path", "")),
                        "shape_zyx": (part.get("image") or {}).get("shape_zyx", []),
                        "spacing_zyx": (part.get("image") or {}).get("spacing_zyx") or full_volume.get("spacing_zyx") or [1.0, 1.0, 1.0],
                    },
                    "part_mask": {
                        "path": project_manager.to_absolute((part.get("mask") or {}).get("path", "")) if (part.get("mask") or {}).get("path") else "",
                        "available": bool((part.get("mask") or {}).get("path")),
                    },
                    "parent_bbox_zyx": part.get("parent_bbox_zyx", []),
                    "local_frame": reslice.get("local_frame", {}),
                    "reslice_params": reslice.get("reslice_params", {}),
                    "training": dict(training),
                    "hard_case_flags": list(training.get("hard_case_flags", []) or []) if isinstance(training.get("hard_case_flags", []), list) else [],
                    "source": reslice.get("source", {}),
                    "metadata_path": project_manager.to_absolute(reslice.get("metadata_path", "")) if reslice.get("metadata_path") else "",
                }
                samples.append(sample)

    manifest = {
        "schema_version": LOCAL_AXIS_TRAINING_MANIFEST_SCHEMA_VERSION,
        "project_id": project_manager.project_data.get("project_id", ""),
        "created_at": _now_iso(),
        "filters": dict(filters),
        "sample_count": len(samples),
        "samples": samples,
    }
    manifest_path = os.path.join(os.path.abspath(output_dir), "local_axis_training_manifest.json")
    _write_json(manifest_path, manifest)
    return {"manifest": manifest, "manifest_path": manifest_path, "sample_count": len(samples)}


class TifLocalAxisBackendRunner:
    def __init__(self, project_manager, backend_config=None, runs_root=None):
        if not isinstance(project_manager, TifProjectManager):
            raise TypeError("project_manager_must_be_tif_project_manager")
        self.project_manager = project_manager
        self.backend_config = sanitize_local_axis_backend_config(backend_config or {})
        self.runs_root = os.path.abspath(runs_root or os.path.join(self.project_manager.project_dir, "runs", "local_axis"))

    def create_run_dir(self, action):
        action_id = _safe_id(action)
        backend_id = _safe_id(self.backend_config.get("backend_id"))
        run_id = f"{action_id}_{_now_stamp()}_{backend_id}"
        run_dir = os.path.join(self.runs_root, action_id, run_id)
        for child in ("dataset", "outputs", "logs"):
            os.makedirs(os.path.join(run_dir, child), exist_ok=True)
        return run_id, run_dir

    def build_contract(self, action, specimen_ids=None, part_ids_by_specimen=None, template_id="", run_id=None, run_dir=None, dataset_dir="", model_manifest="", result_json=""):
        action = str(action or "").strip()
        if action not in LOCAL_AXIS_BACKEND_ACTIONS:
            raise ValueError(f"unsupported_local_axis_backend_action:{action}")
        if run_id is None or run_dir is None:
            run_id, run_dir = self.create_run_dir(action)
        output_dir = os.path.join(run_dir, "outputs")
        dataset_dir = dataset_dir or os.path.join(run_dir, "dataset")
        result_json = result_json or os.path.join(run_dir, "result.json")
        model_manifest = model_manifest or self.backend_config.get("model_manifest", "")
        if model_manifest:
            model_manifest = self._format_template(model_manifest, run_dir, "")
        return {
            "schema_version": LOCAL_AXIS_BACKEND_CONTRACT_SCHEMA_VERSION,
            "action": action,
            "backend_id": self.backend_config.get("backend_id"),
            "project_json": os.path.abspath(self.project_manager.current_project_path or ""),
            "run_id": run_id,
            "run_dir": os.path.abspath(run_dir),
            "dataset_dir": os.path.abspath(dataset_dir),
            "output_dir": os.path.abspath(output_dir),
            "result_json": os.path.abspath(result_json),
            "log_dir": os.path.abspath(os.path.join(run_dir, "logs")),
            "model_manifest": os.path.abspath(model_manifest) if model_manifest else "",
            "template_id": str(template_id or ""),
            "target_part_name": str(template_id or ""),
            "specimens": self._contract_specimens(specimen_ids, part_ids_by_specimen),
            "training_config": {
                "model_family": "local_axis",
                "global_roi_enabled": action in {"predict_global_roi", "predict", "prepare_dataset", "train"},
                "local_frame_enabled": action in {"predict_local_frame", "predict", "prepare_dataset", "train"},
                "normalization": "backend_default",
                "augmentation": "backend_default",
            },
            "safety": {
                "output_is_reviewable_proposal": True,
                "do_not_write_project_json": True,
                "do_not_write_manual_truth": True,
                "do_not_create_final_reslice": True,
                "allow_overwrite_outputs": False,
            },
        }

    def write_contract(self, contract):
        path = os.path.join(contract["run_dir"], "contract.json")
        _write_json(path, contract)
        return path

    def run_action(self, action, specimen_ids=None, part_ids_by_specimen=None, template_id="", dataset_dir="", model_manifest=""):
        run_id, run_dir = self.create_run_dir(action)
        contract = self.build_contract(action, specimen_ids, part_ids_by_specimen, template_id, run_id, run_dir, dataset_dir, model_manifest)
        if action == "prepare_dataset":
            export = export_local_axis_training_manifest(self.project_manager, contract["dataset_dir"], {"template_id": template_id} if template_id else {})
            contract["training_manifest"] = export["manifest_path"]
            contract["training_sample_count"] = export["sample_count"]
        contract_path = self.write_contract(contract)
        command = self._command_for_action(action)
        if not command:
            raise ValueError(f"local_axis_backend_{action}_command_missing")
        self._run_command(command, contract_path, run_dir, action)
        result = self.read_result(contract["result_json"])
        imported = self.import_backend_result(result)
        self._register_run(contract, result)
        return {
            "run_id": run_id,
            "run_dir": run_dir,
            "contract_json": contract_path,
            "contract": contract,
            "result": result,
            "imported": imported,
        }

    def read_result(self, result_json):
        result = _read_json(result_json)
        result["_result_json"] = os.path.abspath(result_json)
        if result.get("schema_version") != LOCAL_AXIS_BACKEND_RESULT_SCHEMA_VERSION:
            raise ValueError(f"invalid_local_axis_backend_result_schema:{result.get('schema_version')}")
        if result.get("contract_schema_version") != LOCAL_AXIS_BACKEND_CONTRACT_SCHEMA_VERSION:
            raise ValueError(f"invalid_local_axis_backend_contract_schema:{result.get('contract_schema_version')}")
        if result.get("status") not in {"success", "partial_success"}:
            raise ValueError(f"local_axis_backend_result_not_success:{result.get('status')}")
        return result

    def import_backend_result(self, result):
        imported = {"global_roi_proposals": [], "local_frame_proposals": [], "models": []}
        warnings = []
        for artifact in result.get("artifacts", []) or []:
            if not isinstance(artifact, dict):
                continue
            artifact_type = artifact.get("type")
            path = self._artifact_abs_path(result, artifact.get("path", ""))
            if artifact_type == "global_roi_proposals":
                imported["global_roi_proposals"].extend(load_global_roi_proposals(path))
            elif artifact_type == "local_frame_proposals":
                imported["local_frame_proposals"].extend(load_local_frame_proposals(path))
            elif artifact_type == "local_axis_model_manifest":
                imported["models"].append(self._register_model_manifest(path, result))
            elif artifact_type in {"local_axis_training_manifest", "dataset_manifest"}:
                continue
            else:
                warnings.append(f"unknown_artifact_type:{artifact_type}")
        project_imported = import_local_axis_proposals(
            self.project_manager,
            imported["global_roi_proposals"],
            imported["local_frame_proposals"],
            save=False,
        )
        if warnings:
            result.setdefault("warnings", []).extend(warnings)
        self.project_manager.save_project()
        project_imported["models"] = imported["models"]
        return project_imported

    def _register_model_manifest(self, path, result):
        return register_local_axis_model_manifest(self.project_manager, path, result_context=result, save=False)

    def _register_run(self, contract, result):
        return self.project_manager.add_local_axis_run(
            {
                "run_id": contract.get("run_id"),
                "action": contract.get("action"),
                "backend_id": contract.get("backend_id"),
                "template_id": contract.get("template_id", ""),
                "specimen_ids": [item.get("specimen_id") for item in contract.get("specimens", [])],
                "part_ids": [
                    part.get("part_id")
                    for specimen in contract.get("specimens", [])
                    for part in specimen.get("parts", []) or []
                ],
                "run_dir": contract.get("run_dir"),
                "contract_json": os.path.join(contract.get("run_dir", ""), "contract.json"),
                "result_json": contract.get("result_json"),
                "result_status": result.get("status"),
                "metrics": result.get("metrics") or {},
                "warnings": result.get("warnings") or [],
                "errors": result.get("errors") or [],
            },
            save=True,
        )

    def _contract_specimens(self, specimen_ids, part_ids_by_specimen):
        ids = [str(item) for item in specimen_ids] if specimen_ids else [item.get("specimen_id") for item in self.project_manager.project_data.get("specimens", [])]
        part_map = part_ids_by_specimen or {}
        result = []
        for specimen_id in ids:
            specimen = self.project_manager.get_specimen(specimen_id, default=None)
            if specimen is None:
                raise KeyError(f"unknown_specimen_id:{specimen_id}")
            working = specimen.get("working_volume") or {}
            part_ids = part_map.get(specimen_id)
            parts = []
            for part in specimen.get("parts", []) or []:
                if part_ids is not None and part.get("part_id") not in set(part_ids):
                    continue
                parts.append(self._contract_part(part))
            result.append(
                {
                    "specimen_id": specimen.get("specimen_id"),
                    "input_volume": {
                        "path": self.project_manager.to_absolute(working.get("path", "")),
                        "format": working.get("format", ""),
                        "shape_zyx": working.get("shape_zyx", []),
                        "dtype": working.get("dtype", ""),
                        "spacing_zyx": working.get("spacing_zyx") or [1.0, 1.0, 1.0],
                        "spacing_unit": working.get("spacing_unit", "micrometer"),
                        "orientation": working.get("orientation", "unknown"),
                    },
                    "parts": parts,
                }
            )
        return result

    def _contract_part(self, part):
        image = part.get("image") or {}
        mask = part.get("mask") or {}
        return {
            "part_id": part.get("part_id"),
            "part_name": part.get("display_name") or part.get("part_id"),
            "part_image": {
                "path": self.project_manager.to_absolute(image.get("path", "")),
                "format": image.get("format", ""),
                "shape_zyx": image.get("shape_zyx", []),
                "dtype": image.get("dtype", ""),
                "spacing_zyx": image.get("spacing_zyx") or [1.0, 1.0, 1.0],
            },
            "part_mask": {
                "path": self.project_manager.to_absolute(mask.get("path", "")) if mask.get("path") else "",
                "format": mask.get("format", ""),
                "shape_zyx": mask.get("shape_zyx", []),
                "dtype": mask.get("dtype", ""),
                "available": bool(mask.get("path")),
            },
            "parent_bbox_zyx": part.get("parent_bbox_zyx", []),
        }

    def _artifact_abs_path(self, result, path):
        text = str(path or "")
        if os.path.isabs(text):
            return os.path.normpath(text)
        result_json = result.get("_result_json", "")
        base = os.path.dirname(result_json) if result_json else os.getcwd()
        return os.path.abspath(os.path.join(base, text))

    def _command_for_action(self, action):
        if action == "predict_global_roi":
            return self.backend_config.get("predict_global_roi_command") or self.backend_config.get("predict_command", "")
        if action == "predict_local_frame":
            return self.backend_config.get("predict_local_frame_command") or self.backend_config.get("predict_command", "")
        return self.backend_config.get(f"{action}_command", "")

    def _format_template(self, template, run_dir, contract_path):
        return str(template).format(
            python=self.backend_config.get("python_executable", "python"),
            contract=contract_path,
            contract_json=contract_path,
            run_dir=run_dir,
        )

    def _run_command(self, command_template, contract_path, run_dir, action):
        command = self._format_template(command_template, run_dir, contract_path)
        log_dir = os.path.join(run_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        stdout_path = os.path.join(log_dir, f"{action}_stdout.log")
        stderr_path = os.path.join(log_dir, f"{action}_stderr.log")
        with open(stdout_path, "w", encoding="utf-8") as stdout_handle, open(stderr_path, "w", encoding="utf-8") as stderr_handle:
            result = subprocess.run(
                command,
                cwd=run_dir,
                shell=True,
                text=True,
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
        if result.returncode != 0:
            raise RuntimeError(f"local_axis_backend_{action}_failed:{result.returncode}:{stderr_path}")
        return result.returncode
