"""Ultralytics instance task adapter, executed in a cancellable child process."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .instance_project import digest, encode_mask
from .safe_io import atomic_write_json


def verify_export(folder, task):
    folder = Path(folder).resolve()
    complete = json.loads((folder / "COMPLETE.json").read_text(encoding="utf-8"))
    if complete["task"] != task or (folder / "INCOMPLETE.json").exists():
        raise ValueError("数据集任务不匹配或导出不完整")
    if digest(folder / "snapshot.json") != complete["snapshot_hash"]:
        raise ValueError("训练快照已变更")
    report = json.loads((folder / "export_report.json").read_text(encoding="utf-8"))
    if not report["coverage"]["train"] or not report["coverage"]["val"]:
        raise ValueError("训练和验证集合均需有已确认对象；请补充独立来源图片或调整划分")
    missing = set(report["coverage"]["val"]) - set(report["coverage"]["train"])
    if missing:
        raise ValueError("验证集中存在训练集没有的类别")
    if task == "classify":
        categories = json.loads((folder / "category_map.json").read_text(encoding="utf-8"))
        if {c["id"] for c in categories} - set(report["coverage"]["train"]):
            raise ValueError("分类训练要求每个声明类别均有训练样本，请补充标注或移除未使用类别")
    inventory = json.loads((folder / "input_fingerprints.json").read_text(encoding="utf-8"))
    for relative, expected in inventory.items():
        target = (folder / relative).resolve()
        if not target.is_relative_to(folder) or digest(target) != expected:
            raise ValueError("训练输入已变更：" + relative)
    return complete


def train(config, model_factory=None):
    if model_factory is None:
        from ultralytics import YOLO
        model_factory = YOLO
    folder, run = Path(config["dataset"]), Path(config["run_dir"])
    task = config["task"]
    verify_export(folder, task)
    categories = json.loads((folder / "category_map.json").read_text(encoding="utf-8"))
    model = model_factory(config["weights"], task=task)
    if model.task != task:
        raise ValueError("初始模型任务不匹配")
    cancel_path = run / "CANCEL_REQUESTED"
    if hasattr(model, "add_callback"):
        def check_cancel(trainer):
            if cancel_path.exists():
                raise InterruptedError("用户取消训练")
        model.add_callback("on_train_batch_end", check_cancel)
        model.add_callback("on_train_epoch_end", check_cancel)
    # Some installations retain save_dir in model overrides; force the run-local path.
    save_dir = (run / "model").resolve()
    if save_dir.exists():
        raise ValueError("训练输出目录已存在，必须创建新的运行目录")
    data = str(folder / "dataset") if task == "classify" else str(folder / "dataset" / "data.yaml")
    result = model.train(data=data, epochs=config["epochs"], batch=config["batch"], imgsz=config["imgsz"],
                         device=config["device"], workers=0, project=str(run), name="model", save_dir=str(save_dir), exist_ok=False,
                         seed=20261102, pretrained=Path(config["weights"]).suffix == ".pt", plots=False,
                         optimizer="SGD", lr0=.01, weight_decay=.0005)
    weights = Path(model.trainer.best)
    if not weights.resolve().is_relative_to(run.resolve()):
        raise ValueError("训练后端输出越过本次运行目录")
    if not weights.is_file():
        raise ValueError("训练结束但未产生可用权重")
    # Model names must equal stable category IDs, never guessed from equal class counts.
    expected = {c["id"] for c in categories}
    names = dict(model.names)
    if set(names.values()) != expected:
        raise ValueError("模型类别映射与项目类别不一致")
    manifest = {"schema_version": "taxamask-instance-model-v1", "task": task,
                "weights": str(weights.resolve()), "weights_hash": digest(weights),
                "names": names, "categories": categories,
                "metrics": {str(k): float(v) for k, v in getattr(result, "results_dict", {}).items()},
                "dataset_snapshot_hash": digest(folder / "snapshot.json")}
    atomic_write_json(run / "model_manifest.json", manifest)
    return manifest


def predict(manifest_path, image_path, category_ids, *, device="cpu", model_factory=None, project_root=None):
    if project_root is not None:
        from .instance_model_jobs import run_model_job
        return run_model_job(project_root, lambda: predict(manifest_path, image_path, category_ids,
                             device=device, model_factory=model_factory))
    if model_factory is None:
        from ultralytics import YOLO
        model_factory = YOLO
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "taxamask-instance-model-v1":
        raise ValueError("不支持的实例模型清单")
    if digest(manifest["weights"]) != manifest["weights_hash"]:
        raise ValueError("权重内容与登记记录不一致")
    names = {int(k): v for k, v in manifest["names"].items()}
    if not set(names.values()).issubset(set(category_ids)):
        raise ValueError("模型类别与当前项目不兼容")
    model = model_factory(manifest["weights"], task=manifest["task"])
    if model.task != manifest["task"] or dict(model.names) != names:
        raise ValueError("模型任务或类别顺序与清单不一致")
    proposals = []
    for result in model.predict(str(image_path), device=device, verbose=False, retina_masks=True):
        if manifest["task"] == "classify":
            proposals.append({"category_id": names[int(result.probs.top1)], "score": float(result.probs.top1conf), "task": "classify"})
            continue
        if result.boxes is None:
            continue
        for i, box in enumerate(result.boxes):
            item = {"box": box.xyxy[0].cpu().tolist(), "category_id": names[int(box.cls[0])], "score": float(box.conf[0]), "task": manifest["task"]}
            if manifest["task"] == "segment":
                if result.masks is None:
                    raise ValueError("分割模型未返回掩膜")
                item["mask"] = encode_mask(result.masks.data[i].cpu().numpy())
            proposals.append(item)
    return proposals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    from .instance_model_jobs import run_model_job
    run_model_job(Path(config["run_dir"]).resolve().parent.parent, lambda: execute_training(config))


def execute_training(config):
    from .instance_training_record import prepare_record
    recorder, run, initial = prepare_record(config)
    try:
        config["weights"] = str(initial)
        config["effective_config"] = run.record["effective_config"]
        if config.get("external_backend"):
            from .instance_external_backend import external_train
            manifest = external_train(config)
        else:
            manifest = train(config)
        run.add_artifact(artifact_id="trained_weights", role="output_weights", path=manifest["weights"],
                         path_base="managed_model_root", base_dir=config["run_dir"])
        run.add_artifact(artifact_id="model_manifest", role="model_manifest", path=Path(config["run_dir"]) / "model_manifest.json",
                         path_base="managed_model_root", base_dir=config["run_dir"])
        verify_export(config["dataset"], config["task"])
        run.succeed()
    except Exception as exc:
        if isinstance(exc, InterruptedError):
            run.cancel()
        else:
            run.fail(exc)
        raise
    finally:
        run.close()


if __name__ == "__main__":
    main()
