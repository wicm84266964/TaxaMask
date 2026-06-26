import json
import os
import shutil
import subprocess
from datetime import datetime

from .safe_io import atomic_write_json
from .tif_project import TifProjectManager
from .tif_export import export_tif_training_dataset
from .tif_volume_io import copy_volume_sidecar, read_volume_metadata, volume_sidecar_exists


TIF_BACKEND_CONTRACT_SCHEMA_VERSION = "ant3d_tif_backend_contract_v1"
TIF_BACKEND_RESULT_SCHEMA_VERSION = "ant3d_tif_backend_result_v1"
TIF_MODEL_MANIFEST_SCHEMA_VERSION = "ant3d_tif_model_manifest_v1"


DEFAULT_TIF_BACKEND_CONFIG = {
    "backend_id": "custom_tif_backend",
    "display_name": "TIF Volume Backend",
    "python_executable": "python",
    "prepare_dataset_command": "",
    "train_command": "",
    "predict_command": "",
    "model_manifest": "",
    "export_formats": "ome_tiff,nrrd,mha,nifti",
}


def _now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_id(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return clean.strip("_") or "tif_backend"


def sanitize_tif_backend_config(config):
    clean = dict(DEFAULT_TIF_BACKEND_CONFIG)
    if isinstance(config, dict):
        for key in clean.keys():
            value = config.get(key)
            if value is not None:
                clean[key] = str(value)
    clean["backend_id"] = _safe_id(clean.get("backend_id") or "custom_tif_backend")
    clean["display_name"] = clean.get("display_name") or clean["backend_id"]
    clean["python_executable"] = clean.get("python_executable") or "python"
    return clean


def _write_json(path, payload):
    atomic_write_json(path, payload, indent=2, ensure_ascii=False)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return payload


class TifBackendRunner:
    def __init__(self, project_manager, backend_config=None, runs_root=None):
        if not isinstance(project_manager, TifProjectManager):
            raise TypeError("project_manager_must_be_tif_project_manager")
        self.project_manager = project_manager
        self.backend_config = sanitize_tif_backend_config(backend_config or {})
        project_dir = self.project_manager.project_dir
        self.runs_root = os.path.abspath(runs_root or os.path.join(project_dir, "runs"))

    def create_run_dir(self, action):
        backend_id = _safe_id(self.backend_config.get("backend_id"))
        run_id = f"{_safe_id(action)}_{_now_stamp()}_{backend_id}"
        run_dir = os.path.join(self.runs_root, _safe_id(action), run_id)
        os.makedirs(os.path.join(run_dir, "outputs"), exist_ok=True)
        os.makedirs(os.path.join(run_dir, "logs"), exist_ok=True)
        return run_id, run_dir

    def build_contract(self, action, specimen_ids=None, run_id=None, run_dir=None, dataset_dir="", model_manifest="", result_json=""):
        action = str(action or "").strip()
        if action not in {"prepare_dataset", "train", "predict"}:
            raise ValueError(f"unsupported_tif_backend_action:{action}")
        if run_id is None or run_dir is None:
            run_id, run_dir = self.create_run_dir(action)
        output_dir = os.path.join(run_dir, "outputs")
        result_json = result_json or os.path.join(run_dir, "result.json")
        model_manifest = model_manifest or self.backend_config.get("model_manifest", "")
        if model_manifest:
            model_manifest = self._format_template(model_manifest, run_dir, "")

        selected_specimens = self._select_specimens(action, specimen_ids)
        return {
            "schema_version": TIF_BACKEND_CONTRACT_SCHEMA_VERSION,
            "action": action,
            "backend_id": self.backend_config.get("backend_id"),
            "project_json": os.path.abspath(self.project_manager.current_project_path or ""),
            "run_id": run_id,
            "run_dir": os.path.abspath(run_dir),
            "dataset_dir": os.path.abspath(dataset_dir) if dataset_dir else os.path.join(run_dir, "dataset"),
            "model_manifest": os.path.abspath(model_manifest) if model_manifest else "",
            "output_dir": os.path.abspath(output_dir),
            "result_json": os.path.abspath(result_json),
            "specimens": selected_specimens,
            "training_config": {
                "model_family": self.backend_config.get("backend_id"),
                "normalization": "backend_default",
                "augmentation": "backend_default",
            },
            "safety": {
                "protect_manual_truth": True,
                "allow_model_draft_as_training_label": False,
                "allow_overwrite_outputs": False,
            },
        }

    def write_contract(self, contract):
        path = os.path.join(contract["run_dir"], "contract.json")
        _write_json(path, contract)
        return path

    def run_action(self, action, specimen_ids=None, dataset_dir="", model_manifest=""):
        run_id, run_dir = self.create_run_dir(action)
        contract = self.build_contract(action, specimen_ids, run_id, run_dir, dataset_dir, model_manifest)
        if action == "prepare_dataset":
            export_formats = [
                item.strip()
                for item in str(self.backend_config.get("export_formats", "")).split(",")
                if item.strip()
            ]
            export_result = export_tif_training_dataset(
                self.project_manager,
                contract["dataset_dir"],
                specimen_ids=[item["specimen_id"] for item in contract.get("specimens", [])],
                formats=export_formats or None,
                require_train_ready=True,
            )
            contract["dataset_manifest"] = export_result["manifest_path"]
            contract["dataset_formats"] = export_result["manifest"].get("formats", [])
        contract_path = self.write_contract(contract)
        command_key = {
            "prepare_dataset": "prepare_dataset_command",
            "train": "train_command",
            "predict": "predict_command",
        }[action]
        command = self.backend_config.get(command_key, "").strip()
        if not command:
            raise ValueError(f"tif_backend_{action}_command_missing")
        self._run_command(command, contract_path, run_dir, action)
        result = self.read_result(contract["result_json"])
        if action == "predict":
            imported = self.import_prediction_result(result)
        else:
            imported = []
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
        if result.get("schema_version") != TIF_BACKEND_RESULT_SCHEMA_VERSION:
            raise ValueError(f"invalid_tif_backend_result_schema:{result.get('schema_version')}")
        if result.get("contract_schema_version") != TIF_BACKEND_CONTRACT_SCHEMA_VERSION:
            raise ValueError(f"invalid_tif_backend_contract_schema:{result.get('contract_schema_version')}")
        if result.get("status") not in {"success", "partial_success"}:
            raise ValueError(f"tif_backend_result_not_success:{result.get('status')}")
        return result

    def import_prediction_result(self, result):
        imported = []
        for artifact in result.get("artifacts", []):
            if not isinstance(artifact, dict):
                continue
            if artifact.get("type") != "prediction_label_volume" or artifact.get("role") != "model_draft":
                continue
            specimen_id = str(artifact.get("specimen_id", "")).strip()
            source_path = self._artifact_abs_path(result, artifact.get("path", ""))
            specimen = self.project_manager.get_specimen(specimen_id, default=None)
            if specimen is None:
                raise ValueError(f"prediction_unknown_specimen:{specimen_id}")
            if not volume_sidecar_exists(source_path):
                raise FileNotFoundError(source_path)
            source_meta = read_volume_metadata(source_path)
            working_shape = (specimen.get("working_volume") or {}).get("shape_zyx", [])
            if list(source_meta.get("shape_zyx", [])) != list(working_shape):
                raise ValueError(f"prediction_shape_mismatch:{specimen_id}:{source_meta.get('shape_zyx')}:{working_shape}")

            prediction_id = artifact.get("prediction_id") or f"{result.get('run_id')}_{specimen_id}"
            draft_rel = os.path.join(
                self.project_manager.specimen_dir(specimen_id),
                "labels",
                "model_draft",
                f"{_safe_id(prediction_id)}.ome.zarr",
            ).replace("\\", "/")
            target_abs = self.project_manager.to_absolute(draft_rel)
            if os.path.exists(target_abs):
                raise FileExistsError(target_abs)
            copy_volume_sidecar(source_path, target_abs, role="model_draft")
            draft = self.project_manager.add_model_draft(
                specimen_id,
                draft_rel,
                source_meta["shape_zyx"],
                source_meta["dtype"],
                prediction_id=prediction_id,
                source_model=result.get("provenance", {}).get("model_manifest", ""),
                spacing_zyx=source_meta.get("spacing_zyx"),
                spacing_unit=source_meta.get("spacing_unit", "micrometer"),
                orientation=source_meta.get("orientation", "unknown"),
                save=False,
            )
            imported.append(draft)
        self.project_manager.save_project()
        return imported

    def _select_specimens(self, action, specimen_ids):
        ids = [str(item) for item in specimen_ids] if specimen_ids else [item.get("specimen_id") for item in self.project_manager.project_data.get("specimens", [])]
        specimens = []
        for specimen_id in ids:
            specimen = self.project_manager.get_specimen(specimen_id, default=None)
            if specimen is None:
                raise KeyError(f"unknown_specimen_id:{specimen_id}")
            if action in {"prepare_dataset", "train"}:
                readiness = self.project_manager.evaluate_train_ready(specimen_id)
                if not readiness["train_ready"]:
                    raise ValueError(f"specimen_not_train_ready:{specimen_id}:{','.join(readiness['reasons'])}")
            specimens.append(self._contract_specimen(specimen, include_label=action in {"prepare_dataset", "train"}))
        return specimens

    def _contract_specimen(self, specimen, include_label):
        working = specimen.get("working_volume") or {}
        manual = (specimen.get("labels") or {}).get("manual_truth") or {}
        return {
            "specimen_id": specimen.get("specimen_id"),
            "modality": specimen.get("modality", "unknown"),
            "input_volume": {
                "path": self.project_manager.to_absolute(working.get("path", "")),
                "format": working.get("format", ""),
                "shape_zyx": working.get("shape_zyx", []),
                "dtype": working.get("dtype", ""),
                "spacing_zyx": working.get("spacing_zyx") or [1.0, 1.0, 1.0],
                "spacing_unit": working.get("spacing_unit", "micrometer"),
                "orientation": working.get("orientation", "unknown"),
            },
            "label_volume": {
                "path": self.project_manager.to_absolute(manual.get("path", "")) if include_label else "",
                "format": manual.get("format", "") if include_label else "",
                "role": "manual_truth" if include_label else "none",
                "shape_zyx": manual.get("shape_zyx", []) if include_label else [],
                "dtype": manual.get("dtype", "") if include_label else "",
            },
            "material_map": self.project_manager.to_absolute(specimen.get("material_map", "")),
        }

    def _artifact_abs_path(self, result, path):
        text = str(path or "")
        if os.path.isabs(text):
            return os.path.normpath(text)
        run_dir = os.path.abspath(os.path.join(self.runs_root, ".."))
        provenance_run_dir = result.get("provenance", {}).get("run_dir")
        if provenance_run_dir:
            run_dir = provenance_run_dir
        elif result.get("run_id"):
            # Best effort: artifacts normally live under the result JSON directory.
            pass
        result_json = result.get("_result_json", "")
        base = os.path.dirname(result_json) if result_json else ""
        if not base:
            base = os.getcwd()
        return os.path.abspath(os.path.join(base, text))

    def _register_run(self, contract, result):
        runs = self.project_manager.project_data.setdefault("runs", [])
        runs.append(
            {
                "run_id": contract.get("run_id"),
                "action": contract.get("action"),
                "backend_id": contract.get("backend_id"),
                "run_dir": contract.get("run_dir"),
                "result_status": result.get("status"),
                "created_at": _now_iso(),
            }
        )
        if contract.get("action") == "train":
            models = self.project_manager.project_data.setdefault("models", [])
            manifest = result.get("provenance", {}).get("model_manifest") or contract.get("model_manifest")
            if manifest:
                models.append({"model_manifest": manifest, "backend_id": contract.get("backend_id"), "run_id": contract.get("run_id")})
        self.project_manager.save_project()

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
            raise RuntimeError(f"tif_backend_{action}_failed:{result.returncode}:{stderr_path}")
        return result.returncode


def write_mock_tif_backend_result(contract, prediction_arrays=None):
    action = contract["action"]
    artifacts = []
    if action == "prepare_dataset":
        manifest_path = os.path.join(contract["output_dir"], "dataset_manifest.json")
        _write_json(
            manifest_path,
            {
                "schema_version": "ant3d_tif_dataset_manifest_v1",
                "specimens": [item["specimen_id"] for item in contract.get("specimens", [])],
            },
        )
        artifacts.append({"type": "dataset_manifest", "path": os.path.relpath(manifest_path, os.path.dirname(contract["result_json"])), "format": "json"})
    elif action == "train":
        manifest_path = contract.get("model_manifest") or os.path.join(contract["output_dir"], "model_manifest.json")
        _write_json(
            manifest_path,
            {
                "schema_version": TIF_MODEL_MANIFEST_SCHEMA_VERSION,
                "model_id": f"{contract['backend_id']}/{contract['run_id']}",
                "backend_id": contract["backend_id"],
                "model_family": contract["training_config"].get("model_family"),
                "created_at": _now_iso(),
                "trained_specimens": [item["specimen_id"] for item in contract.get("specimens", [])],
                "label_role": "manual_truth",
            },
        )
        artifacts.append({"type": "model_manifest", "path": os.path.relpath(manifest_path, os.path.dirname(contract["result_json"])), "format": "json"})
    elif action == "predict":
        if prediction_arrays is None:
            prediction_arrays = {}
        from .tif_volume_io import write_volume_sidecar

        for specimen in contract.get("specimens", []):
            specimen_id = specimen["specimen_id"]
            input_volume = specimen.get("input_volume", {})
            shape = input_volume.get("shape_zyx", [])
            array = prediction_arrays.get(specimen_id)
            if array is None:
                import numpy as np

                array = np.zeros(tuple(shape), dtype=np.uint16)
            prediction_id = f"{contract['run_id']}_{_safe_id(specimen_id)}"
            out_path = os.path.join(contract["output_dir"], f"{prediction_id}.ome.zarr")
            meta = write_volume_sidecar(out_path, array, role="model_draft", spacing_zyx=input_volume.get("spacing_zyx"), spacing_unit=input_volume.get("spacing_unit", "micrometer"), orientation=input_volume.get("orientation", "unknown"), source_format="mock_tif_backend")
            artifacts.append(
                {
                    "type": "prediction_label_volume",
                    "specimen_id": specimen_id,
                    "prediction_id": prediction_id,
                    "path": os.path.relpath(out_path, os.path.dirname(contract["result_json"])),
                    "format": meta["format"],
                    "role": "model_draft",
                }
            )

    result = {
        "schema_version": TIF_BACKEND_RESULT_SCHEMA_VERSION,
        "contract_schema_version": TIF_BACKEND_CONTRACT_SCHEMA_VERSION,
        "status": "success",
        "action": action,
        "backend_id": contract["backend_id"],
        "run_id": contract["run_id"],
        "artifacts": artifacts,
        "metrics": {"summary": {}, "by_material": {}},
        "warnings": [],
        "errors": [],
        "provenance": {
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "model_manifest": contract.get("model_manifest", ""),
            "input_specimens": [item["specimen_id"] for item in contract.get("specimens", [])],
            "input_label_role": "manual_truth" if action in {"prepare_dataset", "train"} else "none",
        },
    }
    _write_json(contract["result_json"], result)
    return result
