"""Figure extraction and multimodal review profile utilities."""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict, List


PROFILE_SCHEMA_VERSION = "taxamask-figure-extraction-review-profile-v1"


DEFAULT_FIGURE_PROFILE: Dict[str, Any] = {
    "schema_version": PROFILE_SCHEMA_VERSION,
    "profile_name": "内置蚂蚁三视图提取复核",
    "profile_description": "Built-in fallback profile matching the historical ant triptych workflow.",
    "target_taxon": {
        "display_name": "蚂蚁",
        "scientific_scope": "Formicidae",
        "tested_status": "ant-tested",
    },
    "taxonomy_terms": [
        "formicidae",
        "ant",
        "ants",
        "worker",
        "queen",
        "male",
        "holotype",
        "paratype",
        "diagnosis",
        "description",
        "measurements",
        "material examined",
        "type material",
        "type locality",
        "distribution",
        "remarks",
        "biology",
        "sp. nov",
        "sp. n",
        "gen. nov",
    ],
    "rejection_terms": [
        "comparison",
        "compared",
        "versus",
        "vs.",
        "other species",
        "distribution map only",
        "phylogeny",
        "ecology",
        "behavior",
        "nest",
        "queen and male",
    ],
    "auxiliary_terms": ["map", "distribution", "inset", "scale", "scale bar", "plate", "locality"],
    "extraction_rules": {
        "caption_patterns": [
            r"^Figure\s+\d+[A-Za-z]?[:\.]\s+.+",
            r"^Fig\.\s*\d+[A-Za-z]?[:\.]\s+.+",
            r"^Plate\s+\d+[A-Za-z]?[:\.]\s+.+",
            r"^图\s*\d+[A-Za-z]?[:：\.]\s*.+",
        ],
        "figure_reference_patterns": [
            r"\bfig\.?\s*(\d+[A-Za-z]?)",
            r"\bfigure\s*(\d+[A-Za-z]?)",
            r"\bplate\s*(\d+[A-Za-z]?)",
            r"图\s*(\d+[A-Za-z]?)",
        ],
        "section_hint_map": {
            "diagnosis": "diagnosis",
            "description": "description",
            "measurements": "measurements",
            "material examined": "material_examined",
            "type material": "type_material",
            "distribution": "distribution",
            "remarks": "remarks",
            "biology": "biology",
            "etymology": "etymology",
            "taxonomic treatment": "taxonomic_treatment",
            "species accounts": "species_account",
            "species account": "species_account",
            "identification key": "identification_key",
            "key to species": "key_to_species",
            "synoptic list": "synoptic_list",
        },
        "core_section_hints": [
            "diagnosis",
            "description",
            "measurements",
            "material_examined",
            "type_material",
            "distribution",
            "remarks",
            "biology",
            "etymology",
            "species_account",
        ],
        "extended_section_hints": [
            "identification_key",
            "key_to_species",
            "taxonomic_treatment",
            "species_account",
            "synoptic_list",
        ],
        "evidence_text_limits": {
            "figure_local_chars": 1200,
            "species_core_chars": 2200,
            "species_extended_chars": 2200,
        },
        "species_name_patterns": [r"\b([A-Z][a-z]{2,})\s+([a-z][a-z\-]{2,})\b"],
        "blocked_genus_words": [
            "worker",
            "queen",
            "male",
            "the",
            "this",
            "that",
            "figure",
            "plate",
            "table",
            "body",
            "head",
            "holotype",
            "paratype",
            "material",
            "type",
            "diagnosis",
            "description",
            "measurements",
            "distribution",
            "remarks",
            "biology",
            "other",
        ],
        "blocked_species_words": [
            "and",
            "for",
            "with",
            "without",
            "view",
            "worker",
            "queen",
            "male",
            "species",
            "nov",
            "n",
            "the",
            "this",
            "that",
            "locality",
        ],
    },
    "review_rules": {
        "acceptance_goal": "只接受主体为单一物种蚂蚁分类学三视图的整张 figure。",
        "accept_if": [
            "主体是同一物种或同一分类单元",
            "包含 lateral、dorsal、head_frontal 主要视图",
            "caption 或附近文本能支持物种候选",
        ],
        "reject_if": [
            "多物种比较图",
            "仅分布图、系统树、生态照片或实验图",
            "主体不是目标分类群",
            "图像证据与文字证据明显冲突",
        ],
        "view_schema": {
            "required_or_expected_views": ["lateral", "dorsal", "head_frontal"],
            "acceptance_mode": "require_all_expected_parts",
            "view_terms": {
                "lateral": [
                    "lateral",
                    "profile",
                    "side view",
                    "in profile",
                    "body in profile",
                    "mesosoma in profile",
                ],
                "dorsal": ["dorsal", "in dorsal view", "from above", "body in dorsal view"],
                "head_frontal": ["full-face", "frontal", "head in full-face", "head frontal", "face view"],
            },
        },
        "category_values": [
            "ant_triptych",
            "comparison_or_multi_species",
            "non_triptych_or_other",
            "uncertain",
        ],
        "decision_thresholds": {"accept_threshold": 0.75},
        "prompt": {
            "system_prompt": (
                "你是严谨的蚂蚁分类学图像审稿助手。"
                "你将收到多个 PDF figure 候选，每个候选包含一张整图和分层文本证据。"
                "你的目标是只保留主体为单一物种蚂蚁三视图的整张 figure。"
                "允许整图中附带地图、比例尺、少量 inset，但若主体不是三视图、或是多物种/比较图，必须拒绝。"
                "请只输出 JSON，不要输出任何额外解释。"
            ),
            "user_instructions": (
                "请按顺序审查以下 figure 候选。你必须为每个 candidate_id 返回一条结果。"
                "accept 仅在主体是单一物种蚂蚁三视图整图时为 true；"
                "detected_views 仅使用 profile 中定义的视图字段；confidence_score 使用 0-1 浮点数。"
            ),
        },
        "mock_fallback": {
            "enabled": True,
            "accept_requires_text_hits": 2,
            "accept_requires_parts": ["lateral", "dorsal", "head_frontal"],
        },
    },
}


