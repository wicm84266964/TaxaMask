from __future__ import annotations

import base64
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont


VLM_PREANNOTATION_SCHEMA_VERSION = "taxamask-vlm-first-mile-v1"
VLM_PREANNOTATION_IMAGE_MODE = "pixel"

COMMON_ANT_FIRST_MILE_PARTS = [
    "Whole body",
    "Head",
    "Mesosoma",
    "Gaster",
    "Petiole",
    "Postpetiole",
    "Eye",
    "Mandible",
    "Antenna",
    "Scape",
    "Pronotum",
    "Mesonotum",
    "Propodeum",
    "Clypeus",
]

PART_SYNONYMS = {
    "头": "Head",
    "头部": "Head",
    "head": "Head",
    "胸": "Mesosoma",
    "胸部": "Mesosoma",
    "中躯": "Mesosoma",
    "mesosoma": "Mesosoma",
    "腹": "Gaster",
    "腹部": "Gaster",
    "gaster": "Gaster",
    "腹柄": "Petiole",
    "腹柄节": "Petiole",
    "petiole": "Petiole",
    "后腹柄": "Postpetiole",
    "后腹柄节": "Postpetiole",
    "postpetiole": "Postpetiole",
    "眼": "Eye",
    "眼睛": "Eye",
    "复眼": "Eye",
    "eye": "Eye",
    "上颚": "Mandible",
    "大颚": "Mandible",
    "mandible": "Mandible",
    "触角": "Antenna",
    "antenna": "Antenna",
    "柄节": "Scape",
    "触角柄节": "Scape",
    "scape": "Scape",
}


class VlmApiError(RuntimeError):
    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = str(raw_response or "")


def _normalize_name(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"[\s_\-]+", "", text).lower()


def default_vlm_target_parts(
    taxonomy: list[str] | tuple[str, ...] | None,
    locator_scope: list[str] | tuple[str, ...] | None = None,
    selected_part: str | None = None,
    max_parts: int = 18,
) -> list[str]:
    taxonomy_list = [str(part).strip() for part in (taxonomy or []) if str(part).strip()]
    taxonomy_set = set(taxonomy_list)
    ordered: list[str] = []

    def add(part_name: Any) -> None:
        clean = str(part_name or "").strip()
        if not clean or clean in ordered:
            return
        if taxonomy_set and clean not in taxonomy_set:
            return
        ordered.append(clean)

    add(selected_part)
    for part in locator_scope or []:
        add(part)
    for part in COMMON_ANT_FIRST_MILE_PARTS:
        add(part)
    for part in taxonomy_list:
        add(part)
    return ordered[: max(1, int(max_parts))]


def resolve_part_name(raw_part: Any, target_parts: list[str] | tuple[str, ...]) -> str | None:
    text = str(raw_part or "").strip()
    if not text:
        return None
    targets = [str(part).strip() for part in target_parts if str(part).strip()]
    if text in targets:
        return text
    normalized_targets = {_normalize_name(part): part for part in targets}
    normalized = _normalize_name(text)
    if normalized in normalized_targets:
        return normalized_targets[normalized]
    synonym = PART_SYNONYMS.get(text) or PART_SYNONYMS.get(normalized)
    if synonym in targets:
        return synonym
    return None


def _normalize_base_url(raw_base_url: Any) -> str:
    base_text = str(raw_base_url or "").strip().rstrip("/")
    for suffix in ("/chat/completions", "/responses"):
        if base_text.endswith(suffix):
            base_text = base_text[: -len(suffix)]
    return base_text.rstrip("/")


def normalize_vlm_api_config(raw_config: dict[str, Any] | None) -> dict[str, Any]:
    config = dict(raw_config or {})
    protocol = str(config.get("api_protocol", "auto") or "auto").strip().lower()
    if protocol not in {"auto", "chat_completions", "responses"}:
        protocol = "auto"
    image_detail = str(config.get("image_detail", "auto") or "auto").strip().lower()
    if image_detail not in {"auto", "low", "high"}:
        image_detail = "auto"
    return {
        "base_url": _normalize_base_url(config.get("base_url", "")),
        "api_key": str(config.get("api_key", "") or "").strip(),
        "model": str(config.get("model", "") or "").strip(),
        "api_protocol": protocol,
        "image_detail": image_detail,
        "timeout": max(30, int(config.get("timeout", config.get("timeout_seconds", 180)) or 180)),
        "max_tokens": max(500, int(config.get("max_tokens", config.get("batch_max_tokens", 3000)) or 3000)),
    }


