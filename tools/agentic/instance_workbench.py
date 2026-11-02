"""Agent CLI for instance projects; all annotations submitted here remain drafts."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from AntSleap.core.instance_project import InstanceProject, uid
from AntSleap.core.instance_agent import capabilities, inspect_project, validate_project, submit_request, MAX_REQUEST_BYTES
from AntSleap.core.instance_dataset import export_dataset
from AntSleap.core.safe_io import atomic_write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["capabilities", "inspect", "validate", "export", "propose_instances", "train", "predict"])
    parser.add_argument("--project")
    parser.add_argument("--request")
    parser.add_argument("--out")
    parser.add_argument("--task", choices=["detect", "segment", "classify"], default="detect")
    parser.add_argument("--format", choices=["coco", "yolo", "classification"], default="coco")
    parser.add_argument("--weights")
    parser.add_argument("--model-manifest")
    parser.add_argument("--image-id")
    parser.add_argument("--instance-id")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)
    project = None
    try:
        if args.action == "capabilities":
            result = capabilities()
        else:
            if not args.project:
                raise ValueError("需要 --project")
            project = InstanceProject(args.project, readonly=True)
            if args.action == "inspect":
                result = inspect_project(project)
            elif args.action == "validate":
                result = validate_project(project)
            elif args.action == "propose_instances":
                if not args.request or Path(args.request).stat().st_size > MAX_REQUEST_BYTES:
                    raise ValueError("需要大小不超过 16 MiB 的 --request JSON")
                request = json.loads(Path(args.request).read_text(encoding="utf-8"))
                result = submit_request(project, request)
            elif args.action in {"export", "train"}:
                settings = project.settings()
                external = settings.get("external_backend") if settings.get("backend") == "external" else None
                fmt = args.format
                if args.action == "train":
                    fmt = "classification" if args.task == "classify" else external.get("dataset_format", "yolo") if external else "yolo"
                destination, report = export_dataset(project, args.out or project.root / "exports", task=args.task, format=fmt)
                result = {"output": str(destination), "report": report}
                if args.action == "train":
                    from AntSleap.core.instance_training import verify_export
                    if not args.weights or not Path(args.weights).is_file():
                        raise ValueError("训练需要本地 --weights")
                    if min(args.epochs, args.batch, args.imgsz) < 1:
                        raise ValueError("训练参数必须为正数")
                    verify_export(destination, args.task)
                    run_dir = project.root / "runs" / uid("agent_train")
                    run_dir.mkdir(parents=True)
                    config = {"dataset": str(destination), "run_dir": str(run_dir), "task": args.task,
                              "weights": str(Path(args.weights).resolve()), "epochs": args.epochs, "batch": args.batch,
                              "imgsz": args.imgsz, "device": args.device}
                    if external:
                        config["external_backend"] = external
                    atomic_write_json(run_dir / "config.json", config)
                    with (run_dir / "training.log").open("w", encoding="utf-8") as log:
                        subprocess.run([sys.executable, "-m", "AntSleap.core.instance_training", str(run_dir / "config.json")], cwd=ROOT,
                                       stdout=log, stderr=log, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    result = {"status": "succeeded", "model_manifest": str(run_dir / "model_manifest.json"), "run_dir": str(run_dir)}
            else:
                from AntSleap.core.instance_training import predict
                from AntSleap.core.instance_external_backend import external_predict
                from AntSleap.core.instance_project import digest
                from PIL import Image
                if not args.image_id or not args.model_manifest:
                    raise ValueError("预测需要 --image-id 和 --model-manifest")
                image = project.get("images", args.image_id)
                image_path = project.image_path(image)
                manifest = json.loads(Path(args.model_manifest).read_text(encoding="utf-8"))
                task = manifest["task"]
                if task == "classify":
                    if not args.instance_id:
                        raise ValueError("分类预测需要 --instance-id，不能把多个体整图作为单标签样本")
                    record = project.get("instances", args.instance_id)
                    if record["image_id"] != args.image_id:
                        raise ValueError("实例与图像不匹配")
                    crop_dir = project.root / "runs" / uid("agent_predict")
                    crop_dir.mkdir(parents=True)
                    crop = crop_dir / "crop.png"
                    with Image.open(image_path) as im:
                        im.crop(tuple(record["box"])).save(crop)
                    with Image.open(crop) as im:
                        image.update(width=im.width, height=im.height, hash=digest(crop))
                    image_path = crop
                settings = project.settings()
                categories = project.records("categories")
                if settings.get("backend") == "external":
                    external = dict(settings["external_backend"], model_manifest=args.model_manifest)
                    proposals = external_predict(external, run_root=project.root / "runs", project_id=project.project_id,
                                                 revision=project.revision, image=image, image_path=image_path, categories=categories,
                                                 task=task, instance_id=args.instance_id)
                else:
                    proposals = predict(args.model_manifest, image_path, [c["id"] for c in categories], device=args.device, project_root=project.root)
                result = {"project_id": project.project_id, "revision": project.revision, "image_id": args.image_id,
                          "instance_id": args.instance_id, "task": task, "proposals": proposals,
                          "write_policy": "prediction_only_not_applied"}
        if args.out and args.action not in {"export", "train"}:
            atomic_write_json(args.out, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    finally:
        if project:
            project.close()


if __name__ == "__main__":
    raise SystemExit(main())
