import math


_PRIMARY_POINT_FIELDS = (
    "origin_zyx",
    "output_axis_start_zyx",
    "output_axis_end_zyx",
)


def _point_values(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError, OverflowError):
        return None


def _shape_values(value):
    values = _point_values(value)
    if values is None or any(not math.isfinite(item) or item <= 0 for item in values):
        return None
    return values


def _point_errors(field_name, value, shape):
    values = _point_values(value)
    if values is None:
        return [f"{field_name}_must_have_3_numeric_values"], None
    if any(not math.isfinite(item) for item in values):
        return [f"{field_name}_must_be_finite"], None
    if shape is not None and any(
        item < 0.0 or item > shape[index] - 1.0
        for index, item in enumerate(values)
    ):
        return [f"{field_name}_out_of_bounds"], values
    return [], values


def local_frame_proposal_geometry_errors(
    proposal,
    *,
    shape_zyx=None,
    require_shape=False,
):
    source = proposal if isinstance(proposal, dict) else {}
    shape = _shape_values(shape_zyx) if shape_zyx is not None else None
    errors = []
    if require_shape and shape is None:
        errors.append("part_shape_zyx_must_have_3_positive_values")

    points = {}
    for field_name in _PRIMARY_POINT_FIELDS:
        point_errors, values = _point_errors(field_name, source.get(field_name), shape)
        errors.extend(point_errors)
        points[field_name] = values

    roll_reference = source.get("roll_reference")
    if isinstance(roll_reference, dict):
        for point_name in ("point_a", "point_b", "point_c"):
            point_record = roll_reference.get(point_name)
            if not isinstance(point_record, dict) or "zyx" not in point_record:
                continue
            point_errors, _ = _point_errors(
                f"roll_reference_{point_name}_zyx",
                point_record.get("zyx"),
                shape,
            )
            errors.extend(point_errors)

    start = points.get("output_axis_start_zyx")
    end = points.get("output_axis_end_zyx")
    if start is not None and end is not None and all(
        math.isfinite(item) for item in start + end
    ):
        squared_distance = sum(
            (end[index] - start[index]) ** 2 for index in range(3)
        )
        if squared_distance <= 1e-16:
            errors.append("output_axis_points_must_not_overlap")
    return errors


def require_valid_local_frame_proposal_geometry(
    proposal,
    *,
    shape_zyx=None,
    require_shape=False,
):
    errors = local_frame_proposal_geometry_errors(
        proposal,
        shape_zyx=shape_zyx,
        require_shape=require_shape,
    )
    if errors:
        raise ValueError("invalid_local_frame_proposal_geometry:" + ",".join(errors))
    return True


def global_roi_proposal_geometry_errors(
    proposal,
    *,
    shape_zyx=None,
    require_shape=False,
):
    source = proposal if isinstance(proposal, dict) else {}
    shape = _shape_values(shape_zyx) if shape_zyx is not None else None
    errors = []
    if require_shape and shape is None:
        errors.append("volume_shape_zyx_must_have_3_positive_values")

    bbox = source.get("bbox_zyx")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 3:
        errors.append("bbox_zyx_must_have_3_axis_ranges")
    else:
        for axis, raw_bounds in enumerate(bbox):
            if not isinstance(raw_bounds, (list, tuple)) or len(raw_bounds) != 2:
                errors.append(f"bbox_zyx_axis_{axis}_must_have_2_numeric_values")
                continue
            try:
                lower, upper = (float(raw_bounds[0]), float(raw_bounds[1]))
            except (TypeError, ValueError, OverflowError):
                errors.append(f"bbox_zyx_axis_{axis}_must_have_2_numeric_values")
                continue
            if not math.isfinite(lower) or not math.isfinite(upper):
                errors.append(f"bbox_zyx_axis_{axis}_must_be_finite")
                continue
            if lower >= upper:
                errors.append(f"bbox_zyx_axis_{axis}_must_have_positive_extent")
            if shape is not None and (lower < 0.0 or upper > shape[axis]):
                errors.append(f"bbox_zyx_axis_{axis}_out_of_bounds")

    center_errors, _ = _point_errors(
        "center_zyx",
        source.get("center_zyx"),
        shape,
    )
    errors.extend(center_errors)
    return errors


def require_valid_global_roi_proposal_geometry(
    proposal,
    *,
    shape_zyx=None,
    require_shape=False,
):
    errors = global_roi_proposal_geometry_errors(
        proposal,
        shape_zyx=shape_zyx,
        require_shape=require_shape,
    )
    if errors:
        raise ValueError("invalid_global_roi_proposal_geometry:" + ",".join(errors))
    return True
