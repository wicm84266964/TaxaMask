import numpy as np


LOCAL_AXIS_SOURCE_Z_SIGNAL_SCHEMA_VERSION = "taxamask_local_axis_source_z_signal_v1"


def compute_source_z_signal(volume, max_samples_per_slice=20000):
    array = np.asarray(volume)
    if array.ndim != 3:
        raise ValueError(f"volume_must_be_3d:{array.ndim}")
    z_count = int(array.shape[0])
    if z_count <= 0:
        raise ValueError("volume_must_have_z_slices")
    signals = []
    occupancies = []
    thresholds = []
    for z_index in range(z_count):
        plane = np.asarray(array[z_index], dtype=np.float32)
        finite = plane[np.isfinite(plane)]
        if finite.size == 0:
            signals.append(0.0)
            occupancies.append(0.0)
            thresholds.append(0.0)
            continue
        if finite.size > int(max_samples_per_slice):
            stride = max(1, int(np.ceil(finite.size / float(max_samples_per_slice))))
            sample = finite[::stride]
        else:
            sample = finite
        low = float(np.percentile(sample, 20))
        high = float(np.percentile(sample, 98))
        threshold = low + (high - low) * 0.25
        mask = finite > threshold
        if np.any(mask):
            values = finite[mask] - threshold
            signal = float(np.mean(values)) * float(np.count_nonzero(mask))
        else:
            signal = 0.0
        signals.append(signal)
        occupancies.append(float(np.count_nonzero(mask)) / float(max(1, finite.size)))
        thresholds.append(threshold)
    signal = np.asarray(signals, dtype=np.float64)
    max_signal = float(np.max(signal)) if signal.size else 0.0
    if max_signal > 0:
        normalized = (signal / max_signal).tolist()
    else:
        normalized = [0.0 for _ in range(z_count)]
    return {
        "schema_version": LOCAL_AXIS_SOURCE_Z_SIGNAL_SCHEMA_VERSION,
        "axis": "source_z",
        "role": "navigation_diagnostic_only",
        "slice_count": z_count,
        "signal": [float(value) for value in signal.tolist()],
        "normalized_signal": [float(value) for value in normalized],
        "occupancy_fraction": [float(value) for value in occupancies],
        "thresholds": [float(value) for value in thresholds],
    }


def analyze_source_z_signal(signal_payload):
    payload = signal_payload if isinstance(signal_payload, dict) else {}
    normalized = np.asarray(payload.get("normalized_signal") or [], dtype=np.float64)
    warnings = ["source_z_signal_is_auxiliary_navigation_only"]
    summary = {
        "slice_count": int(payload.get("slice_count") or len(normalized)),
        "peak_slice": None,
        "active_slice_count": 0,
        "active_fraction": 0.0,
        "gap_count": 0,
        "warnings": warnings,
    }
    if normalized.size == 0:
        warnings.append("empty_signal")
        return summary
    peak_index = int(np.argmax(normalized))
    peak_value = float(normalized[peak_index])
    summary["peak_slice"] = peak_index
    if peak_value <= 1e-8:
        warnings.append("low_dynamic_range")
        return summary
    active = normalized >= max(0.12, peak_value * 0.12)
    active_indices = np.flatnonzero(active)
    summary["active_slice_count"] = int(active_indices.size)
    summary["active_fraction"] = float(active_indices.size) / float(max(1, normalized.size))
    if active_indices.size == 0:
        warnings.append("no_active_source_z_region")
        return summary
    gaps = int(np.count_nonzero(np.diff(active_indices) > 1))
    summary["gap_count"] = gaps
    if gaps:
        warnings.append("fragmented_source_z_signal")
    if active_indices.size <= max(2, int(round(normalized.size * 0.05))):
        warnings.append("very_short_source_z_signal")
    if peak_index <= 1 or peak_index >= int(normalized.size) - 2:
        warnings.append("peak_near_stack_edge")
    if summary["active_fraction"] > 0.88:
        warnings.append("signal_spans_most_slices_container_or_support_possible")
    first = int(active_indices[0])
    last = int(active_indices[-1])
    summary["active_range_zyx"] = [first, last]
    summary["message"] = "This source Z signal can help navigation and quality checks, but it is not an anatomical direction decision."
    return summary