def default_figure_profile() -> Dict[str, Any]:
    return copy.deepcopy(DEFAULT_FIGURE_PROFILE)


def load_figure_profile(profile_path: str | os.PathLike[str] | None) -> Dict[str, Any]:
    if not profile_path:
        return default_figure_profile()
    path_text = os.fspath(profile_path)
    if not os.path.exists(path_text):
        raise ValueError(f"figure_profile_not_found:{path_text}")
    try:
        with open(path_text, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"figure_profile_json_invalid:{path_text}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"figure_profile_root_not_object:{path_text}")
    return normalize_figure_profile(payload)


def normalize_figure_profile(profile: Dict[str, Any] | None) -> Dict[str, Any]:
    if profile is None:
        return default_figure_profile()
    if not isinstance(profile, dict):
        raise ValueError("figure_profile_must_be_object")

    normalized = default_figure_profile()
    _deep_update(normalized, copy.deepcopy(profile))

    schema_version = str(normalized.get("schema_version", "") or "").strip()
    if schema_version and schema_version != PROFILE_SCHEMA_VERSION:
        raise ValueError(f"figure_profile_schema_unsupported:{schema_version}")
    normalized["schema_version"] = PROFILE_SCHEMA_VERSION
    normalized["profile_name"] = _required_text(normalized.get("profile_name"), "profile_name")

    target_taxon = normalized.get("target_taxon")
    if not isinstance(target_taxon, dict):
        raise ValueError("figure_profile_target_taxon_invalid")

    normalized["taxonomy_terms"] = _text_list(normalized.get("taxonomy_terms"), "taxonomy_terms")
    normalized["rejection_terms"] = _text_list(normalized.get("rejection_terms"), "rejection_terms")
    normalized["auxiliary_terms"] = _text_list(normalized.get("auxiliary_terms"), "auxiliary_terms")

    extraction_rules = normalized.get("extraction_rules")
    if not isinstance(extraction_rules, dict):
        raise ValueError("figure_profile_extraction_rules_invalid")
    extraction_rules["caption_patterns"] = _text_list(extraction_rules.get("caption_patterns"), "extraction_rules.caption_patterns")
    extraction_rules["figure_reference_patterns"] = _text_list(
        extraction_rules.get("figure_reference_patterns"),
        "extraction_rules.figure_reference_patterns",
    )
    section_hint_map = extraction_rules.get("section_hint_map")
    if not isinstance(section_hint_map, dict):
        raise ValueError("figure_profile_section_hint_map_invalid")
    extraction_rules["section_hint_map"] = {
        str(key).strip().lower(): str(value).strip()
        for key, value in section_hint_map.items()
        if str(key).strip() and str(value).strip()
    }
    extraction_rules["core_section_hints"] = _text_list(
        extraction_rules.get("core_section_hints"),
        "extraction_rules.core_section_hints",
    )
    extraction_rules["extended_section_hints"] = _text_list(
        extraction_rules.get("extended_section_hints"),
        "extraction_rules.extended_section_hints",
    )
    limits = extraction_rules.get("evidence_text_limits")
    if not isinstance(limits, dict):
        limits = {}
    extraction_rules["evidence_text_limits"] = {
        "figure_local_chars": _positive_int(limits.get("figure_local_chars"), 1200, minimum=200),
        "species_core_chars": _positive_int(limits.get("species_core_chars"), 2200, minimum=200),
        "species_extended_chars": _positive_int(limits.get("species_extended_chars"), 2200, minimum=200),
    }
    extraction_rules["species_name_patterns"] = _text_list(extraction_rules.get("species_name_patterns"), "extraction_rules.species_name_patterns")
    extraction_rules["blocked_genus_words"] = [
        item.lower() for item in _text_list(extraction_rules.get("blocked_genus_words"), "extraction_rules.blocked_genus_words")
    ]
    extraction_rules["blocked_species_words"] = [
        item.lower() for item in _text_list(extraction_rules.get("blocked_species_words"), "extraction_rules.blocked_species_words")
    ]

    review_rules = normalized.get("review_rules")
    if not isinstance(review_rules, dict):
        raise ValueError("figure_profile_review_rules_invalid")
    review_rules["acceptance_goal"] = _required_text(review_rules.get("acceptance_goal"), "review_rules.acceptance_goal")
    review_rules["accept_if"] = _text_list(review_rules.get("accept_if"), "review_rules.accept_if")
    review_rules["reject_if"] = _text_list(review_rules.get("reject_if"), "review_rules.reject_if")
    review_rules["category_values"] = _text_list(review_rules.get("category_values"), "review_rules.category_values")
    if "uncertain" not in {item.lower() for item in review_rules["category_values"]}:
        review_rules["category_values"].append("uncertain")

    view_schema = review_rules.get("view_schema")
    if not isinstance(view_schema, dict):
        raise ValueError("figure_profile_view_schema_invalid")
    view_schema["required_or_expected_views"] = _text_list(
        view_schema.get("required_or_expected_views"),
        "review_rules.view_schema.required_or_expected_views",
        allow_empty=True,
    )
    acceptance_mode = str(view_schema.get("acceptance_mode", "require_all_expected_parts") or "").strip()
    if acceptance_mode not in {"require_all_expected_parts", "model_accept_with_parts_recorded"}:
        acceptance_mode = "require_all_expected_parts"
    view_schema["acceptance_mode"] = acceptance_mode
    view_terms = view_schema.get("view_terms")
    if not isinstance(view_terms, dict):
        view_terms = {}
    view_schema["view_terms"] = {
        str(key).strip(): _text_list(value, f"review_rules.view_schema.view_terms.{key}", allow_empty=True)
        for key, value in view_terms.items()
        if str(key).strip()
    }

    prompt = review_rules.get("prompt")
    if not isinstance(prompt, dict):
        prompt = {}
    review_rules["prompt"] = {
        "system_prompt": _required_text(prompt.get("system_prompt"), "review_rules.prompt.system_prompt"),
        "user_instructions": _required_text(prompt.get("user_instructions"), "review_rules.prompt.user_instructions"),
    }

    thresholds = review_rules.get("decision_thresholds")
    if not isinstance(thresholds, dict):
        thresholds = {}
    review_rules["decision_thresholds"] = {
        "accept_threshold": _clamp_float(thresholds.get("accept_threshold"), 0.75, 0.0, 1.0),
    }

    mock_fallback = review_rules.get("mock_fallback")
    if not isinstance(mock_fallback, dict):
        mock_fallback = {}
    review_rules["mock_fallback"] = {
        "enabled": bool(mock_fallback.get("enabled", True)),
        "accept_requires_text_hits": _positive_int(mock_fallback.get("accept_requires_text_hits"), 2, minimum=0),
        "accept_requires_parts": _text_list(mock_fallback.get("accept_requires_parts"), "review_rules.mock_fallback.accept_requires_parts", allow_empty=True),
    }

    return normalized


def profile_display_name(profile: Dict[str, Any] | None) -> str:
    if not isinstance(profile, dict):
        return ""
    return str(profile.get("profile_name", "") or "").strip()


def _deep_update(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    for key, value in source.items():
        if key in {"section_hint_map", "view_terms"}:
            target[key] = value
            continue
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"figure_profile_field_required:{field_name}")
    return text


def _text_list(value: Any, field_name: str, allow_empty: bool = False) -> List[str]:
    if value is None:
        items: List[Any] = []
    elif isinstance(value, list):
        items = value
    elif isinstance(value, tuple) or isinstance(value, set):
        items = list(value)
    else:
        raise ValueError(f"figure_profile_field_must_be_list:{field_name}")
    normalized = [str(item).strip() for item in items if str(item).strip()]
    if not normalized and not allow_empty:
        raise ValueError(f"figure_profile_field_required:{field_name}")
    return normalized


def _positive_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


def _clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))
