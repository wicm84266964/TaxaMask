"""Versioned external model contracts for multiple instances of the same class."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from .external_backend import sanitize_external_backend_config
from .external_command import render_external_command
from .instance_project import decode_mask, encode_mask, mask_box, digest, uid
from .safe_io import atomic_write_json

CONTRACT_SCHEMA = "taxamask-instance-backend-v1"
PREDICTION_SCHEMA = "taxamask-instance-prediction-v1"
MODEL_SCHEMA = "taxamask-instance-external-model-v1"


def category_hash(categories):
    # Renames are display changes. Model semantics are tied to stable IDs and order.
    ids = sorted(c["id"] for c in categories)
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


def sanitize_instance_backend(value):
    value = value if isinstance(value, dict) else {}
    clean = sanitize_external_backend_config(value)
    clean["timeout_seconds"] = max(1, min(604800, int(value.get("timeout_seconds", 86400))))
    clean["dataset_format"] = str(value.get("dataset_format", "yolo"))
    if clean["dataset_format"] not in {"coco", "yolo"}:
        raise ValueError("外部数据格式仅支持 COCO 或 YOLO；分类使用分类目录")
    clean["tasks"] = list(value.get("tasks", ["detect", "segment", "classify"]))
    if not clean["tasks"] or set(clean["tasks"]) - {"detect", "segment", "classify"}:
        raise ValueError("外部模型任务能力无效")
    params = value.get("train_params", {})
    if not isinstance(params, dict):
        raise ValueError("训练参数必须为 JSON 对象")
    json.dumps(params, allow_nan=False)
    clean["train_params"] = params
    for field in ("prepare_dataset_command", "train_command", "predict_command"):
        command = clean[field]
        if command and not any(tag in command for tag in ("{contract}", "{contract_json}")):
            raise ValueError(f"{field} 必须包含 {{contract}} 或 {{contract_json}}")
        render_external_command(command, python=clean["python_executable"], contract="contract.json", contract_json="contract.json", run_dir="run")
    return clean


def run_command(settings, command_key, contract_file, run_dir, *, cancel_check=None):
    settings = sanitize_instance_backend(settings)
    command = render_external_command(settings[command_key], python=settings["python_executable"],
                                      contract=str(contract_file), contract_json=str(contract_file), run_dir=str(run_dir))
    if not command:
        raise ValueError("尚未配置外部命令：" + command_key)
    logs = Path(run_dir) / "logs"
    logs.mkdir(exist_ok=True)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with (logs / f"{command_key}_stdout.log").open("w", encoding="utf-8") as stdout, (logs / f"{command_key}_stderr.log").open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=run_dir, shell=False, stdout=stdout, stderr=stderr, creationflags=creationflags)
        started = time.monotonic()
        try:
            while process.poll() is None:
                if cancel_check and cancel_check():
                    raise InterruptedError("外部模型任务已取消")
                if time.monotonic() - started > settings["timeout_seconds"]:
                    raise TimeoutError("外部模型任务超时")
                time.sleep(.1)
            if process.returncode:
                raise RuntimeError(f"外部模型失败（退出码 {process.returncode}），详见 {logs}")
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def validate_prediction(payload, *, project_id, revision, image, categories, task):
    if not isinstance(payload, dict) or payload.get("schema_version") != PREDICTION_SCHEMA:
        raise ValueError("外部实例预测 schema 不匹配；旧部位字典协议不能用于多个体")
    expected = {"project_id": project_id, "revision": revision, "image_uid": image["id"],
                "image_hash": image["hash"], "category_map_hash": category_hash(categories), "task": task}
    if any(payload.get(k) != v for k, v in expected.items()):
        raise ValueError("预测结果与项目、类别、图像或请求修订不匹配")
    records = payload.get("instances")
    if not isinstance(records, list) or len(records) > 10000:
        raise ValueError("instances 必须为最多一万个对象的数组")
    allowed = {c["id"] for c in categories}
    results, seen = [], set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("候选必须为对象")
        key = record.get("proposal_id")
        if not isinstance(key, str) or not key or key in seen:
            raise ValueError("候选 ID 缺失或重复")
        seen.add(key)
        if record.get("category_id") not in allowed:
            raise ValueError("预测包含未知物种类别")
        score = float(record.get("score", 0))
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("候选置信度无效")
        result = {"proposal_id": key, "category_id": record["category_id"], "score": score, "task": task, "source": "external_model"}
        if task != "classify":
            box = record.get("bbox_xyxy")
            if not isinstance(box, list) or len(box) != 4 or not all(math.isfinite(float(v)) for v in box):
                raise ValueError("外部预测框无效")
            x1, y1, x2, y2 = map(float, box)
            if not (0 <= x1 < x2 <= image["width"] and 0 <= y1 < y2 <= image["height"]):
                raise ValueError("外部预测框超出图像边界")
            result["box"] = [x1, y1, x2, y2]
            if task == "segment":
                rle = record.get("mask_rle")
                if not isinstance(rle, dict) or rle.get("size") != [image["height"], image["width"]]:
                    raise ValueError("分割候选必须包含与图像同尺寸的 RLE")
                result["mask"] = encode_mask(decode_mask(rle))
                result["box"] = mask_box(result["mask"])
        results.append(result)
    if task == "classify" and len(results) != 1:
        raise ValueError("单体分类请求必须返回一个类别建议")
    return results


def external_predict(settings, *, run_root, project_id, revision, image, image_path, categories, task, instance_id=None, cancel_check=None):
    from .instance_model_jobs import run_model_job
    return run_model_job(Path(run_root).resolve().parent, lambda: _external_predict(settings, run_root=run_root,
        project_id=project_id, revision=revision, image=image, image_path=image_path, categories=categories,
        task=task, instance_id=instance_id, cancel_check=cancel_check))


def _external_predict(settings, *, run_root, project_id, revision, image, image_path, categories, task, instance_id=None, cancel_check=None):
    settings = sanitize_instance_backend(settings)
    if task not in settings["tasks"]:
        raise ValueError("外部模型未声明支持此任务")
    if digest(image_path) != image["hash"]:
        raise ValueError("预测图像已变化，请重新读取项目")
    manifest_path = Path(settings["model_manifest"]).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MODEL_SCHEMA or manifest.get("task") != task or manifest.get("category_map_hash") != category_hash(categories):
        raise ValueError("外部模型清单任务或类别映射不匹配")
    weights = (manifest_path.parent / manifest["weights"]).resolve()
    if not weights.is_relative_to(manifest_path.parent) or digest(weights) != manifest["weights_hash"]:
        raise ValueError("外部模型权重路径或指纹无效")
    run_dir = Path(run_root).resolve() / uid("external_predict")
    run_dir.mkdir(parents=True)
    result_path = run_dir / "prediction.json"
    contract = {"schema_version": CONTRACT_SCHEMA, "action": "predict", "task": task, "project_id": project_id,
                "revision": revision, "image_uid": image["id"], "image_hash": image["hash"],
                "image_path": str(image_path), "width": image["width"], "height": image["height"], "instance_id": instance_id,
                "categories": categories, "category_map_hash": category_hash(categories), "model_manifest": str(manifest_path),
                "prediction_json": str(result_path), "run_dir": str(run_dir)}
    contract_path = run_dir / "contract.json"
    atomic_write_json(contract_path, contract)
    run_command(settings, "predict_command", contract_path, run_dir, cancel_check=cancel_check)
    if result_path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("预测结果超过大小限制")
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    return validate_prediction(payload, project_id=project_id, revision=revision, image=image, categories=categories, task=task)


def external_train(config):
    from .instance_training import verify_export
    settings = sanitize_instance_backend(config["external_backend"])
    task, folder, run_dir = config["task"], Path(config["dataset"]), Path(config["run_dir"])
    if task not in settings["tasks"]:
        raise ValueError("外部模型未声明支持此任务")
    verify_export(folder, task)
    snapshot = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
    categories = snapshot["categories"]
    contract = {"schema_version": CONTRACT_SCHEMA, "action": "train", "task": task,
                "project_id": snapshot["project_id"], "revision": snapshot["revision"], "category_map_hash": category_hash(categories),
                "categories": categories, "dataset_dir": str(folder), "snapshot_json": str(folder / "snapshot.json"),
                "initial_weights": config["weights"], "run_dir": str(run_dir), "model_manifest": str(run_dir / "model_manifest.json"),
                "effective_config": config["effective_config"], "train_params": settings["train_params"]}
    path = run_dir / "external_contract.json"
    atomic_write_json(path, contract)
    cancel = lambda: (run_dir / "CANCEL_REQUESTED").exists()
    if settings["prepare_dataset_command"]:
        prepare = dict(contract, action="prepare")
        prepare_path = run_dir / "prepare_contract.json"
        atomic_write_json(prepare_path, prepare)
        run_command(settings, "prepare_dataset_command", prepare_path, run_dir, cancel_check=cancel)
        # The prepared dataset is a derived output; immutable snapshot must remain intact.
        verify_export(folder, task)
    run_command(settings, "train_command", path, run_dir, cancel_check=cancel)
    manifest = json.loads((run_dir / "model_manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != MODEL_SCHEMA or manifest.get("task") != task
            or manifest.get("category_map_hash") != category_hash(categories)
            or manifest.get("effective_config") != config["effective_config"]):
        raise ValueError("外部训练清单缺少匹配的任务、类别或有效参数记录")
    weights = (run_dir / manifest["weights"]).resolve()
    if not weights.is_relative_to(run_dir.resolve()) or digest(weights) != manifest.get("weights_hash"):
        raise ValueError("外部权重必须位于本次运行目录并通过指纹检查")
    return dict(manifest, weights=str(weights))
