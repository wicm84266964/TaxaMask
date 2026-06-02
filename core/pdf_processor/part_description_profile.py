"""Pure-text morphology part-description profile utilities."""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict, List


PART_DESCRIPTION_PROFILE_SCHEMA_VERSION = "taxamask-part-description-profile-v1"


DEFAULT_PART_SCHEMA: List[Dict[str, Any]] = [
    {
        "key": "body_habitus",
        "label": "整体体型/体态",
        "aliases": ["body", "habitus", "whole body", "size", "body length", "worker caste"],
    },
    {"key": "head", "label": "头部", "aliases": ["head", "cephalic", "clypeus", "frons", "vertex", "occipital"]},
    {"key": "mandible", "label": "上颚", "aliases": ["mandible", "mandibles", "mandibular", "masticatory margin", "teeth"]},
    {"key": "antenna_scape", "label": "触角/柄节", "aliases": ["antenna", "antennae", "scape", "funiculus", "antennal"]},
    {"key": "eye_ocelli", "label": "复眼/单眼", "aliases": ["eye", "eyes", "ocellus", "ocelli"]},
    {"key": "mesosoma", "label": "中躯", "aliases": ["mesosoma", "alitrunk", "mesosomal"]},
    {"key": "pronotum", "label": "前胸背板", "aliases": ["pronotum", "pronotal"]},
    {"key": "mesonotum", "label": "中胸", "aliases": ["mesonotum", "mesonotal", "mesopleuron", "mesopleura"]},
    {"key": "propodeum", "label": "并胸腹节", "aliases": ["propodeum", "propodeal", "propodeal spine", "propodeal spines"]},
    {"key": "petiole", "label": "腹柄节", "aliases": ["petiole", "petiolar", "node", "petiolar node"]},
    {"key": "postpetiole", "label": "后腹柄节", "aliases": ["postpetiole", "postpetiolar"]},
    {"key": "gaster", "label": "腹部/膨腹部", "aliases": ["gaster", "gastral", "tergite", "sternite", "abdomen"]},
    {"key": "legs", "label": "足", "aliases": ["leg", "legs", "femur", "femora", "tibia", "tibiae", "tarsus", "tarsi"]},
    {
        "key": "sculpture",
        "label": "体表雕刻",
        "aliases": ["sculpture", "sculpturing", "striation", "reticulation", "punctation", "rugose", "smooth", "shining"],
    },
    {
        "key": "pilosity_pubescence",
        "label": "毛被/立毛",
        "aliases": ["pilosity", "pubescence", "seta", "setae", "hair", "hairs", "erect hairs"],
    },
    {"key": "color", "label": "颜色", "aliases": ["color", "colour", "yellow", "brown", "black", "reddish", "pale"]},
    {"key": "measurements", "label": "测量值", "aliases": ["measurement", "measurements", "HL", "HW", "SL", "EL", "WL", "CI", "SI"]},
    {"key": "caste_stage", "label": "性型/品级差异", "aliases": ["worker", "queen", "male", "gyne", "ergatoid", "larva", "caste"]},
    {
        "key": "other_diagnostic_structure",
        "label": "其他诊断结构",
        "aliases": ["diagnostic", "character", "structure", "spine", "tooth", "carina", "lamella"],
    },
]


DEFAULT_BLOCK_ROLE_VALUES: List[str] = [
    "morphological_description",
    "diagnosis",
    "measurements",
    "material_examined",
    "type_material",
    "distribution",
    "biology",
    "etymology",
    "remarks",
    "figure_caption",
    "identification_key",
    "references",
    "title_or_metadata",
    "unprocessed",
    "other",
]


DEFAULT_PART_DESCRIPTION_PROFILE: Dict[str, Any] = {
    "schema_version": PART_DESCRIPTION_PROFILE_SCHEMA_VERSION,
    "profile_name": "内置蚂蚁分类学部位描述抽取",
    "profile_description": "Built-in pure-text ant taxonomy profile for structuring taxon-to-part morphology descriptions from PDF text blocks.",
    "target_taxon": {
        "display_name": "蚂蚁",
        "scientific_scope": "Formicidae",
        "tested_status": "ant-tested",
    },
    "part_schema": DEFAULT_PART_SCHEMA,
    "block_role_values": DEFAULT_BLOCK_ROLE_VALUES,
    "extraction_settings": {
        "max_input_chars": 600000,
        "max_output_tokens": 12000,
        "timeout": 180,
        "max_retries": 2,
        "persist_unlabeled_blocks": True,
    },
    "prompt": {
        "system_prompt": "你是严谨的分类学文本结构化助手。只根据输入的 PDF 原文文本块工作，只输出 JSON。",
        "user_instructions": (
            "核心任务：从全文文本块中提取“物种/分类单元 -> 具体部位 -> 文中对该部位的描述”。"
            "重点保留 diagnosis、description、measurements、worker/queen/male 等形态描述内容。"
            "material examined、distribution、references、生态/行为等非形态文本不要写入 taxon_part_descriptions，"
            "但可以在 text_block_labels 中标记。每条部位描述必须列出 source_block_refs，且只能使用输入中真实存在的 block_ref。"
            "description_text 应整理自原文，可以轻微合并同一部位的相邻描述，但不要发明新信息。"
        ),
    },
    "mock_fallback": {
        "measurement_terms": ["measurements", " hl ", " hw ", " sl ", " ci ", " si "],
        "reference_terms": ["references", "literature cited"],
    },
}