def load_vlm_api_config_from_runtime_settings(settings_path: str | os.PathLike[str]) -> dict[str, Any]:
    path = Path(settings_path)
    if not path.exists():
        return normalize_vlm_api_config({})
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return normalize_vlm_api_config({})

    text_payload = payload.get("text_llm") if isinstance(payload.get("text_llm"), dict) else payload
    multimodal_payload = payload.get("multimodal_llm") if isinstance(payload.get("multimodal_llm"), dict) else {}
    use_same = bool(multimodal_payload.get("use_same_as_text", True))
    selected = text_payload if use_same else multimodal_payload
    api_key = str(selected.get("api_key", "") or "").strip()
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    base_url = str(selected.get("base_url", "") or "").strip() or os.environ.get("OPENAI_BASE_URL", "").strip()
    return normalize_vlm_api_config(
        {
            "base_url": base_url,
            "api_key": api_key,
            "model": selected.get("model", ""),
            "api_protocol": selected.get("api_protocol", "auto"),
            "image_detail": multimodal_payload.get("image_detail", "auto"),
        }
    )


def create_grid_overlay(
    image_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    grid_cols: int = 12,
    grid_rows: int = 12,
    max_side: int = 1600,
) -> dict[str, Any]:
    image_path = str(image_path)
    output_path = str(output_path)
    grid_cols = max(2, int(grid_cols))
    grid_rows = max(2, int(grid_rows))
    max_side = max(256, int(max_side))

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
    original_width, original_height = rgb.size
    scale = min(1.0, float(max_side) / float(max(original_width, original_height)))
    if scale < 1.0:
        overlay = rgb.resize((max(1, int(original_width * scale)), max(1, int(original_height * scale))), Image.LANCZOS)
    else:
        overlay = rgb.copy()

    draw = ImageDraw.Draw(overlay, "RGBA")
    width, height = overlay.size
    line_color = (255, 60, 60, 120)
    major_color = (255, 255, 255, 165)
    label_fill = (0, 0, 0, 135)
    text_color = (255, 255, 255, 230)
    try:
        font = ImageFont.truetype("arial.ttf", max(10, int(min(width, height) * 0.018)))
    except Exception:
        font = ImageFont.load_default()

    for col in range(grid_cols + 1):
        x = round(col * width / grid_cols)
        color = major_color if col in {0, grid_cols} else line_color
        draw.line([(x, 0), (x, height)], fill=color, width=1)
        label = str(col)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        lx = max(0, min(width - tw - 4, x + 2))
        draw.rectangle([lx - 2, 1, lx + tw + 2, th + 5], fill=label_fill)
        draw.text((lx, 2), label, fill=text_color, font=font)

    for row in range(grid_rows + 1):
        y = round(row * height / grid_rows)
        color = major_color if row in {0, grid_rows} else line_color
        draw.line([(0, y), (width, y)], fill=color, width=1)
        label = str(row)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        ly = max(0, min(height - th - 4, y + 2))
        draw.rectangle([1, ly - 2, tw + 5, ly + th + 2], fill=label_fill)
        draw.text((2, ly), label, fill=text_color, font=font)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    overlay.save(output_path)
    return {
        "image_path": os.path.abspath(image_path),
        "overlay_path": os.path.abspath(output_path),
        "original_size": [original_width, original_height],
        "overlay_size": [width, height],
        "grid_cols": grid_cols,
        "grid_rows": grid_rows,
        "scale": scale,
    }


