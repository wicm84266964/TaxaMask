import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from .file_integrity import TREE_ALGORITHM, compute_fingerprint
from .safe_io import atomic_write_json
from .training_run_2d import DEFAULT_TRAINING_SEED, prepare_2d_training_run


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
    atomic_write_json(path, payload, indent=2)


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

    def _write_training_snapshot(self, prepared):
        snapshot_root = os.path.join(prepared.run.run_dir, "training_snapshot")
        images_root = os.path.join(snapshot_root, "images")
        os.makedirs(images_root, exist_ok=False)
        database_path = os.path.join(snapshot_root, "training_snapshot.sqlite")
        connection = sqlite3.connect(database_path)
        try:
            connection.executescript(
                """
                PRAGMA journal_mode = DELETE;
                PRAGMA synchronous = FULL;
                CREATE TABLE snapshot_meta (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    schema_version TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    data_version_id TEXT NOT NULL
                );
                CREATE TABLE training_samples (
                    image_uid TEXT PRIMARY KEY,
                    partition TEXT NOT NULL CHECK (partition IN ('train', 'validation')),
                    image_relative_path TEXT NOT NULL,
                    manual_truth_json TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT INTO snapshot_meta VALUES (1, ?, ?, ?)",
                (
                    "taxamask_external_training_snapshot_v1",
                    prepared.dataset["project_id"],
                    prepared.dataset["data_version_id"],
                ),
            )
            selected_paths = {
                str(path)
                for path, _entry in (
                    prepared.locator_train_records
                    + prepared.locator_validation_records
                    + prepared.parts_train_records
                    + prepared.parts_validation_records
                )
            }
            for image_path in sorted(selected_paths):
                uid = prepared.dataset["sample_uid_by_path"][image_path]
                suffix = Path(image_path).suffix.lower() or ".img"
                relative = f"images/{uid}{suffix}"
                target = os.path.join(snapshot_root, *relative.split("/"))
                shutil.copy2(image_path, target)
                label = prepared.dataset["label_snapshots_by_uid"][uid]
                connection.execute(
                    "INSERT INTO training_samples VALUES (?, ?, ?, ?)",
                    (
                        uid,
                        prepared.partition_by_uid[uid],
                        relative,
                        json.dumps(
                            label,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    ),
                )
            connection.commit()
        finally:
            connection.close()
        self._training_snapshot_root = snapshot_root
        self._training_snapshot_expected = compute_fingerprint(
            snapshot_root, TREE_ALGORITHM
        )
        return database_path

    def _verify_training_snapshot(self, prepared, snapshot_path):
        if os.path.abspath(snapshot_path) != os.path.join(
            self._training_snapshot_root, "training_snapshot.sqlite"
        ):
            raise ValueError("external_training_snapshot_path_changed")
        observed = compute_fingerprint(
            self._training_snapshot_root, TREE_ALGORITHM
        )
        if observed.get("digest") != self._training_snapshot_expected.get("digest"):
            raise ValueError("external_training_snapshot_modified")
        with sqlite3.connect(snapshot_path) as connection:
            rows = connection.execute(
                "SELECT image_uid, partition FROM training_samples"
            ).fetchall()
        expected = sorted(prepared.partition_by_uid.items())
        if sorted((str(uid), str(partition)) for uid, partition in rows) != expected:
            raise ValueError("external_training_snapshot_split_mismatch")

    def _manifest_weight_paths(self, manifest_path, manifest):
        raw = manifest.get("weights")
        values = list(raw.values()) if isinstance(raw, dict) else list(raw or [])
        if not values:
            raise ValueError("external_model_weights_missing")
        root = os.path.dirname(os.path.abspath(manifest_path))
        paths = []
        for value in values:
            relative = str(value or "").replace(os.sep, "/")
            if (
                not relative
                or os.path.isabs(relative)
                or relative.startswith("../")
                or "/../" in relative
            ):
                raise ValueError("external_model_weight_path_invalid")
            path = os.path.abspath(os.path.join(root, *relative.split("/")))
            if os.path.commonpath([root, path]) != root or not os.path.isfile(path):
                raise ValueError("external_model_weight_missing")
            paths.append(path)
        return paths

    def build_contract(self, action, run_dir, image_path="", prediction_json="", model_manifest="", training_snapshot_sqlite="", effective_config=None):
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
            "project_json": "" if training_snapshot_sqlite else project_path,
            "training_snapshot_sqlite": os.path.abspath(training_snapshot_sqlite) if training_snapshot_sqlite else "",
            "taxonomy": list(self.project_manager.project_data.get("taxonomy", [])),
            "locator_scope": list(self.project_manager.get_locator_scope()),
            "run_dir": os.path.abspath(run_dir),
            "dataset_dir": os.path.join(run_dir, "dataset"),
            "model_dir": os.path.join(run_dir, "model"),
            "image_path": os.path.abspath(image_path) if image_path else "",
            "prediction_json": os.path.abspath(prediction_json) if prediction_json else "",
            "model_manifest": os.path.abspath(model_manifest),
            "log_dir": os.path.join(run_dir, "logs"),
            "effective_config": dict(effective_config or {}),
        }

    def run_prepare_and_train(self):
        profile = self.project_manager.get_active_model_profile()
        parent = profile.get("parent_backend", {}) if isinstance(profile, dict) else {}
        params = parent.get("train_params", {}) if isinstance(parent, dict) else {}
        effective_config = {
            "epochs": max(1, int(params.get("epochs", 5))),
            "batch_size": max(1, int(params.get("batch", 4))),
            "learning_rate": float(params.get("lr", 1e-4)),
            "weight_decay": float(params.get("weight_decay", 1e-4)),
            "random_seed": DEFAULT_TRAINING_SEED,
            "input_resolution": [512, 512],
            "preprocessing": {
                "dataset_adapter": "external_training_snapshot_sqlite_v1",
                "truth_policy": "manual_truth_only",
            },
            "model": {
                "family": str(self.backend_config.get("backend_id") or "external"),
                "version": "external",
                "locator": "external",
                "parts": "external",
            },
            "loss_weights": dict(parent.get("loss_weights") or {}),
            "train_segmenter": True,
        }
        prepared = prepare_2d_training_run(
            self.project_manager,
            runs_root=self.runs_root,
            entrypoint="external_parent_script",
            effective_config=effective_config,
            backend={
                "backend_id": str(self.backend_config.get("backend_id") or "external"),
                "backend_version": "external",
                "adapter_id": "external_backend_runner",
                "adapter_version": "1.0",
            },
            include_parts=True,
            seed=DEFAULT_TRAINING_SEED,
        )
        run = prepared.run
        run_dir = run.run_dir
        for child in ("dataset", "model", "predictions", "logs"):
            os.makedirs(os.path.join(run_dir, child), exist_ok=True)
        try:
            snapshot_path = self._write_training_snapshot(prepared)
            prepare_contract = self.build_contract(
                "prepare_dataset",
                run_dir,
                training_snapshot_sqlite=snapshot_path,
                effective_config=effective_config,
            )
            prepare_contract_path = os.path.join(run_dir, "prepare_contract.json")
            _write_json(prepare_contract_path, prepare_contract)

            prepare_command = self.backend_config.get("prepare_dataset_command", "").strip()
            if prepare_command:
                self._run_command(prepare_command, prepare_contract_path, run_dir, "prepare_dataset")

            train_contract = self.build_contract(
                "train",
                run_dir,
                model_manifest=prepare_contract["model_manifest"],
                training_snapshot_sqlite=snapshot_path,
                effective_config=effective_config,
            )
            train_contract_path = os.path.join(run_dir, "contract.json")
            _write_json(train_contract_path, train_contract)
            train_command = self.backend_config.get("train_command", "").strip()
            if not train_command:
                raise ValueError("external_train_command_missing")
            self._run_command(train_command, train_contract_path, run_dir, "train")
            self._verify_training_snapshot(prepared, snapshot_path)

            manifest_path = train_contract["model_manifest"]
            manifest = _read_json(manifest_path)
            if manifest.get("schema_version") != EXTERNAL_MODEL_MANIFEST_SCHEMA:
                raise ValueError("external_model_manifest_schema_invalid")
            if manifest.get("effective_config") != effective_config:
                raise ValueError("external_effective_config_missing_or_mismatch")
            weight_paths = self._manifest_weight_paths(manifest_path, manifest)
            run.register_path_base("export_root", run_dir)
            for index, weight_path in enumerate(weight_paths, start=1):
                run.add_artifact(
                    artifact_id=f"external_checkpoint_{index:03d}",
                    role="output_weights",
                    path=weight_path,
                    path_base="export_root",
                    media_type="application/octet-stream",
                )
            run.add_artifact(
                artifact_id="external_model_manifest",
                role="model_manifest",
                path=manifest_path,
                path_base="export_root",
                media_type="application/json",
            )
            run.add_artifact(
                artifact_id="external_training_dataset",
                role="training_dataset_snapshot",
                path=self._training_snapshot_root,
                path_base="export_root",
                media_type="application/x-directory",
            )
            summary = {
                "run_id": run.run_id,
                "run_dir": run_dir,
                "contract_json": train_contract_path,
                "model_manifest": manifest_path,
                "manifest": manifest,
            }
            summary_path = os.path.join(run_dir, "logs", "run_summary.json")
            _write_json(summary_path, summary)
            run.add_artifact(
                artifact_id="training_report",
                role="training_report",
                path=summary_path,
                path_base="export_root",
                media_type="application/json",
            )
            run.succeed()
            return summary
        except BaseException as exc:
            if run.status in {"pending", "running"}:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    run.interrupt(stage="external_training")
                else:
                    run.fail(exc, stage="external_training")
            raise

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
