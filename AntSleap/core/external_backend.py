import json
import os
import subprocess
from datetime import datetime


EXTERNAL_BACKEND_CONTRACT_SCHEMA = "taxamask_external_backend_contract_v1"
EXTERNAL_PREDICTION_SCHEMA = "taxamask_prediction_v1"
EXTERNAL_MODEL_MANIFEST_SCHEMA = "taxamask_model_manifest_v1"
BUILTIN_BACKEND_ID = "builtin_locator_sam"
EXTERNAL_BACKEND_ID = "external_script"


DEFAULT_EXTERNAL_BACKEND_CONFIG = {
    "backend_id": "custom_external_backend",
    "display_name": "External Script Backend",
    "python_executable": "python",
    "prepare_dataset_command": "",
    "train_command": "",
    "predict_command": "",
    "model_manifest": "",
}


def sanitize_external_backend_config(config):
    clean = dict(DEFAULT_EXTERNAL_BACKEND_CONFIG)
    if isinstance(config, dict):
        for key in clean.keys():
            value = config.get(key)
            if value is not None:
                clean[key] = str(value)
    clean["backend_id"] = _safe_id(clean.get("backend_id") or "custom_external_backend")
    clean["display_name"] = clean.get("display_name") or "External Script Backend"
    clean["python_executable"] = clean.get("python_executable") or "python"
    return clean


def _safe_id(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return clean.strip("_") or "external_backend"


def _write_json(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return payload


def external_prediction_to_internal_payload(prediction, taxonomy):
    if not isinstance(prediction, dict):
        return {"polygons": {}, "auto_boxes": {}}
    allowed = set(taxonomy or [])
    polygons = {}
    auto_boxes = {}

    for label, points in (prediction.get("polygons") or {}).items():
        label_name = str(label).strip()
        if label_name in allowed and isinstance(points, list):
            polygons[label_name] = points

    source_boxes = prediction.get("boxes") or prediction.get("auto_boxes") or {}
    for label, box in source_boxes.items():
        label_name = str(label).strip()
        if label_name in allowed and isinstance(box, list) and len(box) == 4:
            auto_boxes[label_name] = box

    return {"polygons": polygons, "auto_boxes": auto_boxes}


class ExternalBackendRunner:
    def __init__(self, project_manager, backend_config, runs_root=None):
        self.project_manager = project_manager
        self.backend_config = sanitize_external_backend_config(backend_config)
        project_path = project_manager.current_project_path or os.getcwd()
        project_dir = os.path.dirname(os.path.abspath(project_path)) if os.path.splitext(project_path)[1] else os.path.abspath(project_path)
        self.runs_root = os.path.abspath(runs_root or os.path.join(project_dir, "external_runs"))

    def create_run_dir(self, action):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backend_id = _safe_id(self.backend_config.get("backend_id"))
        run_dir = os.path.join(self.runs_root, f"{timestamp}_{_safe_id(action)}_{backend_id}")
        os.makedirs(os.path.join(run_dir, "dataset"), exist_ok=True)
        os.makedirs(os.path.join(run_dir, "model"), exist_ok=True)
        os.makedirs(os.path.join(run_dir, "predictions"), exist_ok=True)
        os.makedirs(os.path.join(run_dir, "logs"), exist_ok=True)
        return run_dir

    def build_contract(self, action, run_dir, image_path="", prediction_json="", model_manifest=""):
        project_path = os.path.abspath(self.project_manager.current_project_path or "")
        model_manifest = model_manifest or self.backend_config.get("model_manifest", "")
        if model_manifest:
            model_manifest = self._format_template(model_manifest, run_dir, "")
        else:
            model_manifest = os.path.join(run_dir, "model", "taxamask_model_manifest.json")

        return {
            "schema_version": EXTERNAL_BACKEND_CONTRACT_SCHEMA,
            "action": action,
            "backend_id": self.backend_config.get("backend_id"),
            "project_json": project_path,
            "taxonomy": list(self.project_manager.project_data.get("taxonomy", [])),
            "locator_scope": list(self.project_manager.get_locator_scope()),
            "run_dir": os.path.abspath(run_dir),
            "dataset_dir": os.path.join(run_dir, "dataset"),
            "model_dir": os.path.join(run_dir, "model"),
            "image_path": os.path.abspath(image_path) if image_path else "",
            "prediction_json": os.path.abspath(prediction_json) if prediction_json else "",
            "model_manifest": os.path.abspath(model_manifest),
            "log_dir": os.path.join(run_dir, "logs"),
        }

    def run_prepare_and_train(self):
        run_dir = self.create_run_dir("train")
        prepare_contract = self.build_contract("prepare_dataset", run_dir)
        prepare_contract_path = os.path.join(run_dir, "prepare_contract.json")
        _write_json(prepare_contract_path, prepare_contract)

        prepare_command = self.backend_config.get("prepare_dataset_command", "").strip()
        if prepare_command:
            self._run_command(prepare_command, prepare_contract_path, run_dir, "prepare_dataset")

        train_contract = self.build_contract("train", run_dir, model_manifest=prepare_contract["model_manifest"])
        train_contract_path = os.path.join(run_dir, "contract.json")
        _write_json(train_contract_path, train_contract)
        train_command = self.backend_config.get("train_command", "").strip()
        if not train_command:
            raise ValueError("external_train_command_missing")
        self._run_command(train_command, train_contract_path, run_dir, "train")

        manifest_path = train_contract["model_manifest"]
        manifest = _read_json(manifest_path) if os.path.exists(manifest_path) else {}
        summary = {
            "run_dir": run_dir,
            "contract_json": train_contract_path,
            "model_manifest": manifest_path,
            "manifest": manifest,
        }
        _write_json(os.path.join(run_dir, "logs", "run_summary.json"), summary)
        return summary

    def run_predict(self, image_path, model_manifest=""):
        run_dir = self.create_run_dir("predict")
        prediction_json = os.path.join(run_dir, "predictions", f"{os.path.basename(image_path)}.prediction.json")
        contract = self.build_contract(
            "predict",
            run_dir,
            image_path=image_path,
            prediction_json=prediction_json,
            model_manifest=model_manifest or self.backend_config.get("model_manifest", ""),
        )
        contract_path = os.path.join(run_dir, "contract.json")
        _write_json(contract_path, contract)
        predict_command = self.backend_config.get("predict_command", "").strip()
        if not predict_command:
            raise ValueError("external_predict_command_missing")
        self._run_command(predict_command, contract_path, run_dir, "predict")

        prediction = _read_json(prediction_json)
        if prediction.get("schema_version") != EXTERNAL_PREDICTION_SCHEMA:
            raise ValueError(f"invalid_prediction_schema:{prediction.get('schema_version')}")
        return {
            "run_dir": run_dir,
            "contract_json": contract_path,
            "prediction_json": prediction_json,
            "prediction": prediction,
            "payload": external_prediction_to_internal_payload(
                prediction,
                self.project_manager.project_data.get("taxonomy", []),
            ),
        }

    def _format_template(self, template, run_dir, contract_path):
        return str(template).format(
            python=self.backend_config.get("python_executable", "python"),
            contract_json=contract_path,
            contract=contract_path,
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
            raise RuntimeError(f"external_backend_{action}_failed:{result.returncode}:{stderr_path}")
        return result.returncode
