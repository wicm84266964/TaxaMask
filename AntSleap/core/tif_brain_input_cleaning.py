"""Prepare whole-brain predictions for brain-region inference.

The whole-brain network is allowed to locate the brain, but its raw foreground
is never passed through unchecked. This module keeps one dominant component,
builds a physical-unit crop, and records whether the result resembles the
inputs used to train the region model.
"""

from __future__ import annotations

import numpy as np
from skimage.measure import label as connected_components
from skimage.morphology import isotropic_dilation
from skimage.transform import resize


DEFAULT_REGION_INPUT_PROFILE = {
    "name": "Dataset606_AntConfocalCTStyle5Class",
    "target_spacing_zyx_um": [5.4, 5.4, 5.4],
    "crop_margin_um": 54.0,
    "context_margin_um": 20.0,
    "training_fov_min_zyx_um": [270.0, 334.8, 178.2],
    "training_fov_max_zyx_um": [626.4, 653.4, 421.2],
    "training_fov_tolerance": 1.5,
    "mask_fraction_range": [0.05, 0.35],
    "minimum_component_dominance": 0.95,
    "locator_fov_zyx_um": [388.8, 388.8, 280.8],
}


def _spacing(spacing_zyx_um):
    spacing = np.asarray(spacing_zyx_um, dtype=float)
    if spacing.shape != (3,) or not np.all(np.isfinite(spacing)) or np.any(spacing <= 0):
        raise ValueError("brain_cleaning_spacing_must_be_three_positive_values")
    return spacing


def _bounds_from_mask(mask, margin_voxels):
    coords = np.where(mask)
    if not coords[0].size:
        raise ValueError("brain_cleaning_mask_is_empty")
    margin = np.asarray(margin_voxels, dtype=int)
    starts = np.maximum(0, np.asarray([axis.min() for axis in coords]) - margin)
    stops = np.minimum(
        np.asarray(mask.shape),
        np.asarray([axis.max() + 1 for axis in coords]) + margin,
    )
    return starts, stops


def _slice(bounds):
    starts, stops = bounds
    return tuple(slice(int(start), int(stop)) for start, stop in zip(starts, stops))


def largest_component(mask):
    """Return the largest 3-D component and component audit values."""
    binary = np.asarray(mask, dtype=bool)
    labels = connected_components(binary, connectivity=1)
    counts = np.bincount(labels.ravel())
    foreground_counts = counts[1:]
    if not foreground_counts.size or int(foreground_counts.sum()) == 0:
        raise ValueError("brain_cleaning_mask_is_empty")
    largest_id = int(np.argmax(foreground_counts)) + 1
    largest_voxels = int(foreground_counts[largest_id - 1])
    total_voxels = int(foreground_counts.sum())
    return labels == largest_id, {
        "component_count": int(np.count_nonzero(foreground_counts)),
        "accepted_voxels": total_voxels,
        "largest_component_voxels": largest_voxels,
        "largest_component_dominance": largest_voxels / total_voxels,
    }


def centered_crop_bounds(shape_zyx, center_zyx, spacing_zyx_um, extent_zyx_um):
    """Build a clipped fixed-physical-size locator crop around a prediction center."""
    shape = np.asarray(shape_zyx, dtype=int)
    center = np.asarray(center_zyx, dtype=float)
    spacing = _spacing(spacing_zyx_um)
    extent = np.asarray(extent_zyx_um, dtype=float)
    size = np.minimum(shape, np.maximum(1, np.ceil(extent / spacing).astype(int)))
    starts = np.floor(center - size / 2.0).astype(int)
    starts = np.minimum(np.maximum(0, starts), shape - size)
    return starts, starts + size


def _resample(array, output_shape, order, dtype):
    if tuple(array.shape) == tuple(output_shape):
        return np.asarray(array, dtype=dtype)
    result = resize(
        array,
        tuple(int(value) for value in output_shape),
        order=order,
        mode="edge",
        preserve_range=True,
        anti_aliasing=order > 0,
    )
    if np.issubdtype(np.dtype(dtype), np.integer):
        result = np.rint(result)
    return np.asarray(result, dtype=dtype)


def prepare_locator_candidate(volume_zyx, spacing_zyx_um, bbox_zyx_exclusive, target_spacing_zyx_um):
    """Extract a review-only locator crop and resample it without masking anatomy."""
    volume = np.asarray(volume_zyx)
    starts, stops = (np.asarray(values, dtype=int) for values in bbox_zyx_exclusive)
    if np.any(starts < 0) or np.any(stops > volume.shape) or np.any(stops <= starts):
        raise ValueError("brain_locator_bbox_is_invalid")
    spacing = _spacing(spacing_zyx_um)
    target_spacing = _spacing(target_spacing_zyx_um)
    candidate = np.asarray(volume[_slice((starts, stops))])
    physical_extent = np.asarray(candidate.shape, dtype=float) * spacing
    output_shape = np.maximum(1, np.ceil(physical_extent / target_spacing).astype(int))
    output_spacing = physical_extent / output_shape
    return (
        _resample(candidate, output_shape, order=1, dtype=volume.dtype),
        [float(value) for value in output_spacing],
    )


