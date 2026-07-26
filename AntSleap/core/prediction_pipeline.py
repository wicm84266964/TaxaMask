from __future__ import annotations

import os
import secrets
import time

import numpy as np
import torch
from PIL import Image

try:
    from AntSleap.app_runtime import runtime_log_event
except ImportError:
    from app_runtime import runtime_log_event

from .cascade_routes import route_manifest_has_routes
from .projection import CoordinateMapper
from .training_preflight import format_size_pair


EMPTY_PREDICTION = {"polygons": {}, "auto_boxes": {}, "scores": {}, "meta": {}}
_DETAIL_ENV = "TAXAMASK_PREDICTION_DIAGNOSTICS"


def _elapsed_ms(started):
    return round((time.perf_counter() - started) * 1000.0, 3)


def _diagnostic_details_enabled():
    return str(os.environ.get(_DETAIL_ENV, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _event_context(image_path, model_profile_context):
    context = model_profile_context or {}
    return {
        "prediction_id": str(
            context.get("prediction_run_id") or f"predict_{secrets.token_hex(6)}"
        ),
        "image": os.path.basename(os.fspath(image_path)),
        "image_uid": str(context.get("image_uid") or ""),
        "specimen_id": str(context.get("specimen_id") or ""),
        "model_profile_id": str(context.get("active_profile_id") or ""),
        "parent_backend": str(context.get("parent_backend") or ""),
    }


def _emit(event, event_context, **fields):
    clean_fields = {key: value for key, value in fields.items() if value is not None}
    runtime_log_event(event, **event_context, **clean_fields)


def _prepare_input(engine, image_path):
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as exc:
        return None, type(exc).__name__

    original_width, original_height = image.size
    locator_size = getattr(engine, "locator_resolution", (512, 512)) or (512, 512)
    try:
        locator_width = max(1, int(locator_size[0]))
        locator_height = max(1, int(locator_size[1]))
    except Exception:
        locator_width, locator_height = 512, 512

    scale = min(
        float(locator_width) / original_width,
        float(locator_height) / original_height,
    )
    resized_width = int(original_width * scale)
    resized_height = int(original_height * scale)
    pad_width = (locator_width - resized_width) // 2
    pad_height = (locator_height - resized_height) // 2
    bilinear = (
        Image.Resampling.BILINEAR
        if hasattr(Image, "Resampling")
        else getattr(Image, "BILINEAR", 2)
    )
    resized = image.resize((resized_width, resized_height), bilinear)
    locator_image = Image.new("RGB", (locator_width, locator_height), (0, 0, 0))
    locator_image.paste(resized, (pad_width, pad_height))
    tensor = (
        torch.from_numpy(np.array(locator_image))
        .permute(2, 0, 1)
        .float()
        .unsqueeze(0)
        .to(engine.device)
        / 255.0
    )
    return (
        {
            "image": image,
            "original_width": original_width,
            "original_height": original_height,
            "locator_width": locator_width,
            "locator_height": locator_height,
            "scale": scale,
            "pad_width": pad_width,
            "pad_height": pad_height,
            "tensor": tensor,
        },
        "",
    )


def _run_locator(locator, prepared_input):
    with torch.no_grad():
        heatmaps, box_sizes = locator(prepared_input["tensor"])
        return heatmaps.cpu().numpy()[0], box_sizes.cpu().numpy()[0]


def _prepare_routes(engine, project_route_manifest):
    manager = getattr(engine, "cascade_manager", None)
    get_manifest = getattr(manager, "get_runtime_route_manifest", None)
    if callable(get_manifest):
        manifest = get_manifest(project_route_manifest)
    else:
        manifest = (
            project_route_manifest
            if isinstance(project_route_manifest, dict)
            else {}
        )
    source = (
        "project"
        if route_manifest_has_routes(project_route_manifest or {})
        else "legacy_global"
    )
    routes_ready = getattr(manager, "routes_ready", None)
    if callable(routes_ready):
        try:
            ready = bool(routes_ready(manifest))
        except TypeError:
            ready = bool(routes_ready())
    else:
        ready = False
    if not ready and source != "project":
        source = "none"
    return {
        "manager": manager,
        "manifest": manifest,
        "source": source,
        "ready": ready,
        "block_reasons": {},
        "attempted": [],
        "applied": [],
        "applied_count": 0,
    }


def _routes_for_child(route_state, child_part):
    manifest = route_state["manifest"]
    routes = manifest.get("routes", []) if isinstance(manifest, dict) else []
    if not isinstance(routes, list):
        return []
    child = str(child_part or "").strip()
    return [
        route
        for route in routes
        if isinstance(route, dict)
        and str(route.get("child") or "").strip() == child
    ]


def _new_result(
    prepared_input,
    current_taxonomy,
    active_locator_scope,
    route_state,
    model_profile_context,
    conf_thresh,
    adapt_thresh,
    noise_floor,
):
    context = model_profile_context or {}
    manifest = route_state["manifest"]
    return {
        "polygons": {},
        "auto_boxes": {},
        "scores": {},
        "meta": {
            "image_size": [
                float(prepared_input["original_width"]),
                float(prepared_input["original_height"]),
            ],
            "conf_thresh": float(conf_thresh),
            "adapt_thresh": float(adapt_thresh),
            "noise_floor": float(noise_floor),
            "locator_size": [
                int(prepared_input["locator_width"]),
                int(prepared_input["locator_height"]),
            ],
            "locator_resolution_label": format_size_pair(
                (
                    prepared_input["locator_width"],
                    prepared_input["locator_height"],
                )
            ),
            "project_taxonomy": list(current_taxonomy),
            "locator_scope": list(active_locator_scope),
            "cascade_requested": bool(route_state["ready"]),
            "cascade_enabled": bool(route_state["ready"]),
            "cascade_routes_ready": bool(route_state["ready"]),
            "cascade_route_source": route_state["source"],
            "cascade_route_manifest_version": str(manifest.get("version") or ""),
            "model_profile_id": str(context.get("active_profile_id") or ""),
            "parent_backend": str(context.get("parent_backend") or ""),
            "cascade_applied_count": 0,
            "cascade_attempted_routes": route_state["attempted"],
            "cascade_applied_routes": route_state["applied"],
            "cascade_block_reasons": route_state["block_reasons"],
            "cascade_route_backends": [],
            "cascade_route_manifests": [],
        },
    }


def _locator_candidate(
    prepared_input,
    heatmap,
    box_size,
    conf_thresh,
    adapt_thresh,
    box_pad,
    noise_floor,
):
    peak = float(heatmap.max())
    minimum_peak = max(float(conf_thresh), float(noise_floor))
    if peak < minimum_peak:
        return None, "peak_below_threshold", {
            "peak": peak,
            "threshold": minimum_peak,
        }

    effective_threshold = max(float(noise_floor), float(adapt_thresh) * peak)
    filtered = np.where(heatmap >= effective_threshold, heatmap, 0.0)
    if filtered.max() <= 0:
        return None, "activation_below_effective_threshold", {
            "peak": peak,
            "threshold": effective_threshold,
        }

    y_locator, x_locator = np.unravel_index(filtered.argmax(), filtered.shape)
    center_locator_x = float(x_locator)
    center_locator_y = float(y_locator)
    locator_width = prepared_input["locator_width"]
    locator_height = prepared_input["locator_height"]
    predicted_width = max(float(box_size[0]) * float(locator_width), 10.0)
    predicted_height = max(float(box_size[1]) * float(locator_height), 10.0)
    box_width = predicted_width * (1.0 + float(box_pad))
    box_height = predicted_height * (1.0 + float(box_pad))
    scale = prepared_input["scale"]
    center_x = (center_locator_x - prepared_input["pad_width"]) / scale
    center_y = (center_locator_y - prepared_input["pad_height"]) / scale
    half_width = (box_width / scale) / 2.0
    half_height = (box_height / scale) / 2.0

    crop_width = max(half_width * 2 + 200, 512)
    crop_height = max(half_height * 2 + 200, 512)
    left = max(0, int(center_x - crop_width / 2))
    top = max(0, int(center_y - crop_height / 2))
    right = min(
        prepared_input["original_width"], int(center_x + crop_width / 2)
    )
    bottom = min(
        prepared_input["original_height"], int(center_y + crop_height / 2)
    )
    crop = prepared_input["image"].crop((left, top, right, bottom))
    if crop.width < 2 or crop.height < 2:
        return None, "crop_too_small", {"peak": peak}

    relative_x = center_x - left
    relative_y = center_y - top
    x1 = max(0.0, relative_x - half_width)
    y1 = max(0.0, relative_y - half_height)
    x2 = min(float(crop.width), relative_x + half_width)
    y2 = min(float(crop.height), relative_y + half_height)
    x1 = max(0.0, min(x1, float(crop.width - 1)))
    y1 = max(0.0, min(y1, float(crop.height - 1)))
    x2 = max(x1 + 1.0, min(x2, float(crop.width)))
    y2 = max(y1 + 1.0, min(y2, float(crop.height)))
    prompt_box = [x1, y1, x2, y2]
    if x2 <= x1 or y2 <= y1:
        return None, "prompt_box_invalid", {
            "peak": peak,
            "prompt_box": prompt_box,
        }
    return (
        {
            "peak": peak,
            "crop": crop,
            "left": left,
            "top": top,
            "prompt_box": prompt_box,
            "original_box": [x1 + left, y1 + top, x2 + left, y2 + top],
        },
        "",
        {},
    )


def _normalize_expert_result(expert_result):
    expert_box = None
    expert_confidence = 0.0
    if isinstance(expert_result, dict):
        raw_box = expert_result.get("box")
        if isinstance(raw_box, (list, tuple)) and len(raw_box) == 4:
            expert_box = list(raw_box)
        raw_confidence = expert_result.get("confidence", 0.0)
        if isinstance(raw_confidence, (int, float)):
            expert_confidence = float(raw_confidence)
    elif isinstance(expert_result, (list, tuple)) and len(expert_result) == 4:
        expert_box = list(expert_result)
        expert_confidence = 1.0
    return expert_box, expert_confidence


def _confidence_gate(manager, parent_part, child_part, manifest, conf_thresh):
    minimum = manager.get_route_min_conf(
        parent_part,
        child_part,
        route_manifest=manifest,
    )
    gate = float(conf_thresh)
    if isinstance(minimum, (int, float)):
        gate = max(gate, float(minimum))
    return gate


def _detail_box(box):
    if not _diagnostic_details_enabled():
        return None
    return ",".join(f"{float(value):.3f}" for value in box)


def _run_sam(
    engine,
    result,
    part_name,
    crop,
    prompt_box,
    left,
    top,
    poly_epsilon,
    image_size,
    event_context,
):
    started = time.perf_counter()
    polygon = engine._run_sam_polygon(
        crop,
        prompt_box,
        left,
        top,
        poly_epsilon,
        image_size,
    )
    if polygon:
        result["polygons"][part_name] = polygon
    _emit(
        "prediction_sam_result",
        event_context,
        part=part_name,
        status="polygon" if polygon else "no_polygon",
        vertex_count=len(polygon) if polygon else 0,
        stage_ms=_elapsed_ms(started),
        prompt_box=_detail_box(prompt_box),
    )
    return bool(polygon)


def _process_locator_scope(
    engine,
    image_path,
    prepared_input,
    heatmaps,
    box_sizes,
    active_locator_scope,
    result,
    route_state,
    event_context,
    conf_thresh,
    adapt_thresh,
    box_pad,
    noise_floor,
    poly_epsilon,
):
    image_size = (
        prepared_input["original_width"],
        prepared_input["original_height"],
    )
    manager = route_state["manager"]
    manifest = route_state["manifest"]
    for index, part_name in enumerate(active_locator_scope):
        if index >= heatmaps.shape[0]:
            break
        candidate, skip_reason, skip_fields = _locator_candidate(
            prepared_input,
            heatmaps[index],
            box_sizes[index],
            conf_thresh,
            adapt_thresh,
            box_pad,
            noise_floor,
        )
        if candidate is None:
            _emit(
                "prediction_locator_candidate_skipped",
                event_context,
                part=part_name,
                reason=skip_reason,
                **skip_fields,
            )
            continue

        original_box = list(candidate["original_box"])
        if route_state["ready"]:
            parent_part = "macro_locator"
            route = manager._find_route(
                parent_part,
                part_name,
                route_manifest=manifest,
            )
            if route is not None:
                block_reason = manager.get_route_block_reason(route)
                if block_reason:
                    route_state["block_reasons"][part_name] = block_reason
                    _emit(
                        "prediction_route_decision",
                        event_context,
                        parent=parent_part,
                        part=part_name,
                        outcome="rejected",
                        reason=block_reason,
                    )
                else:
                    route_state["attempted"].append(manager.describe_route(route))
                    expert_result = manager.infer_child_part(
                        image_path,
                        parent_box=original_box,
                        child_part_name=part_name,
                        parent_part=parent_part,
                        route_manifest=manifest,
                    )
                    expert_box, expert_confidence = _normalize_expert_result(
                        expert_result
                    )
                    if expert_box:
                        expert_box = CoordinateMapper.clamp_bbox_to_size(
                            expert_box,
                            *image_size,
                        )
                        gate = _confidence_gate(
                            manager,
                            parent_part,
                            part_name,
                            manifest,
                            conf_thresh,
                        )
                        if expert_confidence >= gate:
                            original_box = expert_box
                            route_state["applied_count"] += 1
                            route_state["applied"].append(
                                manager.describe_route(route)
                            )
                            local_box = [
                                expert_box[0] - candidate["left"],
                                expert_box[1] - candidate["top"],
                                min(
                                    float(candidate["crop"].width),
                                    expert_box[2] - candidate["left"],
                                ),
                                min(
                                    float(candidate["crop"].height),
                                    expert_box[3] - candidate["top"],
                                ),
                            ]
                            local_box[0] = max(0.0, local_box[0])
                            local_box[1] = max(0.0, local_box[1])
                            if local_box[2] > local_box[0] and local_box[3] > local_box[1]:
                                candidate["prompt_box"] = local_box
                            _emit(
                                "prediction_route_decision",
                                event_context,
                                parent=parent_part,
                                part=part_name,
                                outcome="applied",
                                confidence=expert_confidence,
                                gate=gate,
                                box=_detail_box(expert_box),
                            )
                        else:
                            reason = "confidence_below_gate"
                            route_state["block_reasons"][part_name] = reason
                            _emit(
                                "prediction_route_decision",
                                event_context,
                                parent=parent_part,
                                part=part_name,
                                outcome="rejected",
                                reason=reason,
                                confidence=expert_confidence,
                                gate=gate,
                            )
                    else:
                        reason = "expert_unavailable"
                        route_state["block_reasons"][part_name] = reason
                        _emit(
                            "prediction_route_decision",
                            event_context,
                            parent=parent_part,
                            part=part_name,
                            outcome="rejected",
                            reason=reason,
                        )

        final_box = CoordinateMapper.clamp_bbox_to_size(
            original_box,
            *image_size,
        )
        result["auto_boxes"][part_name] = [float(value) for value in final_box]
        result["scores"][part_name] = candidate["peak"]
        _run_sam(
            engine,
            result,
            part_name,
            candidate["crop"],
            candidate["prompt_box"],
            candidate["left"],
            candidate["top"],
            poly_epsilon,
            image_size,
            event_context,
        )


def _record_child_route_rejection(
    route_state,
    event_context,
    parent_part,
    child_part,
    reason,
    **fields,
):
    route_state["block_reasons"][child_part] = reason
    _emit(
        "prediction_route_decision",
        event_context,
        parent=parent_part,
        part=child_part,
        outcome="rejected",
        reason=reason,
        **fields,
    )


def _process_child_routes(
    engine,
    image_path,
    prepared_input,
    current_taxonomy,
    active_locator_scope,
    result,
    route_state,
    event_context,
    conf_thresh,
    poly_epsilon,
):
    manager = route_state["manager"]
    manifest = route_state["manifest"]
    if not route_state["ready"]:
        if route_state["source"] == "project":
            routes = manifest.get("routes", []) if isinstance(manifest, dict) else []
            routes = routes if isinstance(routes, list) else []
            for route in routes:
                if not isinstance(route, dict):
                    continue
                child = str(route.get("child") or "").strip()
                if (
                    not child
                    or child in active_locator_scope
                    or child in result["auto_boxes"]
                    or child in route_state["block_reasons"]
                ):
                    continue
                reason = manager.get_route_block_reason(route) or "route_disabled"
                _record_child_route_rejection(
                    route_state,
                    event_context,
                    str(route.get("parent") or ""),
                    child,
                    reason,
                )
        return

    image_size = (
        prepared_input["original_width"],
        prepared_input["original_height"],
    )
    available_parents = list(result["auto_boxes"].keys())
    for child_part in current_taxonomy:
        if child_part in active_locator_scope or child_part in result["auto_boxes"]:
            continue
        route = manager.resolve_route_for_child(
            child_part,
            available_parents,
            route_manifest=manifest,
        )
        if not route:
            configured = _routes_for_child(route_state, child_part)
            if configured:
                enabled = [route for route in configured if bool(route.get("enabled", False))]
                reason = "parent_box_missing" if enabled else "route_disabled"
                _record_child_route_rejection(
                    route_state,
                    event_context,
                    "",
                    child_part,
                    reason,
                )
            else:
                _emit(
                    "prediction_route_decision",
                    event_context,
                    parent="",
                    part=child_part,
                    outcome="skipped",
                    reason="route_not_configured",
                )
            continue

        parent_part = str(route.get("parent", "")).strip()
        block_reason = manager.get_route_block_reason(route)
        if block_reason:
            _record_child_route_rejection(
                route_state,
                event_context,
                parent_part,
                child_part,
                block_reason,
            )
            continue
        route_state["attempted"].append(manager.describe_route(route))
        parent_box = result["auto_boxes"].get(parent_part)
        if not parent_box:
            _record_child_route_rejection(
                route_state,
                event_context,
                parent_part,
                child_part,
                "parent_box_missing",
            )
            continue

        expert_result = manager.infer_child_part(
            image_path,
            parent_box=parent_box,
            child_part_name=child_part,
            parent_part=parent_part,
            route_manifest=manifest,
        )
        expert_box, expert_confidence = _normalize_expert_result(expert_result)
        if not expert_box:
            _record_child_route_rejection(
                route_state,
                event_context,
                parent_part,
                child_part,
                "expert_unavailable",
            )
            continue
        expert_box = CoordinateMapper.clamp_bbox_to_size(expert_box, *image_size)
        gate = _confidence_gate(
            manager,
            parent_part,
            child_part,
            manifest,
            conf_thresh,
        )
        if expert_confidence < gate:
            _record_child_route_rejection(
                route_state,
                event_context,
                parent_part,
                child_part,
                "confidence_below_gate",
                confidence=expert_confidence,
                gate=gate,
            )
            continue

        clamped_parent = CoordinateMapper.clamp_bbox_to_size(parent_box, *image_size)
        parent_x1, parent_y1, parent_x2, parent_y2 = CoordinateMapper.sanitize_bbox_xyxy(
            clamped_parent
        )
        crop_left = max(0, int(np.floor(parent_x1)))
        crop_top = max(0, int(np.floor(parent_y1)))
        crop_right = min(image_size[0], int(np.ceil(parent_x2)))
        crop_bottom = min(image_size[1], int(np.ceil(parent_y2)))
        if crop_right <= crop_left or crop_bottom <= crop_top:
            _record_child_route_rejection(
                route_state,
                event_context,
                parent_part,
                child_part,
                "parent_crop_invalid",
            )
            continue

        parent_crop = prepared_input["image"].crop(
            (crop_left, crop_top, crop_right, crop_bottom)
        )
        prompt_box = CoordinateMapper.clamp_bbox_to_size(
            [
                expert_box[0] - crop_left,
                expert_box[1] - crop_top,
                expert_box[2] - crop_left,
                expert_box[3] - crop_top,
            ],
            parent_crop.width,
            parent_crop.height,
        )
        result["auto_boxes"][child_part] = [float(value) for value in expert_box]
        result["scores"][child_part] = expert_confidence
        route_state["applied_count"] += 1
        route_state["applied"].append(manager.describe_route(route))
        _emit(
            "prediction_route_decision",
            event_context,
            parent=parent_part,
            part=child_part,
            outcome="applied",
            confidence=expert_confidence,
            gate=gate,
            box=_detail_box(expert_box),
        )
        if not _run_sam(
            engine,
            result,
            child_part,
            parent_crop,
            prompt_box,
            crop_left,
            crop_top,
            poly_epsilon,
            image_size,
            event_context,
        ):
            route_state["block_reasons"][child_part] = "sam_polygon_missing"


def _unique(items):
    result = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _finalize_result(result, route_state):
    result["meta"]["cascade_attempted_routes"] = _unique(route_state["attempted"])
    result["meta"]["cascade_applied_routes"] = _unique(route_state["applied"])
    result["meta"]["cascade_applied_count"] = route_state["applied_count"]
    backends = []
    manifests = []
    manifest = route_state["manifest"]
    routes = manifest.get("routes", []) if isinstance(manifest, dict) else []
    for route in routes:
        if not isinstance(route, dict):
            continue
        backend = str(route.get("expert_backend") or "vit_b_blink").strip() or "vit_b_blink"
        label = f"{route.get('parent', '?')}->{route.get('child', '?')}:{backend}"
        if label not in backends:
            backends.append(label)
        manifest_path = str(route.get("expert_manifest") or "").strip()
        if manifest_path and manifest_path not in manifests:
            manifests.append(manifest_path)
    result["meta"]["cascade_route_backends"] = backends
    result["meta"]["cascade_route_manifests"] = manifests
    return result


def predict_full_pipeline(
    engine,
    image_path,
    current_taxonomy=None,
    locator_scope=None,
    conf_thresh=0.1,
    adapt_thresh=0.4,
    box_pad=0.4,
    noise_floor=0.15,
    poly_epsilon=2.0,
    project_route_manifest=None,
    model_profile_context=None,
):
    started = time.perf_counter()
    event_context = _event_context(image_path, model_profile_context)
    _emit(
        "prediction_begin",
        event_context,
        locator_model=str(
            getattr(engine, "loaded_locator_reference", "") or "base_untrained"
        ),
        segmenter_model=str(
            getattr(engine, "loaded_sam_decoder_reference", "") or "base_sam"
        ),
        conf_thresh=float(conf_thresh),
        adapt_thresh=float(adapt_thresh),
        box_pad=float(box_pad),
        noise_floor=float(noise_floor),
        poly_epsilon=float(poly_epsilon),
    )
    try:
        locator = engine.ensure_locator_loaded()
        locator.eval()
        parts_model = engine.ensure_parts_model_loaded()
        parts_model.sam_model.eval()

        input_started = time.perf_counter()
        prepared_input, input_error = _prepare_input(engine, image_path)
        if prepared_input is None:
            _emit(
                "prediction_failed",
                event_context,
                stage="input",
                error_type=input_error,
                total_ms=_elapsed_ms(started),
            )
            return {key: dict(value) for key, value in EMPTY_PREDICTION.items()}
        _emit(
            "prediction_input_ready",
            event_context,
            input_width=prepared_input["original_width"],
            input_height=prepared_input["original_height"],
            locator_width=prepared_input["locator_width"],
            locator_height=prepared_input["locator_height"],
            stage_ms=_elapsed_ms(input_started),
        )

        locator_started = time.perf_counter()
        heatmaps, box_sizes = _run_locator(locator, prepared_input)
        current_taxonomy, active_locator_scope = engine._resolve_taxonomy_scopes(
            current_taxonomy,
            locator_scope,
        )
        if len(active_locator_scope) != heatmaps.shape[0]:
            _emit(
                "prediction_locator_scope_mismatch",
                event_context,
                scope_count=len(active_locator_scope),
                model_channel_count=int(heatmaps.shape[0]),
            )
        _emit(
            "prediction_locator_complete",
            event_context,
            scope_count=len(active_locator_scope),
            model_channel_count=int(heatmaps.shape[0]),
            stage_ms=_elapsed_ms(locator_started),
        )

        route_state = _prepare_routes(engine, project_route_manifest)
        result = _new_result(
            prepared_input,
            current_taxonomy,
            active_locator_scope,
            route_state,
            model_profile_context,
            conf_thresh,
            adapt_thresh,
            noise_floor,
        )
        _process_locator_scope(
            engine,
            image_path,
            prepared_input,
            heatmaps,
            box_sizes,
            active_locator_scope,
            result,
            route_state,
            event_context,
            conf_thresh,
            adapt_thresh,
            box_pad,
            noise_floor,
            poly_epsilon,
        )
        _process_child_routes(
            engine,
            image_path,
            prepared_input,
            current_taxonomy,
            active_locator_scope,
            result,
            route_state,
            event_context,
            conf_thresh,
            poly_epsilon,
        )
        result = _finalize_result(result, route_state)
        _emit(
            "prediction_complete",
            event_context,
            box_count=len(result["auto_boxes"]),
            polygon_count=len(result["polygons"]),
            cascade_applied_count=result["meta"]["cascade_applied_count"],
            total_ms=_elapsed_ms(started),
        )
        return result
    except Exception as exc:
        _emit(
            "prediction_failed",
            event_context,
            stage="pipeline",
            error_type=type(exc).__name__,
            total_ms=_elapsed_ms(started),
        )
        raise


__all__ = ["predict_full_pipeline"]
