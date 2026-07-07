import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np

from AntSleap.core.safe_io import atomic_write_json
from AntSleap.core.tif_backend import (
    TIF_BACKEND_CONTRACT_SCHEMA_VERSION,
    TIF_BACKEND_RESULT_SCHEMA_VERSION,
    TIF_MODEL_MANIFEST_SCHEMA_VERSION,
)
from AntSleap.core.tif_export import export_nnunet_dataset, export_tif_part_nnunet_dataset
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import read_volume_metadata, write_volume_sidecar


ADAPTER_ID = "taxamask_tif_trainer_backend"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_id(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return clean.strip("_") or "tif_backend"


def _write_json(path, payload):
    atomic_write_json(path, payload, indent=2, ensure_ascii=False)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return payload


def _as_run_relative(contract, path):
    text = str(path or "").strip()
    if not text:
        return ""
    base = os.path.dirname(os.path.abspath(contract["result_json"]))
    try:
        return os.path.relpath(os.path.abspath(text), base).replace("\\", "/")
    except ValueError:
        return os.path.abspath(text)


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


def _part_refs_from_contract(contract):
    refs = []
    for sample in contract.get("part_samples", []) or []:
        if not isinstance(sample, dict):
            continue
        specimen_id = str(sample.get("specimen_id") or "").strip()
        part_id = str(sample.get("part_id") or "").strip()
        reslice_id = str(sample.get("reslice_id") or "").strip()
        if specimen_id and part_id:
            refs.append({"specimen_id": specimen_id, "part_id": part_id, "reslice_id": reslice_id})
    if not refs:
        raise ValueError("contract_part_samples_missing")
    return refs


def _specimen_ids_from_contract(contract):
    ids = []
    for sample in contract.get("specimens", []) or []:
        if not isinstance(sample, dict):
            continue
        specimen_id = str(sample.get("specimen_id") or "").strip()
        if specimen_id:
            ids.append(specimen_id)
    if not ids:
        raise ValueError("contract_specimens_missing")
    return ids


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
            "adapter_mode": "smoke_or_export",
            "run_dir": os.path.abspath(contract.get("run_dir", "")),
            **(provenance if isinstance(provenance, dict) else {}),
        },
    }


def _dataset_name(contract):
    training_config = contract.get("training_config") if isinstance(contract.get("training_config"), dict) else {}
    raw = training_config.get("dataset_name") or training_config.get("nnunet_dataset_name")
    return str(raw or "Dataset001_TaxaMaskTifPart")


def run_prepare_dataset(contract):
    started_at = _now_iso()
    manager = _project_from_contract(contract)
    dataset_dir = os.path.abspath(contract.get("dataset_dir") or os.path.join(contract["run_dir"], "dataset"))
    if str(contract.get("input_scope") or "part_reslice") == "top_level_volume":
        refs = []
        specimen_ids = _specimen_ids_from_contract(contract)
        export = export_nnunet_dataset(
            manager,
            dataset_dir,
            specimen_ids=specimen_ids,
            dataset_name=_dataset_name(contract),
            require_train_ready=True,
        )
    else:
        refs = _part_refs_from_contract(contract)
        specimen_ids = []
        export = export_tif_part_nnunet_dataset(
            manager,
            dataset_dir,
            part_refs=refs,
            dataset_name=_dataset_name(contract),
            require_train_ready=True,
        )
    manifest_path = export["manifest_path"]
    artifacts = [
        {
            "type": "dataset_manifest",
            "path": _as_run_relative(contract, manifest_path),
            "format": "json",
        },
        {
            "type": "nnunet_dataset_json",
            "path": _as_run_relative(contract, os.path.join(dataset_dir, "dataset.json")),
            "format": "json",
        },
        {
            "type": "nnunet_dataset_dir",
            "path": _as_run_relative(contract, dataset_dir),
            "format": "directory",
        },
    ]
    result = _result_base(
        contract,
        started_at,
        artifacts=artifacts,
        metrics={"summary": {"training_samples": export["exported_count"]}, "by_material": {}},
        provenance={
            "dataset_manifest": os.path.abspath(manifest_path),
            "dataset_dir": dataset_dir,
            "input_label_role": "manual_truth",
            "input_part_samples": refs,
            "input_specimens": specimen_ids,
        },
    )
    _write_json(contract["result_json"], result)
    return result


