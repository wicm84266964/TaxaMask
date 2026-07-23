import argparse
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from AntSleap.core.safe_io import atomic_write_json
from AntSleap.core.tif_backend import (
    TIF_BACKEND_CONTRACT_SCHEMA_VERSION,
    TIF_BACKEND_RESULT_SCHEMA_VERSION,
    TIF_MODEL_MANIFEST_SCHEMA_VERSION,
)
from AntSleap.core.tif_export import export_nnunet_dataset, export_tif_part_nnunet_dataset, read_nifti_volume, remap_label_ids, write_nifti_volume
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar, read_volume_metadata, volume_sidecar_exists, write_volume_sidecar


ADAPTER_ID = "taxamask_tif_nnunet_v2_backend"
MODEL_FAMILY = "nnunet_v2_tif_region"
LEGACY_MODEL_FAMILIES = {"nnunet_v2_part_reslice"}
DEFAULT_DATASET_NAME = "TaxaMaskTifVolumeSegmentation"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_id(value, fallback="item"):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return clean.strip("._") or fallback


def _write_json(path, payload):
    atomic_write_json(path, payload, indent=2, ensure_ascii=False)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return payload


def _result_base(contract, started_at, artifacts=None, metrics=None, warnings=None, errors=None, provenance=None, status="success"):
    return {
        "schema_version": TIF_BACKEND_RESULT_SCHEMA_VERSION,
        "contract_schema_version": TIF_BACKEND_CONTRACT_SCHEMA_VERSION,
        "status": status,
        "action": contract.get("action", ""),
        "backend_id": contract.get("backend_id") or ADAPTER_ID,
        "run_id": contract.get("run_id", ""),
        "artifacts": list(artifacts or []),
        "metrics": metrics if isinstance(metrics, dict) else {"summary": {}, "by_material": {}},
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "provenance": {
            "started_at": started_at,
            "finished_at": _now_iso(),
            "adapter_id": ADAPTER_ID,
            "adapter_mode": "nnunet_v2",
            "run_dir": ".",
            **(provenance if isinstance(provenance, dict) else {}),
        },
    }


def _as_run_relative(contract, path):
    text = str(path or "").strip()
    if not text:
        return ""
    base = os.path.dirname(os.path.abspath(contract["result_json"]))
    try:
        return os.path.relpath(os.path.abspath(text), base).replace("\\", "/")
    except ValueError:
        return os.path.abspath(text)


def _as_manifest_relative(manifest_path, path):
    text = str(path or "").strip()
    if not text:
        return ""
    base = Path(manifest_path).resolve().parent
    try:
        return os.path.relpath(Path(text).resolve(), base).replace("\\", "/")
    except ValueError:
        raise ValueError("model_artifact_must_share_manifest_filesystem")


