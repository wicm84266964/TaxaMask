"""Explicit opt-in CPU smoke: python tests/instance_training_smoke.py [output-dir]."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image, ImageDraw
import ultralytics

from AntSleap.core.instance_project import InstanceProject, encode_mask
from AntSleap.core.instance_dataset import export_dataset
from AntSleap.core.instance_training import train, predict
from AntSleap.core.instance_training_record import prepare_record


def main():
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    project = InstanceProject.create(root / "project")
    try:
        category = project.category("synthetic_object")
        for n in range(12):
            path = root / f"synthetic_{n}.png"
            image = Image.new("RGB", (64, 64), (30 + n * 4, 40, 50))
            ImageDraw.Draw(image).rectangle((8, 8, 26, 34), fill=(220, 60, 40))
            image.save(path)
            ids, errors = project.import_images([path])
            assert not errors
            mask = np.zeros((64, 64), np.uint8)
            mask[8:35, 8:27] = 1
            key = project.put_instance(ids[0], category, mask=encode_mask(mask))
            project.batch([key], "confirm")
            project.review_image(ids[0], "complete")
        results = {}
        for task, suffix in [("detect", ""), ("segment", "-seg"), ("classify", "-cls")]:
            output, report = export_dataset(project, root / "exports", task=task, format="classification" if task == "classify" else "yolo")
            model_yaml = Path(ultralytics.__file__).parent / "cfg" / "models" / "11" / f"yolo11{suffix}.yaml"
            config = {"task": task, "weights": str(model_yaml), "dataset": str(output), "run_dir": str(root / task),
                      "epochs": 1, "batch": 2, "imgsz": 64, "device": "cpu"}
            recorder, run, initial = prepare_record(config)
            try:
                config["weights"] = str(initial)
                manifest = train(config)
                run.add_artifact(artifact_id="weights", role="output_weights", path=manifest["weights"], path_base="managed_model_root", base_dir=config["run_dir"])
                run.succeed()
                proposals = predict(Path(config["run_dir"]) / "model_manifest.json", root / "synthetic_0.png", [category])
                results[task] = {"status": run.status, "prediction_count": len(proposals), "weights_present": Path(manifest["weights"]).is_file()}
            except Exception as exc:
                if run.status in {"pending", "running"}:
                    run.fail(exc)
                raise
            finally:
                run.close()
        (root / "smoke_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps(results))
    finally:
        project.close()


if __name__ == "__main__":
    main()
