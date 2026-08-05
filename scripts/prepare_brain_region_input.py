"""Create a strict, scale-audited brain-region model input from a whole-brain mask."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import tifffile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from AntSleap.core.safe_io import atomic_write_json
from AntSleap.core.tif_brain_input_cleaning import (
    DEFAULT_REGION_INPUT_PROFILE,
    prepare_brain_region_input,
    prepare_locator_candidate,
)
from AntSleap.core.tif_export import read_nifti_volume_with_metadata, write_nifti_volume


SPACING_UNIT_TO_MICROMETERS = {
    "meter": 1_000_000.0,
    "millimeter": 1_000.0,
    "micrometer": 1.0,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--mask-npy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--spacing-zyx-um", type=float, nargs=3)
    parser.add_argument("--mask-source-bbox", type=int, nargs=6, metavar=("Z0", "Z1", "Y0", "Y1", "X0", "X1"))
    parser.add_argument("--accepted-value", type=int, action="append")
    parser.add_argument("--case-id", default="brain")
    parser.add_argument(
        "--context-margin-um",
        type=float,
        default=DEFAULT_REGION_INPUT_PROFILE["context_margin_um"],
    )
    return parser.parse_args()


def read_image(path):
    if str(path).lower().endswith((".nii", ".nii.gz")):
        return read_nifti_volume_with_metadata(path)
    array = np.asarray(tifffile.memmap(path))
    return array, {"spacing_zyx": [1.0, 1.0, 1.0], "spacing_unit": "unknown", "scale_verified": False}


def resolve_spacing_zyx_um(explicit_spacing, metadata):
    """Return verified ZYX spacing in micrometers, failing closed on unknown scale."""
    if explicit_spacing is not None:
        return [float(value) for value in explicit_spacing]
    clean = metadata if isinstance(metadata, dict) else {}
    unit = str(clean.get("spacing_unit") or "unknown").strip().lower()
    spacing = clean.get("spacing_zyx")
    if clean.get("scale_verified") is not True or unit not in SPACING_UNIT_TO_MICROMETERS:
        raise ValueError("verified_spacing_zyx_um_is_required")
    if not isinstance(spacing, (list, tuple)) or len(spacing) != 3:
        raise ValueError("verified_spacing_zyx_um_is_required")
    factor = SPACING_UNIT_TO_MICROMETERS[unit]
    return [float(value) * factor for value in spacing]


def main():
    args = parse_args()
    image, metadata = read_image(args.image)
    spacing = resolve_spacing_zyx_um(args.spacing_zyx_um, metadata)
    mask = np.load(args.mask_npy, mmap_mode="r")
    if args.mask_source_bbox:
        z0, z1, y0, y1, x0, x1 = args.mask_source_bbox
        mask = np.asarray(mask[z0:z1, y0:y1, x0:x1])
    else:
        mask = np.asarray(mask)
    cleaned, cleaned_mask, audit = prepare_brain_region_input(
        image,
        mask,
        spacing,
        accepted_values=tuple(dict.fromkeys(args.accepted_value or [2])),
        profile={"context_margin_um": args.context_margin_um},
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    image_out = args.output_dir / f"{args.case_id}_0000.nii.gz"
    mask_out = args.output_dir / f"{args.case_id}_whole_brain_mask.nii.gz"
    output_metadata = {
        "spacing_zyx": audit["output_spacing_zyx_um"],
        "spacing_unit": "micrometer",
        "scale_verified": True,
    }
    write_nifti_volume(image_out, cleaned, output_metadata)
    write_nifti_volume(mask_out, cleaned_mask, output_metadata)
    audit.update(
        {
            "source_image": str(args.image.resolve()),
            "source_mask": str(args.mask_npy.resolve()),
            "cleaned_image": str(image_out.resolve()),
            "cleaned_mask": str(mask_out.resolve()),
        }
    )
    if audit["status"] != "ready":
        locator, locator_spacing = prepare_locator_candidate(
            image,
            spacing,
            audit["locator_fallback_bbox_zyx_exclusive"],
            DEFAULT_REGION_INPUT_PROFILE["target_spacing_zyx_um"],
        )
        locator_out = args.output_dir / f"{args.case_id}_locator_candidate_REVIEW_ONLY_0000.nii.gz"
        write_nifti_volume(
            locator_out,
            locator,
            {
                "spacing_zyx": locator_spacing,
                "spacing_unit": "micrometer",
                "scale_verified": True,
            },
        )
        audit["locator_candidate"] = str(locator_out.resolve())
        audit["locator_candidate_prediction_allowed"] = False
    atomic_write_json(args.output_dir / f"{args.case_id}_cleaning_audit.json", audit, indent=2, ensure_ascii=False)
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    return 0 if audit["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
