from __future__ import annotations

import argparse
import json
import os

from .dataset import TifBlinkDatasetConfig, TifBlinkGroupedSliceDataset, TifBlinkSliceDataset
from .infer import infer_volume
from .nnunet_adapter import NnUNetBlinkDataset, NnUNetBlinkDatasetConfig
from .preprocess import input_channel_count
from .taxamask_io import load_train_ready_samples, save_prediction_as_model_draft
from .train import TifBlinkTrainConfig, train_model


def _load_project(path: str):
    from AntSleap.core.tif_project import TifProjectManager

    manager = TifProjectManager()
    manager.load_project(path)
    return manager


def train_from_project(args) -> dict:
    manager = _load_project(args.project)
    specimen_ids = args.specimen or None
    samples = load_train_ready_samples(manager, specimen_ids)
    dataset_config = TifBlinkDatasetConfig(
        context_slices=int(args.context_slices),
        view_modes=tuple(args.view_mode),
        include_boundary_channel=bool(args.include_boundary_channel),
    )
    dataset = TifBlinkGroupedSliceDataset(samples, dataset_config) if args.grouped_views else TifBlinkSliceDataset(samples, dataset_config)
    config = TifBlinkTrainConfig(
        num_classes=dataset.label_mapping.num_classes,
        in_channels=input_channel_count(args.context_slices, args.include_boundary_channel),
        context_slices=int(args.context_slices),
        include_boundary_channel=bool(args.include_boundary_channel),
        base_channels=int(args.base_channels),
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        learning_rate=float(args.learning_rate),
        boundary_weight=float(args.boundary_weight),
        dice_weight=float(args.dice_weight),
        device=args.device,
        output_dir=args.output_dir,
        model_name=args.model_name,
        use_grouped_views=bool(args.grouped_views),
        use_balanced_sampler=bool(args.balanced_sampler),
        consistency_weight=float(args.consistency_weight),
    )
    result = train_model(
        dataset,
        config,
        trained_specimens=[sample.specimen_id for sample in samples],
    )
    summary = {
        "manifest_path": result["manifest_path"],
        "best_checkpoint": result["best_checkpoint"],
        "last_checkpoint": result["last_checkpoint"],
        "best_metric": result["best_metric"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


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
    train_max_cases = args.max_train_cases if args.max_train_cases is not None else args.max_cases
    val_max_cases = args.max_val_cases if args.max_val_cases is not None else args.max_cases
    train_dataset = NnUNetBlinkDataset(_nnunet_dataset_config(args, "train", train_max_cases))
    val_dataset = NnUNetBlinkDataset(_nnunet_dataset_config(args, "val", val_max_cases))
    config = TifBlinkTrainConfig(
        num_classes=train_dataset.label_mapping.num_classes,
        in_channels=input_channel_count(args.context_slices, args.include_boundary_channel),
        context_slices=int(args.context_slices),
        include_boundary_channel=bool(args.include_boundary_channel),
        base_channels=int(args.base_channels),
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        learning_rate=float(args.learning_rate),
        boundary_weight=float(args.boundary_weight),
        dice_weight=float(args.dice_weight),
        device=args.device,
        num_workers=int(args.num_workers),
        output_dir=args.output_dir,
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
        trained_specimens=train_dataset.case_ids,
    )
    summary = {
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
    train_parser.add_argument("--output-dir", required=True, help="Run output directory.")
    train_parser.add_argument("--context-slices", type=int, default=1)
    train_parser.add_argument("--view-mode", action="append", default=["normal", "inside_band", "outside_band"])
    train_parser.add_argument("--include-boundary-channel", action="store_true")
    train_parser.add_argument("--base-channels", type=int, default=32)
    train_parser.add_argument("--epochs", type=int, default=5)
    train_parser.add_argument("--batch-size", type=int, default=2)
    train_parser.add_argument("--learning-rate", type=float, default=1e-3)
    train_parser.add_argument("--boundary-weight", type=float, default=2.0)
    train_parser.add_argument("--dice-weight", type=float, default=1.0)
    train_parser.add_argument("--grouped-views", action="store_true")
    train_parser.add_argument("--balanced-sampler", action="store_true")
    train_parser.add_argument("--consistency-weight", type=float, default=0.15)
    train_parser.add_argument("--device", default="auto")
    train_parser.add_argument("--model-name", default="tif_blink_unet2d")
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
    nnunet_parser.add_argument("--context-slices", type=int, default=1)
    nnunet_parser.add_argument("--view-mode", action="append", default=None)
    nnunet_parser.add_argument("--include-boundary-channel", action="store_true")
    nnunet_parser.add_argument("--base-channels", type=int, default=32)
    nnunet_parser.add_argument("--epochs", type=int, default=5)
    nnunet_parser.add_argument("--batch-size", type=int, default=2)
    nnunet_parser.add_argument("--learning-rate", type=float, default=1e-3)
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
