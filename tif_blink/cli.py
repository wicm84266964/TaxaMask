from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from AntSleap.core.file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from AntSleap.core.safe_io import atomic_write_json
from AntSleap.core.training_run_recorder import TrainingRunRecorder, capture_environment
from AntSleap.core.training_run_setup import build_and_attach_verified_training_inputs
from AntSleap.core.training_run_tif import attach_tif_training_evidence

from .dataset import TifBlinkDatasetConfig, TifBlinkGroupedSliceDataset, TifBlinkSliceDataset
from .infer import infer_volume
from .labels import coerce_label_mapping
from .nnunet_adapter import NnUNetBlinkDataset, NnUNetBlinkDatasetConfig
from .preprocess import input_channel_count
from .taxamask_io import load_train_ready_samples, save_prediction_as_model_draft
from .train import TifBlinkTrainConfig, train_model
from .training_run import (
    backend_facts,
    effective_config,
    external_file_specs,
    index_training_outputs,
    safe_id,
)


def _load_project(path: str):
    from AntSleap.core.tif_project import TifProjectManager

    manager = TifProjectManager()
    manager.load_project(path)
    return manager


def train_from_project(args) -> dict:
    fallback_root = os.path.abspath(
        args.output_dir
        or os.path.join(os.getcwd(), "TaxaMask_outputs", "runtime_logs", "tif_blink")
    )
    try:
        manager = _load_project(args.project)
    except BaseException as exc:
        fallback = TrainingRunRecorder(fallback_root).create_pending("tif_blink_project")
        fallback.fail(exc, code="project_load_failed", stage="project_load", recoverable=True)
        raise
    runs_root = os.path.join(manager.project_dir, "runs", "tif_blink")
    recorder = TrainingRunRecorder(
        runs_root, database_path=manager.current_database_path
    )
    run = recorder.create_pending("tif_blink_project")
    try:
        if args.output_dir and os.path.normcase(os.path.abspath(args.output_dir)) != os.path.normcase(os.path.abspath(runs_root)):
            raise ValueError(f"tif_blink_project_output_dir_must_be:{runs_root}")
        specimen_ids = [str(value) for value in (args.specimen or [])]
        if not specimen_ids:
            specimen_ids = [
                str(item.get("specimen_id") or "")
                for item in manager.list_train_ready_specimens()
            ]
        sample_specs = []
        input_resolution = []
        for specimen_id in specimen_ids:
            readiness = manager.evaluate_train_ready(specimen_id)
            if not readiness["train_ready"]:
                raise ValueError(
                    f"specimen_not_train_ready:{specimen_id}:{','.join(readiness['reasons'])}"
                )
            specimen = manager.get_specimen(specimen_id)
            shape = list((specimen.get("working_volume") or {}).get("shape_zyx") or [])
            if not input_resolution and len(shape) == 3:
                input_resolution = shape[-2:]
            sample_specs.append(
                {
                    "sample_id": safe_id(specimen_id),
                    "group_id": specimen_id,
                    "owner_keys": [
                        f"specimen.{specimen_id}.working",
                        f"specimen.{specimen_id}.manual_truth",
                    ],
                }
            )
        run_config = effective_config(
            args,
            input_resolution=input_resolution,
            preprocessing={
                "source_kind": "taxamask_tif_project",
                "context_slices": int(args.context_slices),
                "view_modes": list(args.view_mode),
                "include_boundary_channel": bool(args.include_boundary_channel),
                "grouped_views": bool(args.grouped_views),
                "balanced_sampler": bool(args.balanced_sampler),
            },
        )
        evidence = attach_tif_training_evidence(
            run,
            manager,
            sample_specs=sample_specs,
            effective_config=run_config,
            backend=backend_facts("tif_blink_project"),
            seed=int(args.seed),
            compute_device=run_config["compute_device"],
            trusted_label_policy="manual_truth_only",
        )
        samples = load_train_ready_samples(manager, specimen_ids)
        shared_mapping = coerce_label_mapping(
            None, [sample.label for sample in samples]
        )
        by_partition = {"train": [], "validation": []}
        for sample in samples:
            partition = evidence["partition_by_group"][sample.specimen_id]
            by_partition[partition].append(sample)
        if not by_partition["train"] or not by_partition["validation"]:
            raise ValueError("tif_blink_project_split_incomplete")
        dataset_config = TifBlinkDatasetConfig(
            context_slices=int(args.context_slices),
            view_modes=tuple(args.view_mode),
            include_boundary_channel=bool(args.include_boundary_channel),
            label_id_to_class=dict(shared_mapping.label_id_to_class),
        )
        dataset_type = TifBlinkGroupedSliceDataset if args.grouped_views else TifBlinkSliceDataset
        train_dataset = dataset_type(by_partition["train"], dataset_config)
        val_dataset = dataset_type(by_partition["validation"], dataset_config)
        config = TifBlinkTrainConfig(
            num_classes=train_dataset.label_mapping.num_classes,
            in_channels=input_channel_count(args.context_slices, args.include_boundary_channel),
            context_slices=int(args.context_slices),
            include_boundary_channel=bool(args.include_boundary_channel),
            base_channels=int(args.base_channels),
            epochs=int(args.epochs),
            batch_size=int(args.batch_size),
            learning_rate=float(args.learning_rate),
            weight_decay=float(args.weight_decay),
            boundary_weight=float(args.boundary_weight),
            dice_weight=float(args.dice_weight),
            device=run_config["compute_device"],
            output_dir=os.path.join(run.run_dir, "outputs"),
            model_name=args.model_name,
            use_grouped_views=bool(args.grouped_views),
            use_balanced_sampler=bool(args.balanced_sampler),
            consistency_weight=float(args.consistency_weight),
            seed=int(args.seed),
        )
        result = train_model(
            train_dataset,
            config,
            val_dataset=val_dataset,
            trained_specimens=specimen_ids,
        )
        index_training_outputs(run, result)
        run.succeed()
        summary = {
            "run_id": run.run_id,
            "run_dir": run.run_dir,
            "manifest_path": result["manifest_path"],
            "best_checkpoint": result["best_checkpoint"],
            "last_checkpoint": result["last_checkpoint"],
            "best_metric": result["best_metric"],
            "train_specimens": [item.specimen_id for item in by_partition["train"]],
            "val_specimens": [item.specimen_id for item in by_partition["validation"]],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary
    except BaseException as exc:
        if run.status in {"pending", "running"}:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                run.interrupt(stage="tif_blink_project")
            else:
                run.fail(exc, stage="tif_blink_project")
        raise


def _patch_size_from_args(value: list[int] | None) -> tuple[int, int] | None:
    if not value:
        return None
    if len(value) == 1:
        size = int(value[0])
        return (size, size) if size > 0 else None
    height, width = int(value[0]), int(value[1])
    if height <= 0 or width <= 0:
        return None
    return (height, width)


def _nnunet_dataset_config(args, split: str, max_cases: int | None) -> NnUNetBlinkDatasetConfig:
    return NnUNetBlinkDatasetConfig(
        preprocessed_root=args.preprocessed_root,
        dataset_dir=args.dataset_dir,
        plans=args.plans,
        configuration=args.configuration,
        fold=int(args.fold),
        split=split,
        context_slices=int(args.context_slices),
        view_modes=tuple(args.view_mode or ("normal", "inside_band", "outside_band")),
        include_boundary_channel=bool(args.include_boundary_channel),
        ignore_label=int(args.ignore_label) if args.ignore_label is not None else None,
        ignore_to_background=bool(args.ignore_to_background),
        renormalize_percentile=bool(args.renormalize_percentile),
        grouped_views=bool(args.grouped_views),
        patch_size=_patch_size_from_args(args.patch_size),
        foreground_patch_probability=float(args.foreground_patch_probability),
        foreground_slices_only=bool(args.foreground_slices_only),
        slice_stride=int(args.slice_stride),
        max_cases=max_cases,
        max_slices_per_case=args.max_slices_per_case,
        seed=int(args.seed),
    )


def train_from_nnunet_preprocessed(args) -> dict:
    runs_root = os.path.abspath(args.output_dir)
    recorder = TrainingRunRecorder(runs_root)
    run = recorder.create_pending("tif_blink_nnunet_preprocessed")
    try:
        source_id = safe_id(args.trusted_source_id, "external_nnunet")
        trust_note = str(args.trusted_source_note or "").strip()
        if not trust_note:
            raise ValueError("trusted_source_note_required")
        train_max_cases = args.max_train_cases if args.max_train_cases is not None else args.max_cases
        val_max_cases = args.max_val_cases if args.max_val_cases is not None else args.max_cases
        train_dataset = NnUNetBlinkDataset(_nnunet_dataset_config(args, "train", train_max_cases))
        val_dataset = NnUNetBlinkDataset(_nnunet_dataset_config(args, "val", val_max_cases))
        if (
            dict(train_dataset.label_mapping.label_id_to_class)
            != dict(val_dataset.label_mapping.label_id_to_class)
        ):
            raise ValueError("nnunet_train_validation_label_mapping_mismatch")
        train_case_ids = list(train_dataset.case_ids)
        val_case_ids = list(val_dataset.case_ids)
        if not train_case_ids or not val_case_ids:
            raise ValueError("nnunet_train_validation_cases_required")
        overlap = sorted(set(train_case_ids) & set(val_case_ids))
        if overlap:
            raise ValueError(f"nnunet_train_validation_case_leakage:{overlap[0]}")
        first_shape = list(train_dataset.cases[0].shape)
        requested_patch = _patch_size_from_args(args.patch_size)
        input_resolution = list(requested_patch or first_shape[-2:])
        run_config = effective_config(
            args,
            input_resolution=input_resolution,
            preprocessing={
                "source_kind": "nnunet_preprocessed",
                "trusted_source_id": source_id,
                "trusted_source_note": trust_note,
                "configuration": str(args.configuration),
                "plans": Path(str(args.plans)).name,
                "fold": int(args.fold),
                "context_slices": int(args.context_slices),
                "view_modes": list(args.view_mode or ("normal", "inside_band", "outside_band")),
                "include_boundary_channel": bool(args.include_boundary_channel),
                "ignore_label": args.ignore_label,
                "ignore_to_background": bool(args.ignore_to_background),
                "renormalize_percentile": bool(args.renormalize_percentile),
                "patch_size": list(requested_patch or []),
                "foreground_patch_probability": float(args.foreground_patch_probability),
                "foreground_slices_only": bool(args.foreground_slices_only),
                "slice_stride": int(args.slice_stride),
            },
        )
        dataset_dir = Path(train_dataset.dataset_dir)
        plans_name = Path(str(args.plans)).name
        plans_candidates = [
            dataset_dir / f"{plans_name}.json",
            dataset_dir / "nnUNetPlans.json",
        ]
        plans_json = next((path for path in plans_candidates if path.is_file()), None)
        if plans_json is None:
            raise FileNotFoundError("nnunet_plans_json_missing")
        fingerprint_json = dataset_dir / "dataset_fingerprint.json"
        if not fingerprint_json.is_file():
            raise FileNotFoundError("nnunet_dataset_fingerprint_missing")
        items = [
            {"file_id": "dataset_json", "role": "training_config", "path": dataset_dir / "dataset.json"},
            {"file_id": "splits_final", "role": "training_config", "path": dataset_dir / "splits_final.json"},
            {"file_id": "nnunet_plans", "role": "training_config", "path": plans_json},
            {"file_id": "dataset_fingerprint", "role": "training_config", "path": fingerprint_json},
        ]
        case_file_ids = {}
        for partition, dataset in (("train", train_dataset), ("validation", val_dataset)):
            for case in dataset.cases:
                image_id = safe_id(f"{case.case_id}.image")
                truth_id = safe_id(f"{case.case_id}.truth")
                items.extend(
                    [
                        {"file_id": image_id, "role": "training_image", "path": case.image_path},
                        {"file_id": truth_id, "role": "verified_external_truth", "path": case.seg_path},
                    ]
                )
                case_file_ids[case.case_id] = (image_id, truth_id, partition)
        config_path = Path(run.run_dir) / "inputs" / "effective_config.json"
        atomic_write_json(config_path, run_config, indent=2)
        specs, data_version_id = external_file_specs(items, source_id=source_id)
        config_fingerprint = compute_fingerprint(config_path, FULL_FILE_ALGORITHM)
        specs.append(
            {
                "file_id": "effective_config",
                "role": "training_config",
                "data_version_id": data_version_id,
                "algorithm": config_fingerprint["hash_algorithm"],
                "expected": config_fingerprint,
                "path_base": "run_root",
                "relative_path": "inputs/effective_config.json",
                "entry_kind": "file",
            }
        )
        assignments = [
            {
                "sample_id": safe_id(case_id),
                "partition": partition,
                "group_id": safe_id(case_id),
                "input_file_ids": [image_id, truth_id],
            }
            for case_id, (image_id, truth_id, partition) in sorted(case_file_ids.items())
        ]
        run.attach_facts(
            dataset_ref={
                "dataset_id": source_id,
                "data_version_id": data_version_id,
                "trusted_label_policy": "verified_external_truth",
                "source_kind": "verified_external",
                "trusted_source_ref": source_id,
            },
            effective_config=run_config,
            backend=backend_facts("tif_blink_nnunet_preprocessed"),
            environment=capture_environment(
                compute_device=run_config["compute_device"]
            ),
        )
        build_and_attach_verified_training_inputs(
            run,
            file_specs=specs,
            assignments=assignments,
            dataset_id=source_id,
            data_version_id=data_version_id,
            strategy={
                "name": "nnunet_fold",
                "version": "v1",
                "seed": int(args.seed),
                "validation_ratio": len(val_case_ids) / (len(train_case_ids) + len(val_case_ids)),
            },
        )
        run.mark_running()
        config = TifBlinkTrainConfig(
            num_classes=train_dataset.label_mapping.num_classes,
            in_channels=input_channel_count(args.context_slices, args.include_boundary_channel),
            context_slices=int(args.context_slices),
            include_boundary_channel=bool(args.include_boundary_channel),
            base_channels=int(args.base_channels),
            epochs=int(args.epochs),
            batch_size=int(args.batch_size),
            learning_rate=float(args.learning_rate),
            weight_decay=float(args.weight_decay),
            boundary_weight=float(args.boundary_weight),
            dice_weight=float(args.dice_weight),
            device=run_config["compute_device"],
            num_workers=int(args.num_workers),
            output_dir=os.path.join(run.run_dir, "outputs"),
            model_name=args.model_name,
            use_grouped_views=bool(args.grouped_views),
            use_balanced_sampler=bool(args.balanced_sampler),
            consistency_weight=float(args.consistency_weight),
            seed=int(args.seed),
        )
        result = train_model(
            train_dataset,
            config,
            val_dataset=val_dataset,
            trained_specimens=train_case_ids,
        )
        index_training_outputs(run, result)
        run.succeed()
        summary = {
            "run_id": run.run_id,
            "run_dir": run.run_dir,
            "manifest_path": result["manifest_path"],
            "best_checkpoint": result["best_checkpoint"],
            "last_checkpoint": result["last_checkpoint"],
            "best_metric": result["best_metric"],
            "train_items": len(train_dataset),
            "val_items": len(val_dataset),
            "train_cases": len(train_dataset.cases),
            "val_cases": len(val_dataset.cases),
            "num_classes": train_dataset.label_mapping.num_classes,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary
    except BaseException as exc:
        if run.status in {"pending", "running"}:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                run.interrupt(stage="tif_blink_nnunet_preprocessed")
            else:
                run.fail(exc, stage="tif_blink_nnunet_preprocessed")
        raise


def predict_project(args) -> dict:
    manager = _load_project(args.project)
    specimen = manager.get_specimen(args.specimen, default=None)
    if specimen is None:
        raise KeyError(f"unknown_specimen_id:{args.specimen}")
    from AntSleap.core.tif_volume_io import load_volume_sidecar

    working = specimen.get("working_volume") or {}
    image = load_volume_sidecar(manager.to_absolute(working.get("path", "")))
    prediction = infer_volume(
        image,
        checkpoint_path=args.checkpoint,
        device=args.device,
        batch_size=int(args.batch_size),
    )
    result = save_prediction_as_model_draft(
        manager,
        args.specimen,
        prediction,
        prediction_id=args.prediction_id,
        source_model=args.source_model,
        model_manifest=os.path.abspath(args.model_manifest) if args.model_manifest else "",
    )
    summary = {
        "prediction_id": result["draft"]["prediction_id"],
        "model_draft": result["draft"]["path"],
        "report_path": result["report_path"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Experimental TIF-Blink training and prediction CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train-project", help="Train TIF-Blink from train-ready TaxaMask specimens.")
    train_parser.add_argument("--project", required=True, help="Path to TaxaMask TIF project.json.")
    train_parser.add_argument("--specimen", action="append", default=[], help="Specimen ID. Repeat to train on multiple specimens.")
    train_parser.add_argument("--output-dir", default="", help="Optional project run directory; must equal <project>/runs/tif_blink.")
    train_parser.add_argument("--context-slices", type=int, default=1)
    train_parser.add_argument("--view-mode", action="append", default=["normal", "inside_band", "outside_band"])
    train_parser.add_argument("--include-boundary-channel", action="store_true")
    train_parser.add_argument("--base-channels", type=int, default=32)
    train_parser.add_argument("--epochs", type=int, default=5)
    train_parser.add_argument("--batch-size", type=int, default=2)
    train_parser.add_argument("--learning-rate", type=float, default=1e-3)
    train_parser.add_argument("--weight-decay", type=float, default=1e-2)
    train_parser.add_argument("--boundary-weight", type=float, default=2.0)
    train_parser.add_argument("--dice-weight", type=float, default=1.0)
    train_parser.add_argument("--grouped-views", action="store_true")
    train_parser.add_argument("--balanced-sampler", action="store_true")
    train_parser.add_argument("--consistency-weight", type=float, default=0.15)
    train_parser.add_argument("--device", default="auto")
    train_parser.add_argument("--model-name", default="tif_blink_unet2d")
    train_parser.add_argument("--seed", type=int, default=17)
    train_parser.set_defaults(func=train_from_project)

    nnunet_parser = subparsers.add_parser(
        "train-nnunet-preprocessed",
        help="Train TIF-Blink directly from nnU-Net preprocessed .b2nd cases.",
    )
    nnunet_parser.add_argument("--preprocessed-root", required=True, help="Path to nnUNet_preprocessed.")
    nnunet_parser.add_argument("--dataset-dir", required=True, help="Dataset folder name or absolute dataset path.")
    nnunet_parser.add_argument("--plans", required=True, help="Plans name or resolved plans/configuration folder.")
    nnunet_parser.add_argument("--configuration", default="3d_fullres")
    nnunet_parser.add_argument("--fold", type=int, default=0)
    nnunet_parser.add_argument("--output-dir", required=True, help="Run output directory.")
    nnunet_parser.add_argument("--trusted-source-id", required=True, help="Stable identifier for the externally reviewed dataset.")
    nnunet_parser.add_argument("--trusted-source-note", required=True, help="Researcher note describing why this external label source is trusted.")
    nnunet_parser.add_argument("--context-slices", type=int, default=1)
    nnunet_parser.add_argument("--view-mode", action="append", default=None)
    nnunet_parser.add_argument("--include-boundary-channel", action="store_true")
    nnunet_parser.add_argument("--base-channels", type=int, default=32)
    nnunet_parser.add_argument("--epochs", type=int, default=5)
    nnunet_parser.add_argument("--batch-size", type=int, default=2)
    nnunet_parser.add_argument("--learning-rate", type=float, default=1e-3)
    nnunet_parser.add_argument("--weight-decay", type=float, default=1e-2)
    nnunet_parser.add_argument("--boundary-weight", type=float, default=2.0)
    nnunet_parser.add_argument("--dice-weight", type=float, default=1.0)
    nnunet_parser.add_argument("--grouped-views", action="store_true")
    nnunet_parser.add_argument("--balanced-sampler", action="store_true")
    nnunet_parser.add_argument("--consistency-weight", type=float, default=0.15)
    nnunet_parser.add_argument("--device", default="auto")
    nnunet_parser.add_argument("--num-workers", type=int, default=0)
    nnunet_parser.add_argument("--seed", type=int, default=17)
    nnunet_parser.add_argument("--model-name", default="tif_blink_unet2d_nnunet")
    nnunet_parser.add_argument("--ignore-label", type=int, default=-1)
    nnunet_parser.add_argument("--ignore-to-background", action=argparse.BooleanOptionalAction, default=True)
    nnunet_parser.add_argument("--renormalize-percentile", action=argparse.BooleanOptionalAction, default=True)
    nnunet_parser.add_argument("--patch-size", type=int, nargs="+", default=None, help="Optional H W patch size; omit for full slices with padded batching.")
    nnunet_parser.add_argument("--foreground-patch-probability", type=float, default=0.5)
    nnunet_parser.add_argument("--foreground-slices-only", action="store_true")
    nnunet_parser.add_argument("--slice-stride", type=int, default=1)
    nnunet_parser.add_argument("--max-cases", type=int, default=None)
    nnunet_parser.add_argument("--max-train-cases", type=int, default=None)
    nnunet_parser.add_argument("--max-val-cases", type=int, default=None)
    nnunet_parser.add_argument("--max-slices-per-case", type=int, default=None)
    nnunet_parser.set_defaults(func=train_from_nnunet_preprocessed)

    predict_parser = subparsers.add_parser("predict-project", help="Predict one TaxaMask specimen and save model_draft.")
    predict_parser.add_argument("--project", required=True, help="Path to TaxaMask TIF project.json.")
    predict_parser.add_argument("--specimen", required=True, help="Specimen ID to predict.")
    predict_parser.add_argument("--checkpoint", required=True, help="Path to best.pt or last.pt.")
    predict_parser.add_argument("--prediction-id", default="", help="Prediction ID for model_draft registration.")
    predict_parser.add_argument("--source-model", default="tif_blink", help="Source model name stored in model_draft metadata.")
    predict_parser.add_argument("--model-manifest", default="", help="Optional model_manifest.json path.")
    predict_parser.add_argument("--batch-size", type=int, default=4)
    predict_parser.add_argument("--device", default="auto")
    predict_parser.set_defaults(func=predict_project)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