def default_part_description_profile() -> Dict[str, Any]:
    return copy.deepcopy(DEFAULT_PART_DESCRIPTION_PROFILE)


def load_part_description_profile(profile_path: str | os.PathLike[str] | None) -> Dict[str, Any]:
    if not profile_path:
        return default_part_description_profile()
    path_text = os.fspath(profile_path)
    if not os.path.exists(path_text):
        raise ValueError(f"part_description_profile_not_found:{path_text}")
    try:
        with open(path_text, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"part_description_profile_json_invalid:{path_text}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"part_description_profile_root_not_object:{path_text}")
    return normalize_part_description_profile(payload)


def normalize_part_description_profile(profile: Dict[str, Any] | None) -> Dict[str, Any]:
    if profile is None:
        return default_part_description_profile()
    if not isinstance(profile, dict):
        raise ValueError("part_description_profile_must_be_object")

    normalized = default_part_description_profile()
    _deep_update(normalized, copy.deepcopy(profile))

    schema_version = str(normalized.get("schema_version", "") or "").strip()
    if schema_version and schema_version != PART_DESCRIPTION_PROFILE_SCHEMA_VERSION:
        raise ValueError(f"part_description_profile_schema_unsupported:{schema_version}")
    normalized["schema_version"] = PART_DESCRIPTION_PROFILE_SCHEMA_VERSION
    normalized["profile_name"] = _required_text(normalized.get("profile_name"), "profile_name")

    target_taxon = normalized.get("target_taxon")
    if not isinstance(target_taxon, dict):
        raise ValueError("part_description_profile_target_taxon_invalid")

    normalized["part_schema"] = _part_schema(normalized.get("part_schema"))
    normalized["block_role_values"] = _text_list(normalized.get("block_role_values"), "block_role_values")

    settings = normalized.get("extraction_settings")
    if not isinstance(settings, dict):
        settings = {}
    normalized["extraction_settings"] = {
        "max_input_chars": _positive_int(settings.get("max_input_chars"), 600000, minimum=5000),
        "max_output_tokens": _positive_int(settings.get("max_output_tokens"), 12000, minimum=500),
        "timeout": _positive_int(settings.get("timeout"), 180, minimum=30),
        "max_retries": _positive_int(settings.get("max_retries"), 2, minimum=1),
        "persist_unlabeled_blocks": bool(settings.get("persist_unlabeled_blocks", True)),
    }

    prompt = normalized.get("prompt")
    if not isinstance(prompt, dict):
        prompt = {}
    normalized["prompt"] = {
        "system_prompt": _required_text(prompt.get("system_prompt"), "prompt.system_prompt"),
        "user_instructions": _required_text(prompt.get("user_instructions"), "prompt.user_instructions"),
    }

    mock_fallback = normalized.get("mock_fallback")
    if not isinstance(mock_fallback, dict):
        mock_fallback = {}
    normalized["mock_fallback"] = {
        "measurement_terms": _text_list(mock_fallback.get("measurement_terms"), "mock_fallback.measurement_terms", allow_empty=True),
        "reference_terms": _text_list(mock_fallback.get("reference_terms"), "mock_fallback.reference_terms", allow_empty=True),
    }

    return normalized


def profile_display_name(profile: Dict[str, Any] | None) -> str:
    if not isinstance(profile, dict):
        return ""
    return str(profile.get("profile_name", "") or "").strip()


def _deep_update(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"part_description_profile_field_required:{field_name}")
    return text


def _text_list(value: Any, field_name: str, allow_empty: bool = False) -> List[str]:
    if value is None:
        items: List[Any] = []
    elif isinstance(value, list):
        items = value
    elif isinstance(value, tuple) or isinstance(value, set):
        items = list(value)
    else:
        raise ValueError(f"part_description_profile_field_must_be_list:{field_name}")
    normalized = [str(item).strip() for item in items if str(item).strip()]
    if not normalized and not allow_empty:
        raise ValueError(f"part_description_profile_field_required:{field_name}")
    return normalized


def _part_schema(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("part_description_profile_part_schema_must_be_list")
    normalized: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        label = str(item.get("label", key) or key).strip() or key
        aliases = _text_list(item.get("aliases", []), f"part_schema.{key}.aliases", allow_empty=True)
        normalized.append({"key": key, "label": label, "aliases": aliases})
    if not normalized:
        raise ValueError("part_description_profile_part_schema_empty")
    return normalized


def _positive_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)
