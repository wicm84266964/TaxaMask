"""Bridge instance snapshots into the existing verified training-run ledger."""
from pathlib import Path
import json
import shutil

from .integrity_manifest_service import IntegrityManifestService, build_file_entry
from .training_run_recorder import TrainingRunRecorder, utc_now
from .safe_io import atomic_write_json


def prepare_record(config):
    folder = Path(config["dataset"])
    snapshot = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
    version = "instance_revision_" + str(snapshot["revision"])
    dataset_id = "dataset_" + snapshot["project_id"]
    external = config.get("external_backend")
    from .instance_external_backend import sanitize_instance_backend
    external = sanitize_instance_backend(external) if external else None
    effective_config = {"epochs": config["epochs"], "batch_size": config["batch"], "learning_rate": .01,
                        "weight_decay": .0005, "random_seed": 20261102, "input_resolution": [config["imgsz"], config["imgsz"]],
                        "preprocessing": {"adapter": "external_instances" if external else "ultralytics"},
                        "model": {"family": external["backend_id"] if external else "ultralytics_" + config["task"], "version": "1"},
                        "loss_weights": {}, "persist_weights": True}
    if external:
        effective_config.update(external["train_params"])
    recorder = TrainingRunRecorder(Path(config["run_dir"]) / "ledger")
    run = recorder.create_pending(
        "species_instances_" + config["task"],
        project_ref={"project_kind": "species_instances_2d", "project_id": snapshot["project_id"], "project_data_version_id": version},
        dataset_ref={"dataset_id": dataset_id, "data_version_id": version, "source_kind": "project", "trusted_label_policy": "human_confirmed_only"},
        effective_config=effective_config,
        backend={"backend_id": external["backend_id"] if external else "ultralytics", "backend_version": "1", "adapter_id": "taxamask_instances", "adapter_version": "1"})
    try:
        run.register_path_base("export_root", folder)
        entries = []
        file_ids = {}
        for n, path in enumerate(sorted((folder / "dataset").rglob("*"))):
            if not path.is_file():
                continue
            relative = path.relative_to(folder).as_posix()
            file_id = f"dataset_file_{n}"
            file_ids[relative] = file_id
            role = "training_image" if path.suffix.lower() in {".png", ".jpg", ".jpeg"} else "human_confirmed_label"
            entries.append(build_file_entry(file_id, role, "export_root", relative, version))
        entries.append(build_file_entry("snapshot", "human_confirmed_label", "export_root", "snapshot.json", version))
        entries.append(build_file_entry("category_map", "label_schema", "export_root", "category_map.json", version))
        initial = Path(run.run_dir) / ("initial" + Path(config["weights"]).suffix)
        shutil.copy2(config["weights"], initial)
        entries.append(build_file_entry("initial_weights", "initial_weights", "run_root", initial.name, version))
        config_path = Path(run.run_dir) / "effective_config.json"
        atomic_write_json(config_path, run.record["effective_config"])
        entries.append(build_file_entry("effective_config", "training_config", "run_root", config_path.name, version))
        partitions = json.loads((folder / "split_manifest.json").read_text(encoding="utf-8"))
        provenance = [json.loads(line) for line in (folder / "provenance.jsonl").read_text(encoding="utf-8").splitlines()]
        assignments = []
        for relative, file_id in file_ids.items():
            path = Path(relative)
            if path.suffix != ".png":
                continue
            if config["task"] == "classify":
                ref = next(p for p in provenance if p["instance_id"] == path.stem)
                image_id = ref["image_id"]
                truth_id = file_id + "_truth"
                truth_path = Path(run.run_dir) / f"{truth_id}.json"
                atomic_write_json(truth_path, {"instance_id": path.stem, "category_id": path.parent.name})
                entries.append(build_file_entry(truth_id, "human_confirmed_label", "run_root", truth_path.name, version))
            else:
                image_id = path.stem
                truth_relative = relative.replace("/images/", "/labels/")[:-4] + ".txt"
                truth_id = file_ids.get(truth_relative)
                if truth_id is None:
                    truth_id = file_id + "_truth"
                    truth_path = Path(run.run_dir) / f"{truth_id}.json"
                    atomic_write_json(truth_path, [r for r in snapshot["instances"] if r["image_id"] == image_id])
                    entries.append(build_file_entry(truth_id, "human_confirmed_label", "run_root", truth_path.name, version))
            split = partitions[image_id]
            assignments.append({"sample_id": file_id, "partition": "validation" if split == "val" else split,
                                "group_id": image_id, "input_file_ids": [file_id, truth_id]})
        integrity = Path(run.run_dir) / "integrity_manifest.json"
        service = IntegrityManifestService(integrity, {"run_root": run.run_dir, "export_root": folder})
        service.create_manifest(run.run_id, entries)
        service.capture_expected_fingerprints()
        service.verify_manifest()
        stamp = utc_now()
        split_path = Path(run.run_dir) / "split_manifest.json"
        atomic_write_json(split_path, {"schema_version": "taxamask_training_split_v1", "split_id": "instance_split", "run_id": run.run_id,
                                      "status": "verified", "created_at": stamp, "started_at": stamp, "finished_at": stamp,
                                      "dataset_id": dataset_id, "strategy": {"name": "source_group_holdout", "version": "v1", "seed": 20261102, "validation_ratio": .1},
                                      "assignments": assignments, "error": None})
        run.attach_integrity_manifest(integrity)
        run.attach_split_manifest(split_path)
        run.mark_running()
        return recorder, run, initial
    except Exception as exc:
        run.fail(exc, stage="preflight")
        run.close()
        raise