def create_preannotation_image(
    image_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    max_side: int = 1600,
) -> dict[str, Any]:
    image_path = str(image_path)
    output_path = str(output_path)
    max_side = max(256, int(max_side))

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
    original_width, original_height = rgb.size
    scale = min(1.0, float(max_side) / float(max(original_width, original_height)))
    if scale < 1.0:
        prepared = rgb.resize((max(1, int(original_width * scale)), max(1, int(original_height * scale))), Image.LANCZOS)
    else:
        prepared = rgb.copy()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    prepared.save(output_path)
    width, height = prepared.size
    return {
        "image_path": os.path.abspath(image_path),
        "overlay_path": os.path.abspath(output_path),
        "prepared_path": os.path.abspath(output_path),
        "original_size": [original_width, original_height],
        "overlay_size": [width, height],
        "prepared_size": [width, height],
        "image_mode": VLM_PREANNOTATION_IMAGE_MODE,
        "grid_cols": 0,
        "grid_rows": 0,
        "scale": scale,
    }


def build_vlm_preannotation_prompt(
    target_parts: list[str] | tuple[str, ...],
    image_size: tuple[int, int],
    input_size: tuple[int, int] | None = None,
    grid_cols: int = 0,
    grid_rows: int = 0,
) -> str:
    input_width, input_height = input_size or image_size
    parts_text = ", ".join(target_parts)
    return (
        "你正在帮助蚂蚁分类学图片完成第一公里预标注。"
        f"当前输入图片像素尺寸为 width={input_width}, height={input_height}。"
        "请直接按当前输入图片像素坐标输出候选框。\n\n"
        "任务：为目标结构画宽松提示框，供 SAM 后续分割和人工复核使用。"
        "这些框不是最终分类学标注；如果目标结构主体可见，请尽量给出候选框，"
        "不要因为局部遮挡、姿态变化或边界不完美就直接漏报。"
        "框应覆盖目标结构主体，允许少量边缘余量，但不要包含明显无关的大面积背景。\n\n"
        "重要标注规则：不同解剖结构的提示框不是互斥切片。"
        "相邻或连接的结构（例如 Head 与 Mesosoma）允许合理重叠；"
        "不要为了让框不重叠而把某个结构挤小、贴边、错开，或切掉真实可见范围。"
        "每个框应以对应结构主体为中心，覆盖该结构完整可见范围，并可与邻近结构框相交。\n\n"
        f"目标结构名称必须从以下列表中原样选择：{parts_text}\n\n"
        "请只输出 JSON 对象，不要输出 Markdown 或解释文字。格式必须为：\n"
        "{\n"
        f'  "schema_version": "{VLM_PREANNOTATION_SCHEMA_VERSION}",\n'
        '  "detections": [\n'
        '    {"part": "Head", "bbox_xyxy": [x1, y1, x2, y2], "confidence": 0.0, "reason": "简短理由"}\n'
        "  ]\n"
        "}\n\n"
        "bbox_xyxy 必须使用当前输入图片像素坐标，格式为左上角 x1,y1 和右下角 x2,y2。"
        "x 的范围是 0 到 width，y 的范围是 0 到 height。"
    )


def _encode_image_as_data_url(image_path: str) -> str:
    with open(image_path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("utf-8")
    ext = os.path.splitext(image_path)[1].lower()
    mime = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64,{encoded}"


def _resolve_api_protocol(config: dict[str, Any]) -> str:
    protocol = str(config.get("api_protocol", "auto") or "auto").strip().lower()
    if protocol in {"chat_completions", "responses"}:
        return protocol
    model_text = str(config.get("model", "") or "").lower()
    base_text = str(config.get("base_url", "") or "").lower()
    if "gmn.chuangzuoli.com" in base_text and "gpt" in model_text:
        return "responses"
    return "chat_completions"


def _json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string"},
            "detections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "part": {"type": "string"},
                        "bbox_xyxy": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["part", "bbox_xyxy", "confidence"],
                    "additionalProperties": True,
                },
            },
        },
        "required": ["detections"],
        "additionalProperties": True,
    }


