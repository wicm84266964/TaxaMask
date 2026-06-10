import json
import os
import subprocess
from datetime import datetime


EXTERNAL_BLINK_CONTRACT_SCHEMA = "taxamask_external_blink_contract_v1"
EXTERNAL_BLINK_PREDICTION_SCHEMA = "taxamask_blink_prediction_v1"


DEFAULT_EXTERNAL_BLINK_CONFIG = {
    "backend_id": "custom_blink_backend",
    "display_name": "External Blink Backend",
    "python_executable": "python",
    "predict_command": "",
    "train_command": "",
    "model_manifest": "",
}


def _safe_id(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return clean.strip("_") or "external_blink_backend"


def sanitize_external_blink_config(config):
    clean = dict(DEFAULT_EXTERNAL_BLINK_CONFIG)
    if isinstance(config, dict):
        for key in clean:
            value = config.get(key)
            if value is not None:
                clean[key] = str(value)
    clean["backend_id"] = _safe_id(clean.get("backend_id") or "custom_blink_backend")
    clean["display_name"] = clean.get("display_name") or "External Blink Backend"
    clean["python_executable"] = clean.get("python_executable") or "python"
    return clean


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


def _clean_box(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(item) for item in value]
    except Exception:
        return None
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


class ExternalBlinkBackendRunner:
    def __init__(self, project_manager, backend_config=None, runs_root=None):
        self.project_manager = project_manager
        self.backend_config = sanitize_external_blink_config(backend_config or {})
        project_path = getattr(project_manager, "current_project_path", "") or os.getcwd()
        project_dir = os.path.dirname(os.path.abspath(project_path)) if os.path.splitext(project_path)[1] else os.path.abspath(project_path)
        self.runs_root = os.path.abspath(runs_root or os.path.join(project_dir, "external_blink_runs"))

    def create_run_dir(self, action):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(self.runs_root, f"{timestamp}_{_safe_id(action)}_{_safe_id(self.backend_config.get('backend_id'))}")
        os.makedirs(os.path.join(run_dir, "predictions"), exist_ok=True)
        os.makedirs(os.path.join(run_dir, "logs"), exist_ok=True)
        os.makedirs(os.path.join(run_dir, "model"), exist_ok=True)
        return run_dir

    def build_predict_contract(
        self,
        *,
        run_dir,
        image_path,
        parent_part,
        child_part,
        parent_box,
        prediction_json="",
        model_manifest="",
    ):
        project_path = os.path.abspath(getattr(self.project_manager, "current_project_path", "") or "")
        prediction_json = prediction_json or os.path.join(run_dir, "predictions", "blink_prediction.json")
        model_manifest = model_manifest or self.backend_config.get("model_manifest", "")
        if model_manifest:
            model_manifest = self._format_template(model_manifest, run_dir, "")
        return {
            "schema_version": EXTERNAL_BLINK_CONTRACT_SCHEMA,
            "action": "predict_child",
            "backend_id": self.backend_config.get("backend_id"),
            "project_json": project_path,
            "image_path": os.path.abspath(str(image_path or "")),
            "parent_part": str(parent_part or ""),
            "child_part": str(child_part or ""),
            "parent_box": [float(v) for v in _clean_box(parent_box) or [0.0, 0.0, 1.0, 1.0]],
            "prediction_json": os.path.abspath(prediction_json),
            "model_manifest": os.path.abspath(model_manifest) if model_manifest else "",
            "run_dir": os.path.abspath(run_dir),
            "log_dir": os.path.join(run_dir, "logs"),
            "safety": {
                "output_is_reviewable_draft": True,
                "do_not_write_manual_truth": True,
            },
        }

    def run_predict_child(self, *, image_path, parent_part, child_part, parent_box, model_manifest=""):
        run_dir = self.create_run_dir("predict_child")
        prediction_json = os.path.join(run_dir, "predictions", f"{_safe_id(child_part)}.prediction.json")
        contract = self.build_predict_contract(
            run_dir=run_dir,
            image_path=image_path,
            parent_part=parent_part,
            child_part=child_part,
            parent_box=parent_box,
            prediction_json=prediction_json,
            model_manifest=model_manifest,
        )
        contract_path = os.path.join(run_dir, "contract.json")
        _write_json(contract_path, contract)
        command = self.backend_config.get("predict_command", "").strip()
        if not command:
            raise ValueError("external_blink_predict_command_missing")
        self._run_command(command, contract_path, run_dir, "predict_child")

        prediction = _read_json(prediction_json)
        result = external_blink_prediction_to_result(prediction, expected_child=child_part)
        summary = {
            "run_dir": run_dir,
            "contract_json": contract_path,
            "prediction_json": prediction_json,
            "prediction": prediction,
            "result": result,
        }
        _write_json(os.path.join(run_dir, "logs", "run_summary.json"), summary)
        return summary

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
            raise RuntimeError(f"external_blink_backend_{action}_failed:{result.returncode}:{stderr_path}")
        return result.returncode


def external_blink_prediction_to_result(prediction, expected_child=""):
    if not isinstance(prediction, dict):
        raise ValueError("external_blink_prediction_not_object")
    if prediction.get("schema_version") != EXTERNAL_BLINK_PREDICTION_SCHEMA:
        raise ValueError(f"invalid_external_blink_prediction_schema:{prediction.get('schema_version')}")
    child = str(prediction.get("child_part") or "").strip()
    expected = str(expected_child or "").strip()
    if expected and child and child != expected:
        raise ValueError(f"external_blink_child_mismatch:{child}!={expected}")
    box = _clean_box(prediction.get("box"))
    if not box:
        raise ValueError("external_blink_prediction_box_invalid")
    score = prediction.get("score", prediction.get("confidence", 0.0))
    try:
        score = float(score)
    except Exception:
        score = 0.0
    result = {
        "box": box,
        "confidence": score,
        "backend": "external_blink",
        "model_id": str(prediction.get("model_id") or ""),
    }
    if isinstance(prediction.get("polygon"), list):
        result["polygon"] = prediction.get("polygon")
    return result