def prepare_brain_region_input(
    volume_zyx,
    prediction_zyx,
    spacing_zyx_um,
    *,
    accepted_values=(2,),
    profile=None,
    background_value=None,
):
    """Return a strict brain-only model input, mask, and an auditable report.

    The output arrays are in ZYX order. A failed quality gate still returns the
    strict result for review, but callers must not launch automatic region
    inference unless ``audit["status"]`` is ``"ready"``.
    """
    volume = np.asarray(volume_zyx)
    prediction = np.asarray(prediction_zyx)
    if volume.ndim != 3 or prediction.shape != volume.shape:
        raise ValueError("brain_cleaning_volume_and_mask_must_share_3d_shape")
    spacing = _spacing(spacing_zyx_um)
    settings = dict(DEFAULT_REGION_INPUT_PROFILE)
    if profile:
        settings.update(profile)

    accepted = np.isin(prediction, np.asarray(tuple(accepted_values)))
    brain_mask, component_audit = largest_component(accepted)
    crop_margin_voxels = np.ceil(float(settings["crop_margin_um"]) / spacing).astype(int)
    crop_bounds = _bounds_from_mask(brain_mask, crop_margin_voxels)
    crop_slice = _slice(crop_bounds)
    cropped_volume = np.asarray(volume[crop_slice])
    cropped_mask = np.asarray(brain_mask[crop_slice])

    context_margin_um = float(settings["context_margin_um"])
    if context_margin_um > 0:
        # Distance-transform dilation has the same physical ellipsoid as a
        # large footprint, without the footprint's radius-dependent cost.
        context_mask = isotropic_dilation(
            cropped_mask,
            radius=context_margin_um,
            spacing=spacing,
        )
    else:
        context_mask = cropped_mask

    if background_value is None:
        border = np.concatenate(
            [
                cropped_volume[0].ravel(),
                cropped_volume[-1].ravel(),
                cropped_volume[:, 0].ravel(),
                cropped_volume[:, -1].ravel(),
                cropped_volume[:, :, 0].ravel(),
                cropped_volume[:, :, -1].ravel(),
            ]
        )
        background_value = float(np.median(border))
    background_value = np.asarray(background_value, dtype=cropped_volume.dtype).item()
    cleaned = np.full(cropped_volume.shape, background_value, dtype=cropped_volume.dtype)
    cleaned[context_mask] = cropped_volume[context_mask]

    target_spacing = _spacing(settings["target_spacing_zyx_um"])
    physical_extent = np.asarray(cleaned.shape, dtype=float) * spacing
    output_shape = np.maximum(1, np.ceil(physical_extent / target_spacing).astype(int))
    output_spacing = physical_extent / output_shape
    cleaned_resampled = _resample(cleaned, output_shape, order=1, dtype=volume.dtype)
    mask_resampled = _resample(cropped_mask.astype(np.uint8), output_shape, order=0, dtype=np.uint8) > 0

    coords = np.where(brain_mask)
    center = [float(axis.mean()) for axis in coords]
    largest_bbox_start, largest_bbox_stop = _bounds_from_mask(brain_mask, [0, 0, 0])
    largest_extent_um = (largest_bbox_stop - largest_bbox_start) * spacing
    output_mask_fraction = float(mask_resampled.mean())
    allowed_min = np.asarray(settings["training_fov_min_zyx_um"], dtype=float) / float(
        settings["training_fov_tolerance"]
    )
    allowed_max = np.asarray(settings["training_fov_max_zyx_um"], dtype=float) * float(
        settings["training_fov_tolerance"]
    )
    fov_pass = bool(np.all(physical_extent >= allowed_min) and np.all(physical_extent <= allowed_max))
    fraction_min, fraction_max = settings["mask_fraction_range"]
    fraction_pass = bool(fraction_min <= output_mask_fraction <= fraction_max)
    dominance_pass = bool(
        component_audit["largest_component_dominance"]
        >= float(settings["minimum_component_dominance"])
    )
    gate_pass = fov_pass and fraction_pass and dominance_pass
    locator_bounds = centered_crop_bounds(
        volume.shape,
        center,
        spacing,
        settings["locator_fov_zyx_um"],
    )
    audit = {
        "schema_version": "taxamask_brain_region_input_cleaning_v1",
        "status": "ready" if gate_pass else "requires_review",
        "profile": settings["name"],
        "source_shape_zyx": [int(value) for value in volume.shape],
        "source_spacing_zyx_um": [float(value) for value in spacing],
        "accepted_values": [int(value) for value in accepted_values],
        **component_audit,
        "largest_component_center_zyx": center,
        "largest_component_bbox_zyx_exclusive": [
            [int(value) for value in largest_bbox_start],
            [int(value) for value in largest_bbox_stop],
        ],
        "largest_component_extent_zyx_um": [float(value) for value in largest_extent_um],
        "crop_bbox_zyx_exclusive": [
            [int(value) for value in crop_bounds[0]],
            [int(value) for value in crop_bounds[1]],
        ],
        "crop_margin_um": float(settings["crop_margin_um"]),
        "context_margin_um": context_margin_um,
        "background_value": background_value,
        "output_shape_zyx": [int(value) for value in cleaned_resampled.shape],
        "output_spacing_zyx_um": [float(value) for value in output_spacing],
        "output_physical_extent_zyx_um": [float(value) for value in physical_extent],
        "output_mask_fraction": output_mask_fraction,
        "quality_gate": {
            "component_dominance_pass": dominance_pass,
            "mask_fraction_pass": fraction_pass,
            "physical_fov_pass": fov_pass,
            "automatic_prediction_allowed": gate_pass,
        },
        "locator_fallback_bbox_zyx_exclusive": [
            [int(value) for value in locator_bounds[0]],
            [int(value) for value in locator_bounds[1]],
        ],
        "locator_fallback_requires_human_confirmation": not gate_pass,
    }
    return cleaned_resampled, mask_resampled.astype(np.uint8), audit