def call_vlm_preannotation_api(
    api_config: dict[str, Any],
    image_input_path: str,
    prompt: str,
) -> tuple[str, str]:
    config = normalize_vlm_api_config(api_config)
    if not config.get("api_key") or not config.get("base_url") or not config.get("model"):
        raise ValueError("multimodal_api_not_configured")

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    system_prompt = (
        "你是严谨的分类学图像预标注助手。你只返回可解析 JSON，"
        "不把不确定的结构当作确定结果。"
    )
    protocol = _resolve_api_protocol(config)
    if protocol == "responses":
        payload = {
            "model": config["model"],
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": _encode_image_as_data_url(image_input_path)},
                    ],
                },
            ],
            "max_output_tokens": config["max_tokens"],
            "temperature": 0.0,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "taxamask_vlm_first_mile",
                    "strict": True,
                    "schema": _json_schema(),
                }
            },
        }
        response = requests.post(
            f"{config['base_url']}/responses",
            headers=headers,
            json=payload,
            timeout=config["timeout"],
        )
        if response.status_code >= 400:
            raise VlmApiError(f"HTTP {response.status_code} - responses_error", response.text)
        try:
            body = response.json()
        except ValueError as exc:
            preview = response.text[:500].replace("\r", " ").replace("\n", " ").strip()
            raise VlmApiError(f"vlm_api_response_not_json: {preview or 'empty provider response'}", response.text) from exc
        text = str(body.get("output_text", "") or "").strip()
        if not text:
            chunks: list[str] = []
            for item in body.get("output", []) if isinstance(body.get("output"), list) else []:
                for content_item in item.get("content", []) if isinstance(item, dict) else []:
                    if isinstance(content_item, dict) and content_item.get("type") == "output_text":
                        chunks.append(str(content_item.get("text", "") or ""))
            text = "\n".join(chunks).strip()
        finish_reason = str(body.get("status", "") or "stop").strip().lower()
        if not text:
            raise VlmApiError("empty_vlm_output", response.text)
        return text, finish_reason

    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": _encode_image_as_data_url(image_input_path),
                            "detail": config["image_detail"],
                        },
                    },
                ],
            },
        ],
        "max_tokens": config["max_tokens"],
        "temperature": 0.0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "taxamask_vlm_first_mile",
                "strict": True,
                "schema": _json_schema(),
            },
        },
    }
    response = requests.post(
        f"{config['base_url']}/chat/completions",
        headers=headers,
        json=payload,
        timeout=config["timeout"],
    )
    if response.status_code >= 400:
        raise VlmApiError(f"HTTP {response.status_code} - chat_completions_error", response.text)
    try:
        body = response.json()
    except ValueError as exc:
        preview = response.text[:500].replace("\r", " ").replace("\n", " ").strip()
        raise VlmApiError(f"vlm_api_response_not_json: {preview or 'empty provider response'}", response.text) from exc
    choices = body.get("choices", [])
    first_choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    text = str(first_choice.get("message", {}).get("content", "") or "").strip()
    finish_reason = str(first_choice.get("finish_reason", "") or "").strip().lower()
    if not text:
        raise VlmApiError("empty_vlm_output", response.text)
    return text, finish_reason


def _extract_json_payload(raw_response: str) -> Any:
    text = str(raw_response or "").strip()
    if not text:
        raise ValueError("vlm_response_not_json: empty response")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    if not text:
        raise ValueError("vlm_response_not_json: empty response after removing code fences")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        object_match = re.search(r"\{.*\}", text, re.DOTALL)
        if object_match:
            return json.loads(object_match.group())
        array_match = re.search(r"\[.*\]", text, re.DOTALL)
        if array_match:
            return json.loads(array_match.group())
        preview = text[:180].replace("\r", " ").replace("\n", " ")
        raise ValueError(f"vlm_response_not_json: {preview}")


def _as_box_list(raw_box: Any) -> list[float] | None:
    if isinstance(raw_box, dict):
        keys = ("x1", "y1", "x2", "y2")
        if all(key in raw_box for key in keys):
            raw_box = [raw_box[key] for key in keys]
    if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
        return None
    try:
        values = [float(value) for value in raw_box]
    except Exception:
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    return values