def _resolve_manifest_path(manifest_path, value):
    text = str(value or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate.resolve()
    return (Path(manifest_path).resolve().parent / candidate).resolve()


def _ensure_contract(contract):
    if contract.get("schema_version") != TIF_BACKEND_CONTRACT_SCHEMA_VERSION:
        raise ValueError(f"invalid_tif_backend_contract_schema:{contract.get('schema_version')}")
    action = str(contract.get("action") or "")
    if action not in {"prepare_dataset", "train", "predict"}:
        raise ValueError(f"unsupported_tif_backend_action:{action}")
    for key in ("run_id", "run_dir", "output_dir", "result_json"):
        if not str(contract.get(key) or "").strip():
            raise ValueError(f"contract_field_missing:{key}")
    return action


def _project_from_contract(contract):
    project_json = str(contract.get("project_json") or "").strip()
    if not project_json:
        raise ValueError("contract_project_json_missing")
    manager = TifProjectManager()
    manager.load_project(project_json)
    return manager


def _part_refs_from_contract(contract, require_label):
    refs = []
    for sample in contract.get("part_samples", []) or []:
        if not isinstance(sample, dict):
            continue
        specimen_id = str(sample.get("specimen_id") or "").strip()
        part_id = str(sample.get("part_id") or "").strip()
        reslice_id = str(sample.get("reslice_id") or "").strip()
        if specimen_id and part_id:
            if require_label and (sample.get("label_volume") or {}).get("role") != "manual_truth":
                raise ValueError(f"manual_truth_required_for_training:{specimen_id}:{part_id}")
            refs.append({"specimen_id": specimen_id, "part_id": part_id, "reslice_id": reslice_id})
    if not refs:
        raise ValueError("contract_part_samples_missing")
    return refs


def _specimen_ids_from_contract(contract, require_label):
    ids = []
    for sample in contract.get("specimens", []) or []:
        if not isinstance(sample, dict):
            continue
        specimen_id = str(sample.get("specimen_id") or "").strip()
        if not specimen_id:
            continue
        if require_label and (sample.get("label_volume") or {}).get("role") != "manual_truth":
            raise ValueError(f"manual_truth_required_for_training:{specimen_id}")
        ids.append(specimen_id)
    if not ids:
        raise ValueError("contract_specimens_missing")
    return ids


def _sample_refs_from_contract(contract, require_label):
    if str(contract.get("input_scope") or "part_reslice") == "top_level_volume":
        return _specimen_ids_from_contract(contract, require_label)
    return _part_refs_from_contract(contract, require_label)


def _dataset_folder_name(dataset_id, dataset_name):
    return f"Dataset{int(dataset_id):03d}_{_safe_id(dataset_name, DEFAULT_DATASET_NAME)}"


def _nnunet_roots(args, contract):
    base = Path(args.nnunet_work_dir or Path(contract["run_dir"]) / "nnunet").resolve()
    raw = Path(args.nnunet_raw).resolve() if args.nnunet_raw else base / "nnUNet_raw"
    preprocessed = Path(args.nnunet_preprocessed).resolve() if args.nnunet_preprocessed else base / "nnUNet_preprocessed"
    results = Path(args.nnunet_results).resolve() if args.nnunet_results else base / "nnUNet_results"
    for path in (raw, preprocessed, results):
        path.mkdir(parents=True, exist_ok=True)
    return raw, preprocessed, results


def _command_env(args, raw_root, preprocessed_root, results_root):
    env = os.environ.copy()
    env["nnUNet_raw"] = str(raw_root)
    env["nnUNet_preprocessed"] = str(preprocessed_root)
    env["nnUNet_results"] = str(results_root)
    env["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    scripts_dir = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    if scripts_dir.exists():
        env["PATH"] = str(scripts_dir) + os.pathsep + env.get("PATH", "")
    return env


def _resolve_executable(command, env):
    text = _strip_shell_quotes(str(command or ""))
    if not text:
        return ""
    if os.path.isabs(text) and os.path.exists(text):
        return text
    if (os.path.sep in text or (os.path.altsep and os.path.altsep in text)) and os.path.exists(text):
        return text
    resolved = shutil.which(text, path=env.get("PATH"))
    if resolved:
        return resolved
    suffixes = (".exe", ".bat", ".cmd") if os.name == "nt" else ("",)
    scripts_dir = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    for suffix in suffixes:
        candidate = scripts_dir / f"{text}{suffix}"
        if candidate.exists():
            return str(candidate)
    return ""


def _missing_command_message(command, env):
    scripts_dir = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    return (
        f"nnunet_command_not_found:{command}; "
        f"backend_python={sys.executable}; "
        f"scripts_dir={scripts_dir}; "
        "Install nnU-Net v2 in the backend Python environment, or set the TIF backend Python field "
        "to an environment that contains nnUNetv2_plan_and_preprocess, nnUNetv2_train, and nnUNetv2_predict."
    )


def _strip_shell_quotes(value):
    text = str(value or "")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _command_prefix(command, env, require_exists=True):
    parts = shlex.split(str(command or ""), posix=False)
    parts = [_strip_shell_quotes(item) for item in parts if str(item or "").strip()]
    if not parts:
        raise ValueError("nnunet_command_missing")
    resolved = _resolve_executable(parts[0], env)
    if not resolved:
        if not require_exists:
            return parts
        raise FileNotFoundError(_missing_command_message(parts[0], env))
    parts[0] = resolved
    return parts


def _run_command(cmd, cwd, env, log_path, dry_run=False):
    cmd = [str(item) for item in cmd]
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8", newline="\n") as log:
        log.write(f"$ {' '.join(cmd)}\n")
        log.write(f"cwd={cwd}\n")
        for key in ("nnUNet_raw", "nnUNet_preprocessed", "nnUNet_results", "CUDA_VISIBLE_DEVICES"):
            log.write(f"{key}={env.get(key, '')}\n")
        if dry_run:
            log.write("dry_run=true\n\n")
            return 0
        try:
            process = subprocess.run(
                cmd,
                cwd=str(cwd),
                env=env,
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(_missing_command_message(cmd[0], env)) from exc
        log.write(f"returncode={process.returncode}\n\n")
    if process.returncode != 0:
        raise RuntimeError(f"nnunet_command_failed:{process.returncode}:{log_path}")
    return process.returncode


def _collect_sample_metadata(contract):
    schema_ids = []
    labels = []
    trained_parts = []
    trained_top_level_volumes = []
    if str(contract.get("input_scope") or "part_reslice") == "top_level_volume":
        for sample in contract.get("specimens", []) or []:
            if not isinstance(sample, dict):
                continue
            specimen_id = str(sample.get("specimen_id") or "")
            trained_top_level_volumes.append({"specimen_id": specimen_id})
        return schema_ids, labels, trained_parts, trained_top_level_volumes
    for sample in contract.get("part_samples", []) or []:
        if not isinstance(sample, dict):
            continue
        trained_parts.append(
            {
                "specimen_id": sample.get("specimen_id", ""),
                "part_id": sample.get("part_id", ""),
                "reslice_id": sample.get("reslice_id", ""),
            }
        )
        schema_id = str(sample.get("label_schema_id") or "")
        if schema_id and schema_id not in schema_ids:
            schema_ids.append(schema_id)
        schema = sample.get("label_schema") if isinstance(sample.get("label_schema"), dict) else {}
        if not labels and isinstance(schema.get("labels"), list):
            labels = list(schema.get("labels") or [])
    return schema_ids, labels, trained_parts, trained_top_level_volumes


def _copy_splits_to_preprocessed(dataset_dir, preprocessed_dataset_dir):
    source = Path(dataset_dir) / "splits_final.json"
    if not source.exists():
        return ""
    target = Path(preprocessed_dataset_dir) / "splits_final.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target)


def _training_sample_count(export):
    if not isinstance(export, dict):
        return 0
    try:
        return int(export.get("exported_count", 0) or 0)
    except (TypeError, ValueError):
        pass
    manifest = export.get("manifest") if isinstance(export.get("manifest"), dict) else {}
    samples = manifest.get("training")
    if not isinstance(samples, list):
        samples = manifest.get("samples")
    if not isinstance(samples, list):
        samples = manifest.get("specimens")
    return len(samples or [])


def _validate_train_sample_count(export, dry_run=False):
    count = _training_sample_count(export)
    if not dry_run and count < 2:
        raise ValueError(f"nnunet_training_requires_at_least_2_samples:{count}")
    return count


def _apply_contract_training_split(contract, dataset_dir, dataset_manifest):
    split = contract.get("training_split")
    assignments = (split or {}).get("assignments") if isinstance(split, dict) else None
    if not isinstance(assignments, list) or not assignments:
        raise ValueError("contract_training_split_missing")
    partition_by_sample = {}
    for item in assignments:
        if not isinstance(item, dict):
            raise ValueError("contract_training_split_assignment_invalid")
        sample_id = str(item.get("sample_id") or "")
        partition = str(item.get("partition") or "")
        if not sample_id or partition not in {"train", "validation"}:
            raise ValueError(f"contract_training_split_assignment_invalid:{sample_id}")
        if sample_id in partition_by_sample:
            raise ValueError(f"contract_training_split_sample_duplicate:{sample_id}")
        partition_by_sample[sample_id] = partition

    cases = list(dataset_manifest.get("training") or [])
    if not cases:
        raise ValueError("nnunet_training_cases_missing")
    resolved = {"train": [], "val": []}
    seen = set()
    for case in cases:
        sample_id = str(case.get("sample_id") or case.get("specimen_id") or "")
        case_id = str(case.get("case_id") or "")
        if sample_id not in partition_by_sample or not case_id:
            raise ValueError(f"nnunet_split_case_unresolved:{sample_id}")
        seen.add(sample_id)
        target = "train" if partition_by_sample[sample_id] == "train" else "val"
        resolved[target].append(case_id)
    missing = sorted(set(partition_by_sample) - seen)
    if missing:
        raise ValueError(f"nnunet_split_sample_not_exported:{missing[0]}")
    if not resolved["train"] or not resolved["val"]:
        raise ValueError("nnunet_split_requires_train_and_validation")
    _write_json(Path(dataset_dir) / "splits_final.json", [resolved])
    return resolved


def _split_seed(contract):
    strategy = ((contract.get("training_split") or {}).get("strategy") or {})
    seed = strategy.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("contract_training_split_seed_invalid")
    return seed


def _first_input_resolution(contract):
    samples = contract.get("part_samples") or contract.get("specimens") or []
    if samples:
        shape = ((samples[0].get("input_volume") or {}).get("shape_zyx") or [])
        if len(shape) in {2, 3} and all(isinstance(value, int) and value > 0 for value in shape):
            return list(shape)
    return [1, 1, 1]


def _dry_run_effective_config(contract, args, split):
    return {
        "epochs": 0,
        "batch_size": 0,
        "learning_rate": 0.0,
        "weight_decay": 0.0,
        "random_seed": _split_seed(contract),
        "input_resolution": _first_input_resolution(contract),
        "preprocessing": {
            "configuration": args.configuration,
            "plans": args.plans,
            "split": split,
            "split_source": "taxamask_verified_training_split",
            "dataset_integrity_check": bool(args.verify_dataset_integrity),
        },
        "model": {
            "family": MODEL_FAMILY,
            "version": "nnunet_v2_dry_run",
            "trainer": args.trainer,
        },
        "loss_weights": {},
        "execution_kind": "backend_dry_run",
        "persist_weights": False,
    }


def _first_finite_number(values, *, positive=False):
    for value in values:
        if isinstance(value, (list, tuple)):
            found = _first_finite_number(value, positive=positive)
            if found is not None:
                return found
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
            if math.isfinite(number) and (number > 0 if positive else number >= 0):
                return number
    return None


def _load_checkpoint_payload(checkpoint_path):
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("torch_required_to_resolve_nnunet_effective_config") from exc
    try:
        payload = torch.load(str(checkpoint_path), map_location="cpu", weights_only=True)
    except TypeError:
        payload = torch.load(str(checkpoint_path), map_location="cpu")
    if not isinstance(payload, dict):
        raise ValueError("nnunet_checkpoint_payload_invalid")
    return payload


def _resolved_effective_config(contract, args, checkpoint_path, split):
    checkpoint = _load_checkpoint_payload(checkpoint_path)
    init_args = checkpoint.get("init_args") if isinstance(checkpoint.get("init_args"), dict) else {}
    plans = init_args.get("plans") if isinstance(init_args.get("plans"), dict) else {}
    configurations = plans.get("configurations") if isinstance(plans.get("configurations"), dict) else {}
    plan = configurations.get(args.configuration) if isinstance(configurations.get(args.configuration), dict) else {}
    batch_size = plan.get("batch_size")
    patch_size = plan.get("patch_size")
    epochs = checkpoint.get("current_epoch")
    optimizer = checkpoint.get("optimizer_state") if isinstance(checkpoint.get("optimizer_state"), dict) else {}
    parameter_groups = optimizer.get("param_groups") if isinstance(optimizer.get("param_groups"), list) else []
    learning_rate_candidates = []
    weight_decay_candidates = []
    for group in parameter_groups:
        if not isinstance(group, dict):
            continue
        learning_rate_candidates.extend([group.get("initial_lr"), group.get("lr")])
        weight_decay_candidates.append(group.get("weight_decay"))
    logging_payload = checkpoint.get("logging") if isinstance(checkpoint.get("logging"), dict) else {}
    learning_rate_candidates = list(logging_payload.get("lrs") or []) + learning_rate_candidates
    learning_rate = _first_finite_number(learning_rate_candidates, positive=True)
    weight_decay = _first_finite_number(weight_decay_candidates)
    if not isinstance(epochs, int) or isinstance(epochs, bool) or epochs <= 0:
        raise ValueError("nnunet_checkpoint_epochs_missing")
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size <= 0:
        raise ValueError("nnunet_plans_batch_size_missing")
    if not isinstance(patch_size, (list, tuple)) or len(patch_size) not in {2, 3}:
        raise ValueError("nnunet_plans_patch_size_missing")
    input_resolution = [int(value) for value in patch_size]
    if any(value <= 0 for value in input_resolution):
        raise ValueError("nnunet_plans_patch_size_invalid")
    if learning_rate is None:
        raise ValueError("nnunet_checkpoint_learning_rate_missing")
    if weight_decay is None:
        raise ValueError("nnunet_checkpoint_weight_decay_missing")
    return {
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "weight_decay": weight_decay,
        "random_seed": _split_seed(contract),
        "input_resolution": input_resolution,
        "preprocessing": {
            "configuration": args.configuration,
            "plans": args.plans,
            "split": split,
            "split_source": "taxamask_verified_training_split",
            "dataset_integrity_check": bool(args.verify_dataset_integrity),
        },
        "model": {
            "family": MODEL_FAMILY,
            "version": "nnunet_v2",
            "trainer": str(checkpoint.get("trainer_name") or args.trainer),
        },
        "loss_weights": {},
        "continue_training": bool(args.continue_training),
        "checkpoint": args.checkpoint,
        "parameter_sources": {
            "epochs": "checkpoint.current_epoch",
            "batch_size": "checkpoint.init_args.plans.configurations",
            "input_resolution": "checkpoint.init_args.plans.configurations",
            "learning_rate": "checkpoint.logging.lrs_or_optimizer_state",
            "weight_decay": "checkpoint.optimizer_state",
            "random_seed": "taxamask_verified_training_split",
        },
        "persist_weights": True,
    }


def _export_training_dataset(contract, args, raw_root):
    manager = _project_from_contract(contract)
    dataset_folder = _dataset_folder_name(args.dataset_id, args.dataset_name)
    dataset_dir = raw_root / dataset_folder
    if dataset_dir.exists():
        if not args.overwrite_dataset:
            raise FileExistsError(f"nnunet_dataset_exists:{dataset_dir}")
        shutil.rmtree(dataset_dir)
    if str(contract.get("input_scope") or "part_reslice") == "top_level_volume":
        export = export_nnunet_dataset(
            manager,
            dataset_dir,
            specimen_ids=_specimen_ids_from_contract(contract, require_label=True),
            dataset_name=dataset_folder,
            require_train_ready=True,
        )
    else:
        refs = _part_refs_from_contract(contract, require_label=True)
        export = export_tif_part_nnunet_dataset(
            manager,
            dataset_dir,
            part_refs=refs,
            dataset_name=dataset_folder,
            require_train_ready=True,
            file_ending=args.file_ending,
            label_id_mode=args.label_id_mode,
            split_mode=args.split_mode,
            include_images_ts=True,
        )
    return dataset_dir, export


def _model_output_dir(args, results_root):
    dataset_folder = _dataset_folder_name(args.dataset_id, args.dataset_name)
    return Path(results_root) / dataset_folder / f"{args.trainer}__{args.plans}__{args.configuration}"


def _checkpoint_path(args, results_root):
    model_dir = _model_output_dir(args, results_root)
    fold_dir = model_dir / f"fold_{args.fold}"
    return fold_dir / args.checkpoint


def _model_manifest_path(contract):
    manifest = str(contract.get("model_manifest") or "").strip()
    if manifest:
        return Path(manifest).resolve()
    return Path(contract["output_dir"]).resolve() / "model_manifest.json"


def _write_model_manifest(contract, args, raw_root, preprocessed_root, results_root, dataset_dir, dataset_manifest, command_log, dry_run=False):
    schema_ids, labels, trained_parts, trained_top_level_volumes = _collect_sample_metadata(contract)
    checkpoint = _checkpoint_path(args, results_root)
    if not dry_run and not checkpoint.exists():
        raise FileNotFoundError(f"nnunet_checkpoint_missing:{checkpoint}")
    manifest_path = _model_manifest_path(contract)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    relative = lambda value: _as_manifest_relative(manifest_path, value)
    manifest = {
        "schema_version": TIF_MODEL_MANIFEST_SCHEMA_VERSION,
        "model_id": f"{contract.get('backend_id') or ADAPTER_ID}/{contract.get('run_id')}",
        "backend_id": contract.get("backend_id") or ADAPTER_ID,
        "model_family": MODEL_FAMILY,
        "created_at": _now_iso(),
        "trained_specimens": sorted({str(item.get("specimen_id") or "") for item in (trained_parts or trained_top_level_volumes)}),
        "trained_parts": trained_parts,
        "trained_top_level_volumes": trained_top_level_volumes,
        "input_scope": str(contract.get("input_scope") or "part_reslice"),
        "label_role": "manual_truth",
        "label_schema_ids": schema_ids,
        "labels": labels,
        "nnunet": {
            "dataset_id": int(args.dataset_id),
            "dataset_name": _safe_id(args.dataset_name, DEFAULT_DATASET_NAME),
            "dataset_folder": _dataset_folder_name(args.dataset_id, args.dataset_name),
            "configuration": args.configuration,
            "fold": str(args.fold),
            "trainer": args.trainer,
            "plans": args.plans,
            "checkpoint": args.checkpoint,
            "raw_root": relative(raw_root),
            "preprocessed_root": relative(preprocessed_root),
            "results_root": relative(results_root),
            "dataset_dir": relative(dataset_dir),
            "model_output_dir": relative(_model_output_dir(args, results_root)),
            "checkpoint_path": relative(checkpoint),
            "file_ending": args.file_ending,
            "label_id_mode": args.label_id_mode,
            "label_id_mapping": dataset_manifest.get("label_id_mapping", {}),
        },
        "weights": {"main": relative(checkpoint)},
        "training_mode": "nnunet_v2_real" if not dry_run else "nnunet_v2_dry_run",
        "usable_for_research_prediction": not dry_run,
        "command_log": relative(command_log),
        "notes": [
            "Predictions from this model must be imported as editable_ai_result and reviewed before promotion to manual_truth.",
            "TaxaMask stores nnU-Net label remapping in this manifest so compact nnU-Net class IDs can be restored to research label IDs.",
        ],
    }
    _write_json(manifest_path, manifest)
    return manifest_path, manifest


def _load_model_manifest(path):
    text = str(path or "").strip()
    if not text:
        raise ValueError("model_manifest_required_for_prediction")
    manifest = _read_json(text)
    if manifest.get("schema_version") != TIF_MODEL_MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"invalid_tif_model_manifest_schema:{manifest.get('schema_version')}")
    if manifest.get("model_family") != MODEL_FAMILY and manifest.get("model_family") not in LEGACY_MODEL_FAMILIES:
        raise ValueError(f"unsupported_tif_model_family:{manifest.get('model_family')}")
    return manifest


def _label_restore_mapping(manifest):
    mapping = (((manifest.get("nnunet") or {}).get("label_id_mapping") or {}).get("nnunet_to_source") or {})
    clean = {}
    for key, value in mapping.items():
        try:
            clean[int(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return clean


def _export_prediction_inputs(contract, args):
    output_dir = Path(contract["output_dir"]).resolve()
    images_ts = output_dir / "imagesTs"
    images_ts.mkdir(parents=True, exist_ok=True)
    cases = []
    samples = contract.get("part_samples", []) or []
    if str(contract.get("input_scope") or "part_reslice") == "top_level_volume":
        samples = contract.get("specimens", []) or []
    for idx, sample in enumerate(samples, start=1):
        if not isinstance(sample, dict):
            continue
        specimen_id = str(sample.get("specimen_id") or "")
        part_id = str(sample.get("part_id") or "")
        reslice_id = str(sample.get("reslice_id") or "")
        input_volume = sample.get("input_volume") if isinstance(sample.get("input_volume"), dict) else {}
        image_path = str(input_volume.get("path") or "")
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(image_path)
        case_suffix = f"{_safe_id(specimen_id)}_{_safe_id(part_id)}" if part_id else _safe_id(specimen_id)
        case_id = f"taxamask_predict_{idx:04d}_{case_suffix}"
        out_path = images_ts / f"{case_id}_0000{args.file_ending}"
        if volume_sidecar_exists(image_path):
            array = load_volume_sidecar(image_path, mmap_mode="r")
            sidecar_meta = read_volume_metadata(image_path)
            metadata = {
                "spacing_zyx": sidecar_meta.get("spacing_zyx") or input_volume.get("spacing_zyx") or [1.0, 1.0, 1.0],
                "spacing_unit": sidecar_meta.get("spacing_unit", input_volume.get("spacing_unit", "micrometer")),
            }
        elif str(image_path).lower().endswith((".nii", ".nii.gz")):
            array = read_nifti_volume(image_path)
            metadata = {
                "spacing_zyx": input_volume.get("spacing_zyx") or [1.0, 1.0, 1.0],
                "spacing_unit": input_volume.get("spacing_unit", "micrometer"),
            }
        else:
            import tifffile

            array = tifffile.imread(image_path)
            metadata = {
                "spacing_zyx": input_volume.get("spacing_zyx") or [1.0, 1.0, 1.0],
                "spacing_unit": input_volume.get("spacing_unit", "micrometer"),
            }
        write_nifti_volume(out_path, array, metadata)
        cases.append(
            {
                "case_id": case_id,
                "specimen_id": specimen_id,
                "part_id": part_id,
                "reslice_id": reslice_id,
                "input_volume": input_volume,
                "image_path": str(out_path),
                "shape_zyx": [int(value) for value in np.asarray(array).shape],
            }
        )
    if not cases:
        raise ValueError("contract_samples_missing")
    _write_json(output_dir / "prediction_case_mapping.json", {"cases": cases})
    return images_ts, cases


def _prediction_output_for_case(predictions_dir, case_id):
    candidates = [
        Path(predictions_dir) / f"{case_id}.nii.gz",
        Path(predictions_dir) / f"{case_id}.nii",
        Path(predictions_dir) / case_id,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"nnunet_prediction_missing:{case_id}:{predictions_dir}")


def _write_prediction_sidecars(contract, cases, predictions_dir, manifest):
    output_dir = Path(contract["output_dir"]).resolve()
    restore_mapping = _label_restore_mapping(manifest)
    artifacts = []
    for case in cases:
        prediction_file = _prediction_output_for_case(predictions_dir, case["case_id"])
        prediction = read_nifti_volume(prediction_file)
        if restore_mapping:
            prediction = remap_label_ids(prediction, restore_mapping, dtype=np.uint16)
        expected_shape = [int(value) for value in case.get("shape_zyx", [])]
        if list(prediction.shape) != expected_shape:
            raise ValueError(f"prediction_shape_mismatch:{case['case_id']}:{list(prediction.shape)}:{expected_shape}")
        prediction_id = f"{contract.get('run_id')}_{_safe_id(case['specimen_id'])}"
        if case.get("part_id"):
            prediction_id = f"{prediction_id}_{_safe_id(case['part_id'])}"
        sidecar_path = output_dir / f"{prediction_id}.ome.zarr"
        input_volume = case.get("input_volume") if isinstance(case.get("input_volume"), dict) else {}
        meta = write_volume_sidecar(
            sidecar_path,
            prediction.astype(np.uint16, copy=False),
            role="editable_ai_result",
            spacing_zyx=input_volume.get("spacing_zyx") or [1.0, 1.0, 1.0],
            spacing_unit=input_volume.get("spacing_unit", "micrometer"),
            orientation=input_volume.get("orientation", "part_reslice" if case.get("part_id") else "top_level_volume"),
            source_format="nnunet_v2_prediction",
            extra_metadata={
                "nnunet_case_id": case["case_id"],
                "label_id_mapping": (manifest.get("nnunet") or {}).get("label_id_mapping", {}),
            },
        )
        artifacts.append(
            {
                "type": "prediction_label_volume",
                "specimen_id": case["specimen_id"],
                "part_id": case["part_id"],
                "reslice_id": case["reslice_id"],
                "prediction_id": prediction_id,
                "path": _as_run_relative(contract, sidecar_path),
                "format": meta["format"],
                "role": "editable_ai_result",
            }
        )
    return artifacts


def run_prepare_dataset(contract, args):
    started_at = _now_iso()
    raw_root, preprocessed_root, results_root = _nnunet_roots(args, contract)
    dataset_dir, export = _export_training_dataset(contract, args, raw_root)
    artifacts = [
        {"type": "dataset_manifest", "path": _as_run_relative(contract, export["manifest_path"]), "format": "json"},
        {"type": "nnunet_dataset_json", "path": _as_run_relative(contract, Path(dataset_dir) / "dataset.json"), "format": "json"},
        {"type": "nnunet_dataset_dir", "path": _as_run_relative(contract, dataset_dir), "format": "directory"},
    ]
    result = _result_base(
        contract,
        started_at,
        artifacts=artifacts,
        metrics={"summary": {"training_samples": export["exported_count"]}, "by_material": {}},
        provenance={
            "dataset_manifest": _as_run_relative(contract, export["manifest_path"]),
            "dataset_dir": _as_run_relative(contract, dataset_dir),
            "nnunet_raw": _as_run_relative(contract, raw_root),
            "nnunet_preprocessed": _as_run_relative(contract, preprocessed_root),
            "nnunet_results": _as_run_relative(contract, results_root),
            "input_label_role": "manual_truth",
            "input_part_samples": _part_refs_from_contract(contract, require_label=True) if contract.get("input_scope") == "part_reslice" else [],
            "input_specimens": _specimen_ids_from_contract(contract, require_label=True) if contract.get("input_scope") == "top_level_volume" else [],
        },
    )
    _write_json(contract["result_json"], result)
    return result


def run_train(contract, args):
    started_at = _now_iso()
    raw_root, preprocessed_root, results_root = _nnunet_roots(args, contract)
    env = _command_env(args, raw_root, preprocessed_root, results_root)
    command_log = Path(contract["run_dir"]) / "logs" / "nnunet_v2_commands.log"
    require_commands = not args.dry_run_commands
    plan_prefix = _command_prefix(args.plan_command, env, require_exists=require_commands)
    train_prefix = _command_prefix(args.train_command, env, require_exists=require_commands)
    dataset_dir, export = _export_training_dataset(contract, args, raw_root)
    _validate_train_sample_count(export, dry_run=args.dry_run_commands)
    actual_split = _apply_contract_training_split(
        contract, dataset_dir, export["manifest"]
    )
    preprocessed_dataset_dir = preprocessed_root / _dataset_folder_name(args.dataset_id, args.dataset_name)
    copied_split = ""
    plan_cmd = plan_prefix + [
        "-d",
        str(int(args.dataset_id)),
        "-c",
        args.configuration,
    ]
    if args.verify_dataset_integrity:
        plan_cmd.append("--verify_dataset_integrity")
    if args.fingerprint_processes is not None:
        plan_cmd.extend(["-npfp", str(args.fingerprint_processes)])
    if args.preprocess_processes is not None:
        plan_cmd.extend(["-np", str(args.preprocess_processes)])
    train_cmd = train_prefix + [
        str(int(args.dataset_id)),
        args.configuration,
        str(args.fold),
        "-tr",
        args.trainer,
        "-p",
        args.plans,
        "-device",
        args.device,
    ]
    if args.continue_training:
        train_cmd.append("--c")
    _run_command(plan_cmd, Path(contract["run_dir"]), env, command_log, dry_run=args.dry_run_commands)
    copied_split = _copy_splits_to_preprocessed(dataset_dir, preprocessed_dataset_dir)
    if copied_split:
        with open(command_log, "a", encoding="utf-8", newline="\n") as log:
            log.write(f"copied_splits_final={copied_split}\n")
    _run_command(train_cmd, Path(contract["run_dir"]), env, command_log, dry_run=args.dry_run_commands)
    manifest_path, manifest = _write_model_manifest(
        contract,
        args,
        raw_root,
        preprocessed_root,
        results_root,
        dataset_dir,
        export["manifest"],
        command_log,
        dry_run=args.dry_run_commands,
    )
    effective_config = (
        _dry_run_effective_config(contract, args, actual_split)
        if args.dry_run_commands
        else _resolved_effective_config(
            contract,
            args,
            _checkpoint_path(args, results_root),
            actual_split,
        )
    )
    manifest["effective_config"] = effective_config
    _write_json(manifest_path, manifest)
    artifacts = [
        {"type": "model_manifest", "path": _as_run_relative(contract, manifest_path), "format": "json"},
        {"type": "model_output_dir", "path": _as_run_relative(contract, _model_output_dir(args, results_root)), "format": "directory"},
        {"type": "nnunet_command_log", "path": _as_run_relative(contract, command_log), "format": "text"},
        {"type": "nnunet_dataset_dir", "path": _as_run_relative(contract, dataset_dir), "format": "directory"},
    ]
    warnings = ["nnunet_dry_run_no_training_performed"] if args.dry_run_commands else []
    result = _result_base(
        contract,
        started_at,
        artifacts=artifacts,
        metrics={"summary": {"training_samples": export["exported_count"], "usable_for_research_prediction": int(not args.dry_run_commands)}, "by_material": {}},
        warnings=warnings,
        provenance={
            "model_manifest": _as_run_relative(contract, manifest_path),
            "model_output_dir": _as_run_relative(contract, _model_output_dir(args, results_root)),
            "dataset_manifest": _as_run_relative(contract, export["manifest_path"]),
            "dataset_dir": _as_run_relative(contract, dataset_dir),
            "input_label_role": "manual_truth",
            "input_part_samples": manifest.get("trained_parts", []),
            "input_specimens": [item.get("specimen_id", "") for item in manifest.get("trained_top_level_volumes", []) or []],
            "usable_for_research_prediction": not args.dry_run_commands,
            "nnunet_raw": _as_run_relative(contract, raw_root),
            "nnunet_preprocessed": _as_run_relative(contract, preprocessed_root),
            "nnunet_results": _as_run_relative(contract, results_root),
        },
    )
    result["effective_config"] = effective_config
    result["training_split"] = {
        "status": "not_executed" if args.dry_run_commands else "applied",
        "assignments": list(
            (contract.get("training_split") or {}).get("assignments") or []
        ),
        "backend_partitions": actual_split,
    }
    _write_json(contract["result_json"], result)
    return result


def run_predict(contract, args):
    started_at = _now_iso()
    manifest_path = Path(contract.get("model_manifest") or "").resolve()
    manifest = _load_model_manifest(manifest_path)
    nnunet_meta = manifest.get("nnunet") if isinstance(manifest.get("nnunet"), dict) else {}
    raw_root = Path(args.nnunet_raw).resolve() if args.nnunet_raw else (_resolve_manifest_path(manifest_path, nnunet_meta.get("raw_root")) or Path(contract["run_dir"]) / "nnunet" / "nnUNet_raw").resolve()
    preprocessed_root = Path(args.nnunet_preprocessed).resolve() if args.nnunet_preprocessed else (_resolve_manifest_path(manifest_path, nnunet_meta.get("preprocessed_root")) or Path(contract["run_dir"]) / "nnunet" / "nnUNet_preprocessed").resolve()
    results_root = Path(args.nnunet_results).resolve() if args.nnunet_results else (_resolve_manifest_path(manifest_path, nnunet_meta.get("results_root")) or Path(contract["run_dir"]) / "nnunet" / "nnUNet_results").resolve()
    for path in (raw_root, preprocessed_root, results_root):
        path.mkdir(parents=True, exist_ok=True)
    if not args.dataset_id_from_cli and nnunet_meta.get("dataset_id") is not None:
        args.dataset_id = int(nnunet_meta.get("dataset_id"))
    if not args.dataset_name_from_cli and nnunet_meta.get("dataset_name"):
        args.dataset_name = str(nnunet_meta.get("dataset_name"))
    for attr in ("configuration", "trainer", "plans", "fold", "checkpoint", "file_ending", "label_id_mode"):
        cli_marker = f"{attr}_from_cli"
        if not getattr(args, cli_marker, False) and nnunet_meta.get(attr) is not None:
            setattr(args, attr, str(nnunet_meta.get(attr)))
    env = _command_env(args, raw_root, preprocessed_root, results_root)
    predict_prefix = _command_prefix(args.predict_command, env, require_exists=not args.dry_run_commands)
    images_ts, cases = _export_prediction_inputs(contract, args)
    predictions_dir = Path(contract["output_dir"]).resolve() / "nnunet_predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    command_log = Path(contract["run_dir"]) / "logs" / "nnunet_v2_predict.log"
    predict_cmd = predict_prefix + [
        "-i",
        str(images_ts),
        "-o",
        str(predictions_dir),
        "-d",
        str(int(args.dataset_id)),
        "-c",
        args.configuration,
        "-f",
        str(args.fold),
        "-tr",
        args.trainer,
        "-p",
        args.plans,
        "-chk",
        args.checkpoint,
        "-device",
        args.device,
    ]
    if args.disable_tta:
        predict_cmd.append("--disable_tta")
    if args.save_probabilities:
        predict_cmd.append("--save_probabilities")
    if args.not_on_device:
        predict_cmd.append("--not_on_device")
    _run_command(predict_cmd, Path(contract["run_dir"]), env, command_log, dry_run=args.dry_run_commands)
    artifacts = _write_prediction_sidecars(contract, cases, predictions_dir, manifest)
    result = _result_base(
        contract,
        started_at,
        artifacts=artifacts + [
            {"type": "nnunet_prediction_dir", "path": _as_run_relative(contract, predictions_dir), "format": "directory"},
            {"type": "nnunet_command_log", "path": _as_run_relative(contract, command_log), "format": "text"},
        ],
        metrics={"summary": {"prediction_samples": len(artifacts)}, "by_material": {}},
        provenance={
            "model_manifest": _as_run_relative(contract, manifest_path),
            "nnunet_prediction_dir": _as_run_relative(contract, predictions_dir),
            "input_label_role": "none",
            "input_part_samples": [
                {"specimen_id": item["specimen_id"], "part_id": item["part_id"], "reslice_id": item["reslice_id"]}
                for item in cases
                if item.get("part_id")
            ],
            "input_specimens": [item["specimen_id"] for item in cases if not item.get("part_id")],
            "usable_for_research_prediction": bool(manifest.get("usable_for_research_prediction")),
        },
    )
    _write_json(contract["result_json"], result)
    return result


def run_contract(contract_path, args):
    contract = _read_json(contract_path)
    action = _ensure_contract(contract)
    Path(contract["output_dir"]).mkdir(parents=True, exist_ok=True)
    Path(contract["result_json"]).parent.mkdir(parents=True, exist_ok=True)
    if action == "prepare_dataset":
        return run_prepare_dataset(contract, args)
    if action == "train":
        return run_train(contract, args)
    if action == "predict":
        return run_predict(contract, args)
    raise ValueError(f"unsupported_tif_backend_action:{action}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="TaxaMask TIF nnU-Net v2 backend adapter")
    parser.add_argument("--contract", "--contract-json", dest="contract", required=True)
    parser.add_argument("--dataset-id", type=int, default=701)
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--configuration", default="3d_fullres")
    parser.add_argument("--fold", default="0")
    parser.add_argument("--trainer", default="nnUNetTrainer")
    parser.add_argument("--plans", default="nnUNetPlans")
    parser.add_argument("--checkpoint", default="checkpoint_final.pth")
    parser.add_argument("--device", default="cuda", choices=("cuda", "cpu"))
    parser.add_argument("--gpu", default="0")
    parser.add_argument("--nnunet-work-dir", default="")
    parser.add_argument("--nnunet-raw", default="")
    parser.add_argument("--nnunet-preprocessed", default="")
    parser.add_argument("--nnunet-results", default="")
    parser.add_argument("--plan-command", default="nnUNetv2_plan_and_preprocess")
    parser.add_argument("--train-command", default="nnUNetv2_train")
    parser.add_argument("--predict-command", default="nnUNetv2_predict")
    parser.add_argument("--file-ending", default=".nii.gz", choices=(".nii", ".nii.gz"))
    parser.add_argument("--label-id-mode", default="compact", choices=("compact", "preserve"))
    parser.add_argument("--split-mode", default="all_train", choices=("all_train", "leave_one_val"))
    parser.add_argument("--overwrite-dataset", action="store_true")
    parser.add_argument("--continue-training", action="store_true")
    parser.add_argument("--verify-dataset-integrity", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--fingerprint-processes", type=int, default=None)
    parser.add_argument("--preprocess-processes", type=int, default=None)
    parser.add_argument("--disable-tta", action="store_true")
    parser.add_argument("--save-probabilities", action="store_true")
    parser.add_argument("--not-on-device", action="store_true")
    parser.add_argument("--dry-run-commands", action="store_true")
    args = parser.parse_args(argv)
    explicit = set()
    argv_list = list(argv if argv is not None else sys.argv[1:])
    for item in argv_list:
        if item.startswith("--"):
            explicit.add(item.split("=", 1)[0])
    for attr, option in {
        "dataset_id": "--dataset-id",
        "dataset_name": "--dataset-name",
        "configuration": "--configuration",
        "trainer": "--trainer",
        "plans": "--plans",
        "fold": "--fold",
        "checkpoint": "--checkpoint",
        "file_ending": "--file-ending",
        "label_id_mode": "--label-id-mode",
    }.items():
        setattr(args, f"{attr}_from_cli", option in explicit)
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        run_contract(args.contract, args)
    except Exception as exc:
        print(f"{ADAPTER_ID} failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