def _model_manifest_path(contract):
    manifest = str(contract.get("model_manifest") or "").strip()
    if manifest:
        return os.path.abspath(manifest)
    return os.path.join(os.path.abspath(contract["output_dir"]), "model_manifest.json")


def _write_smoke_model_manifest(contract, model_dir):
    os.makedirs(model_dir, exist_ok=True)
    manifest_path = _model_manifest_path(contract)
    os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
    samples = contract.get("part_samples", []) or []
    top_level_samples = contract.get("specimens", []) or []
    schema_ids = []
    labels = []
    for sample in samples:
        schema_id = str(sample.get("label_schema_id") or "")
        if schema_id and schema_id not in schema_ids:
            schema_ids.append(schema_id)
        schema = sample.get("label_schema") if isinstance(sample.get("label_schema"), dict) else {}
        if not labels and isinstance(schema.get("labels"), list):
            labels = list(schema.get("labels") or [])
    manifest = {
        "schema_version": TIF_MODEL_MANIFEST_SCHEMA_VERSION,
        "model_id": f"{contract.get('backend_id') or ADAPTER_ID}/{contract.get('run_id')}",
        "backend_id": contract.get("backend_id") or ADAPTER_ID,
        "model_family": "nnunet_v2_tif_region",
        "created_at": _now_iso(),
        "trained_specimens": sorted({str(item.get("specimen_id") or "") for item in list(samples) + list(top_level_samples) if isinstance(item, dict)}),
        "trained_parts": [
            {
                "specimen_id": item.get("specimen_id", ""),
                "part_id": item.get("part_id", ""),
                "reslice_id": item.get("reslice_id", ""),
            }
            for item in samples
            if isinstance(item, dict)
        ],
        "trained_top_level_volumes": [
            {
                "specimen_id": item.get("specimen_id", ""),
            }
            for item in top_level_samples
            if isinstance(item, dict)
        ],
        "input_scope": str(contract.get("input_scope") or "part_reslice"),
        "label_role": "manual_truth",
        "label_schema_ids": schema_ids,
        "labels": labels,
        "weights": {},
        "training_mode": "smoke_adapter",
        "usable_for_research_prediction": False,
        "notes": [
            "This manifest was produced by the bundled TaxaMask adapter smoke path.",
            "It validates contract wiring and artifact provenance; it is not a trained nnU-Net checkpoint.",
        ],
    }
    _write_json(manifest_path, manifest)
    return manifest_path, manifest


def run_train(contract):
    started_at = _now_iso()
    output_dir = os.path.abspath(contract["output_dir"])
    model_dir = os.path.join(output_dir, "model")
    manifest_path, manifest = _write_smoke_model_manifest(contract, model_dir)
    readme_path = os.path.join(model_dir, "SMOKE_MODEL_README.txt")
    with open(readme_path, "w", encoding="utf-8") as handle:
        handle.write(
            "TaxaMask TIF trainer adapter smoke model.\n"
            "This directory proves the train contract path and manifest writing.\n"
            "Configure a real nnU-Net v2 command before using predictions for research.\n"
        )
    artifacts = [
        {"type": "model_manifest", "path": _as_run_relative(contract, manifest_path), "format": "json"},
        {"type": "model_output_dir", "path": _as_run_relative(contract, model_dir), "format": "directory"},
    ]
    result = _result_base(
        contract,
        started_at,
        artifacts=artifacts,
        metrics={"summary": {"training_samples": len(contract.get("part_samples", []) or contract.get("specimens", []) or []), "smoke_model": 1}, "by_material": {}},
        warnings=["smoke_model_manifest_only"],
        provenance={
            "model_manifest": os.path.abspath(manifest_path),
            "model_output_dir": os.path.abspath(model_dir),
            "usable_for_research_prediction": False,
            "input_label_role": "manual_truth",
            "input_part_samples": manifest.get("trained_parts", []),
            "input_specimens": [item.get("specimen_id", "") for item in manifest.get("trained_top_level_volumes", []) or []],
        },
    )
    _write_json(contract["result_json"], result)
    return result