def _clamp_box(box: list[float], image_size: tuple[int, int]) -> list[float] | None:
    width, height = image_size
    x1, y1, x2, y2 = box
    x1 = max(0.0, min(float(width) - 0.1, x1))
    x2 = max(0.0, min(float(width) - 0.1, x2))
    y1 = max(0.0, min(float(height) - 0.1, y1))
    y2 = max(0.0, min(float(height) - 0.1, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    if (x2 - x1) < 2.0 or (y2 - y1) < 2.0:
        return None
    return [float(x1), float(y1), float(x2), float(y2)]


def _box_from_detection(
    item: dict[str, Any],
    image_size: tuple[int, int],
    overlay_size: tuple[int, int],
    grid_cols: int,
    grid_rows: int,
    default_coordinate_space: str = "original",
) -> list[float] | None:
    width, height = image_size
    overlay_width, overlay_height = overlay_size
    coordinate_space = str(item.get("coordinate_space", item.get("coord_frame", "")) or default_coordinate_space).strip().lower()

    for key in ("bbox_norm_xyxy", "bbox_normalized", "normalized_bbox"):
        box = _as_box_list(item.get(key))
        if box:
            return _clamp_box([box[0] * width, box[1] * height, box[2] * width, box[3] * height], image_size)

    box = _as_box_list(
        item.get("bbox_xyxy")
        or item.get("bbox_pixels")
        or item.get("box_xyxy")
        or item.get("box")
        or item.get("bbox")
    )
    if box:
        if coordinate_space in {"normalized", "norm", "relative"} or all(0.0 <= value <= 1.0 for value in box):
            return _clamp_box([box[0] * width, box[1] * height, box[2] * width, box[3] * height], image_size)
        if coordinate_space in {"overlay", "overlay_pixel", "overlay_pixels", "input", "input_pixel", "input_pixels", "input_image"}:
            return _clamp_box(
                [
                    box[0] / float(overlay_width) * width,
                    box[1] / float(overlay_height) * height,
                    box[2] / float(overlay_width) * width,
                    box[3] / float(overlay_height) * height,
                ],
                image_size,
            )
        return _clamp_box(box, image_size)

    grid_box = _as_box_list(item.get("bbox_grid_xyxy") or item.get("grid_bbox") or item.get("grid_box"))
    if grid_box and grid_cols > 0 and grid_rows > 0:
        return _clamp_box(
            [
                grid_box[0] / float(grid_cols) * width,
                grid_box[1] / float(grid_rows) * height,
                grid_box[2] / float(grid_cols) * width,
                grid_box[3] / float(grid_rows) * height,
            ],
            image_size,
        )
    return None


def _candidate_items(parsed: Any) -> list[dict[str, Any]]:
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if not isinstance(parsed, dict):
        return []
    for key in ("detections", "candidates", "predictions", "boxes", "results"):
        value = parsed.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def parse_vlm_response(
    raw_response: str,
    target_parts: list[str] | tuple[str, ...],
    image_size: tuple[int, int],
    overlay_size: tuple[int, int] | None = None,
    grid_cols: int = 12,
    grid_rows: int = 12,
    min_confidence: float = 0.0,
    default_coordinate_space: str = "original",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Any]:
    parsed = _extract_json_payload(raw_response)
    overlay_size = overlay_size or image_size
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    best_by_part: dict[str, dict[str, Any]] = {}

    for item in _candidate_items(parsed):
        raw_part = item.get("part", item.get("label", item.get("structure", item.get("name", ""))))
        part_name = resolve_part_name(raw_part, list(target_parts))
        if not part_name:
            rejected.append({"part": str(raw_part or ""), "reason": "unknown_or_untargeted_part"})
            continue
        try:
            confidence = float(item.get("confidence", item.get("score", 0.5)) or 0.0)
        except Exception:
            confidence = 0.0
        if confidence < float(min_confidence):
            rejected.append({"part": part_name, "reason": "below_confidence_threshold"})
            continue
        box = _box_from_detection(
            item,
            image_size,
            overlay_size,
            int(grid_cols),
            int(grid_rows),
            default_coordinate_space=default_coordinate_space,
        )
        if not box:
            rejected.append({"part": part_name, "reason": "invalid_box"})
            continue
        payload = {
            "part": part_name,
            "box_xyxy": box,
            "confidence": max(0.0, min(1.0, confidence)),
            "reason": str(item.get("reason", item.get("rationale", "")) or "").strip(),
            "raw_part": str(raw_part or ""),
        }
        existing = best_by_part.get(part_name)
        if existing is None or payload["confidence"] > existing.get("confidence", 0.0):
            best_by_part[part_name] = payload

    for part_name in target_parts:
        if part_name in best_by_part:
            candidates.append(best_by_part[part_name])
    return candidates, rejected, parsed


def run_vlm_preannotation(
    image_path: str | os.PathLike[str],
    target_parts: list[str] | tuple[str, ...],
    output_dir: str | os.PathLike[str],
    api_config: dict[str, Any] | None = None,
    grid_cols: int = 12,
    grid_rows: int = 12,
    min_confidence: float = 0.25,
    dry_run: bool = False,
    raw_response: str | None = None,
    run_id: str | None = None,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    image_path = os.path.abspath(str(image_path))
    output_dir = os.path.abspath(str(output_dir))
    os.makedirs(output_dir, exist_ok=True)
    started = time.time()
    run_id = str(run_id or time.strftime("%Y%m%d_%H%M%S"))
    overlay_path = os.path.join(output_dir, f"{Path(image_path).stem}_vlm_input_{run_id}.png")
    overlay_meta = create_preannotation_image(image_path, overlay_path)
    if callable(progress_callback):
        progress_callback("prepare")
    image_size = tuple(int(value) for value in overlay_meta["original_size"])
    overlay_size = tuple(int(value) for value in overlay_meta["overlay_size"])
    prompt = build_vlm_preannotation_prompt(list(target_parts), image_size, input_size=overlay_size)

    finish_reason = "dry_run" if dry_run else ""
    raw_text = raw_response or ""
    parsed: Any = {}
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    status = "dry_run" if dry_run else "passed"
    error = ""

    if not dry_run:
        try:
            if raw_text:
                finish_reason = "fixture"
            else:
                raw_text, finish_reason = call_vlm_preannotation_api(api_config or {}, overlay_path, prompt)
            if callable(progress_callback):
                progress_callback("vlm")
            candidates, rejected, parsed = parse_vlm_response(
                raw_text,
                list(target_parts),
                image_size,
                overlay_size=overlay_size,
                grid_cols=grid_cols,
                grid_rows=grid_rows,
                min_confidence=min_confidence,
                default_coordinate_space="input",
            )
            if callable(progress_callback):
                progress_callback("parse")
        except Exception as exc:
            status = "failed"
            error = str(exc)
            raw_error_response = getattr(exc, "raw_response", "")
            if raw_error_response and not raw_text:
                raw_text = str(raw_error_response)
            rejected.append({"part": "", "reason": error})

    raw_response_path = os.path.join(output_dir, f"{Path(image_path).stem}_raw_response_{run_id}.txt")
    if raw_text:
        with open(raw_response_path, "w", encoding="utf-8") as handle:
            handle.write(raw_text)
    else:
        raw_response_path = ""

    result = {
        "schema_version": VLM_PREANNOTATION_SCHEMA_VERSION,
        "status": status,
        "image_path": image_path,
        "target_parts": list(target_parts),
        "overlay": overlay_meta,
        "prompt": prompt,
        "finish_reason": finish_reason,
        "candidates": candidates,
        "rejected": rejected,
        "parsed_response": parsed,
        "raw_response_path": raw_response_path,
        "started_at_unix": started,
        "finished_at_unix": time.time(),
        "duration_seconds": round(time.time() - started, 3),
        "error": error,
    }
    report_path = os.path.join(output_dir, f"{Path(image_path).stem}_vlm_preannotation_{run_id}.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    result["report_path"] = report_path
    if status == "failed":
        raise ValueError(f"{error}; raw_response={raw_response_path or 'not_saved'}; report={report_path}")
    return result