def run_predict(contract):
    started_at = _now_iso()
    output_dir = os.path.abspath(contract["output_dir"])
    os.makedirs(output_dir, exist_ok=True)
    artifacts = []
    samples = contract.get("part_samples", []) or []
    if str(contract.get("input_scope") or "part_reslice") == "top_level_volume":
        samples = contract.get("specimens", []) or []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        specimen_id = str(sample.get("specimen_id") or "")
        part_id = str(sample.get("part_id") or "")
        input_volume = sample.get("input_volume") if isinstance(sample.get("input_volume"), dict) else {}
        shape = [int(value) for value in input_volume.get("shape_zyx", [])]
        if len(shape) != 3:
            source_meta = read_volume_metadata(input_volume.get("path", ""))
            shape = [int(value) for value in source_meta.get("shape_zyx", [])]
        prediction_id = f"{contract.get('run_id')}_{_safe_id(specimen_id)}"
        if part_id:
            prediction_id = f"{prediction_id}_{_safe_id(part_id)}"
        out_path = os.path.join(output_dir, f"{prediction_id}.ome.zarr")
        metadata = write_volume_sidecar(
            out_path,
            np.zeros(tuple(shape), dtype=np.uint16),
            role="editable_ai_result",
            spacing_zyx=input_volume.get("spacing_zyx") or [1.0, 1.0, 1.0],
            spacing_unit=input_volume.get("spacing_unit", "micrometer"),
            orientation=input_volume.get("orientation", "part_reslice" if part_id else "top_level_volume"),
            source_format="taxamask_tif_trainer_backend_smoke",
        )
        artifacts.append(
            {
                "type": "prediction_label_volume",
                "specimen_id": specimen_id,
                "part_id": part_id,
                "reslice_id": str(sample.get("reslice_id") or ""),
                "prediction_id": prediction_id,
                "path": _as_run_relative(contract, out_path),
                "format": metadata["format"],
                "role": "editable_ai_result",
            }
        )
    result = _result_base(
        contract,
        started_at,
        artifacts=artifacts,
        metrics={"summary": {"prediction_samples": len(artifacts), "smoke_prediction": 1}, "by_material": {}},
        warnings=["smoke_zero_predictions"],
        provenance={
            "model_manifest": os.path.abspath(contract.get("model_manifest") or "") if contract.get("model_manifest") else "",
            "usable_for_research_prediction": False,
            "input_label_role": "none",
                "input_part_samples": [
                    {
                        "specimen_id": item.get("specimen_id", ""),
                        "part_id": item.get("part_id", ""),
                        "reslice_id": item.get("reslice_id", ""),
                    }
                    for item in contract.get("part_samples", []) or []
                    if isinstance(item, dict)
                ],
            "input_specimens": [
                item.get("specimen_id", "")
                for item in contract.get("specimens", []) or []
                if isinstance(item, dict)
            ],
        },
    )
    _write_json(contract["result_json"], result)
    return result


def run_contract(contract_path):
    contract = _read_json(contract_path)
    action = _ensure_contract(contract)
    os.makedirs(contract["output_dir"], exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(contract["result_json"])), exist_ok=True)
    if action == "prepare_dataset":
        return run_prepare_dataset(contract)
    if action == "train":
        return run_train(contract)
    if action == "predict":
        return run_predict(contract)
    raise ValueError(f"unsupported_tif_backend_action:{action}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="TaxaMask TIF trainer backend adapter")
    parser.add_argument("--contract", "--contract-json", dest="contract", required=True)
    args = parser.parse_args(argv)
    try:
        run_contract(args.contract)
    except Exception as exc:
        print(f"{ADAPTER_ID} failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
