"""
Figure 提取器 V2.0 的多模态批量复核模块。

核心目标：
1. 以“整张 figure 候选”为单位做批量多模态复核，而不是一张图一次请求。
2. 将 caption / local text / species-core / species-extended 一起送入模型，减少总调用次数。
3. 保留对旧接口的最低兼容，避免其他模块导入时立即崩溃。
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import requests

from .figure_profile import load_figure_profile, normalize_figure_profile, profile_display_name


@dataclass
class ValidationResult:
    """兼容旧版单图验证结果结构。"""

    is_taxonomic: bool
    confidence_score: float
    category: str
    reasoning: str
    model_used: str
    text_image_alignment_score: float = 0.0
    key_scientific_elements: List[str] = field(default_factory=list)
    text_accuracy_score: float = 0.0
    alignment_reasoning: str = ""


@dataclass
class TextImageMatchResult:
    """兼容旧版文本-图片匹配结构。"""

    text_block_id: int
    image_id: int
    match_score: float
    content_consistency: bool
    match_reasoning: str
    text_relevance_score: float
    image_relevance_score: float
    combined_relevance_score: float
    key_matching_elements: List[str] = field(default_factory=list)
    model_used: str = "rule_based"
    validation_timestamp: str = ""


@dataclass
class FigureReviewResult:
    candidate_id: str
    accept: bool
    confidence_score: float
    category: str
    reasoning: str
    species_candidate: str = ""
    species_confidence: float = 0.0
    detected_views: List[str] = field(default_factory=list)
    has_auxiliary_inset: bool = False
    comparison_figure: bool = False
    multiple_species: bool = False
    model_used: str = ""
    review_mode: str = "real"


class MultimodalValidator:
    """批量多模态大模型验证器。"""

    DEFAULT_BATCH_SIZE = 2
    DEFAULT_BATCH_FALLBACK_SIZE = 1
    DEFAULT_BATCH_CHAR_BUDGET = 24000
    DEFAULT_MAX_TOKENS = 4000
    DEFAULT_TIMEOUT_SECONDS = 180

    CORE_VIEW_TERMS = {
        "lateral": ["lateral", "profile", "side view", "in profile", "body in profile", "mesosoma in profile"],
        "dorsal": ["dorsal", "in dorsal view", "from above", "body in dorsal view"],
        "head_frontal": ["full-face", "frontal", "head in full-face", "head frontal", "face view"],
    }

    TAXONOMIC_TERMS = [
        "formicidae",
        "ant",
        "ants",
        "worker",
        "holotype",
        "paratype",
        "diagnosis",
        "description",
        "measurements",
        "type material",
        "material examined",
        "species",
        "sp. nov",
        "sp. n",
    ]

    REJECTION_TERMS = [
        "comparison",
        "compared",
        "versus",
        "vs.",
        "distribution map only",
        "phylogeny",
        "ecology",
        "behavior",
        "nest",
    ]

    AUXILIARY_TERMS = ["map", "distribution", "inset", "scale bar", "plate", "locality"]

    CORE_SECTION_TERMS = [
        "diagnosis",
        "description",
        "measurements",
        "type material",
        "material examined",
        "distribution",
        "remarks",
        "biology",
        "etymology",
    ]

    EXTENDED_SECTION_TERMS = [
        "key",
        "identification key",
        "species account",
        "taxonomic treatment",
        "synoptic list",
    ]

    def __init__(self, api_config: Dict[str, Any] | None = None):
        self.logger = logging.getLogger(__name__)
        self.api_config = api_config or {}
        self.figure_profile = self._load_runtime_figure_profile()
        self.figure_profile_name = profile_display_name(self.figure_profile) or "内置默认方案"
        self._apply_figure_profile(self.figure_profile)

        provider_config = self.api_config.get("providers", {}).get(
            self.api_config.get("default_provider", "silicon_flow"),
            {},
        )
        self.default_provider = str(self.api_config.get("default_provider", "silicon_flow") or "silicon_flow").strip().lower()
        self.base_url = self._normalize_base_url(provider_config.get("base_url", "https://api.siliconflow.cn/v1"))
        self.api_key = str(provider_config.get("api_key", "") or "").strip()
        self.model = self._normalize_provider_model(provider_config.get("model", "Qwen/Qwen3-VL-32B-Instruct") or "Qwen/Qwen3-VL-32B-Instruct")
        raw_protocol = str(self.api_config.get("api_protocol", provider_config.get("api_protocol", "auto")) or "auto").strip().lower()
        self.api_protocol = raw_protocol if raw_protocol in {"auto", "chat_completions", "responses"} else "auto"
        self.image_detail = str(self.api_config.get("image_detail", "auto") or "auto").strip().lower()
        if self.image_detail not in {"auto", "low", "high"}:
            self.image_detail = "auto"

        self.review_batch_size = min(
            self.DEFAULT_BATCH_SIZE,
            max(1, int(self.api_config.get("review_batch_size", self.DEFAULT_BATCH_SIZE))),
        )
        self.review_batch_fallback_size = min(
            self.DEFAULT_BATCH_FALLBACK_SIZE,
            max(
                1,
                int(self.api_config.get("review_batch_fallback_size", self.DEFAULT_BATCH_FALLBACK_SIZE)),
            ),
        )
        if self.review_batch_fallback_size > self.review_batch_size:
            self.review_batch_fallback_size = self.review_batch_size
        self.batch_char_budget = max(3000, int(self.api_config.get("batch_char_budget", self.DEFAULT_BATCH_CHAR_BUDGET)))
        self.batch_max_tokens = max(500, int(self.api_config.get("batch_max_tokens", self.DEFAULT_MAX_TOKENS)))
        self.timeout_seconds = max(30, int(self.api_config.get("timeout", self.DEFAULT_TIMEOUT_SECONDS)))
        self.last_raw_response = ""
        self.last_raw_protocol = ""
        self.logger.info(
            f"Figure review runtime | profile={self.figure_profile_name} | provider={self.default_provider} | model={self.model} | protocol={self._resolve_api_protocol()} | batch={self.review_batch_size}/{self.review_batch_fallback_size} | chars={self.batch_char_budget} | max_tokens={self.batch_max_tokens} | timeout={self.timeout_seconds}s"
        )

    def _load_runtime_figure_profile(self) -> Dict[str, Any]:
        profile_path = str(self.api_config.get("figure_profile_path", "") or "").strip()
        if profile_path:
            return load_figure_profile(profile_path)
        profile_payload = self.api_config.get("figure_profile")
        if isinstance(profile_payload, dict):
            return normalize_figure_profile(profile_payload)
        return normalize_figure_profile(None)

    def _apply_figure_profile(self, profile: Dict[str, Any]) -> None:
        review_rules = profile.get("review_rules", {})
        extraction_rules = profile.get("extraction_rules", {})
        view_schema = review_rules.get("view_schema", {})

        self.CORE_VIEW_TERMS = dict(view_schema.get("view_terms", {}))
        self.TAXONOMIC_TERMS = [str(item).lower() for item in profile.get("taxonomy_terms", [])]
        self.REJECTION_TERMS = [str(item).lower() for item in profile.get("rejection_terms", [])]
        self.AUXILIARY_TERMS = [str(item).lower() for item in profile.get("auxiliary_terms", [])]
        self.CORE_SECTION_TERMS = list(extraction_rules.get("core_section_hints", []))
        self.EXTENDED_SECTION_TERMS = list(extraction_rules.get("extended_section_hints", []))
        self.species_name_patterns = list(extraction_rules.get("species_name_patterns", []))
        self.blocked_genus_words = set(extraction_rules.get("blocked_genus_words", []))
        self.blocked_species_words = set(extraction_rules.get("blocked_species_words", []))
        self.required_figure_parts = set(str(item).strip() for item in view_schema.get("required_or_expected_views", []) if str(item).strip())
        self.figure_acceptance_mode = str(view_schema.get("acceptance_mode", "require_all_expected_parts") or "require_all_expected_parts")
        if self.figure_acceptance_mode not in {"require_all_expected_parts", "model_accept_with_parts_recorded"}:
            self.figure_acceptance_mode = "require_all_expected_parts"
        self.category_values = [str(item).strip() for item in review_rules.get("category_values", []) if str(item).strip()]
        if not self.category_values:
            self.category_values = ["target_taxon_figure", "comparison_or_multi_species", "non_target_or_other", "uncertain"]
        self.review_prompt = review_rules.get("prompt", {})
        self.accept_if = list(review_rules.get("accept_if", []))
        self.reject_if = list(review_rules.get("reject_if", []))
        self.acceptance_goal = str(review_rules.get("acceptance_goal", "") or "")
        self.mock_fallback = dict(review_rules.get("mock_fallback", {}))

    # ---------------------------------------------------------------------
    # Public V2.0 batch review API
    # ---------------------------------------------------------------------
    def review_triptych_batch(self, candidates: List[Dict[str, Any]]) -> Tuple[List[FigureReviewResult], str, str]:
        if not candidates:
            return [], "[]", "none"

        if self.default_provider == "mock" or not self.api_key or not self.base_url:
            return self.review_triptych_batch_mock(candidates)

        self.last_raw_response = ""
        self.last_raw_protocol = ""
        protocol_order = [self._resolve_api_protocol()]
        if self.api_protocol == "auto":
            fallback_protocol = "responses" if protocol_order[0] == "chat_completions" else "chat_completions"
            protocol_order.append(fallback_protocol)
        last_error: Exception | None = None
        for protocol in protocol_order:
            try:
                raw_response, finish_reason = self._call_triptych_batch_api(candidates, protocol)
                self.last_raw_response = raw_response
                self.last_raw_protocol = protocol
                if finish_reason in {"length", "max_output_tokens", "incomplete"}:
                    raise ValueError("triptych_batch_truncated_by_max_tokens")
                results = self._parse_triptych_results(raw_response, candidates, model_used=self.model)
                return results, raw_response, protocol
            except Exception as exc:
                last_error = exc
                self.logger.warning(f"批量多模态复核失败（协议={protocol}）: {exc}")

        if last_error is not None:
            raise last_error
        raise RuntimeError("triptych_batch_unknown_failure")

    def review_triptych_batch_mock(
        self,
        candidates: List[Dict[str, Any]],
        error_context: str = "",
    ) -> Tuple[List[FigureReviewResult], str, str]:
        results = [self._mock_review_candidate(candidate, error_context=error_context) for candidate in candidates]
        raw_response = json.dumps([self._result_to_payload(item) for item in results], ensure_ascii=False, indent=2)
        return results, raw_response, "mock"

    # ---------------------------------------------------------------------
    # Legacy compatibility wrappers
    # ---------------------------------------------------------------------
    def validate_image(self, image_path: str, context_text: str = "") -> ValidationResult:
        candidate = {
            "candidate_id": os.path.basename(image_path) or "candidate_0000",
            "image_path": image_path,
            "caption_text": "",
            "figure_local_text": context_text,
            "species_core_text": "",
            "species_extended_text": "",
        }
        result = self._mock_review_candidate(candidate)
        return ValidationResult(
            is_taxonomic=result.accept,
            confidence_score=result.confidence_score * 100.0,
            category=result.category,
            reasoning=result.reasoning,
            model_used=result.model_used,
            key_scientific_elements=result.detected_views,
        )

    def batch_validate(self, image_paths: List[str], context_texts: List[str] | None = None) -> List[ValidationResult]:
        context_texts = context_texts or [""] * len(image_paths)
        return [self.validate_image(path, context) for path, context in zip(image_paths, context_texts)]

    def validate_text_image_match(self, text_content: str, image_path: str, text_block_id: int, image_id: int) -> TextImageMatchResult:
        return self._rule_based_text_image_match(text_content, image_path, text_block_id, image_id)

    def batch_validate_text_image_matches(self, text_image_pairs: List[Dict[str, Any]]) -> List[TextImageMatchResult]:
        results: List[TextImageMatchResult] = []
        for pair in text_image_pairs:
            results.append(
                self._rule_based_text_image_match(
                    str(pair.get("text_content", "") or ""),
                    str(pair.get("image_path", "") or ""),
                    int(pair.get("text_block_id", 0) or 0),
                    int(pair.get("image_id", 0) or 0),
                )
            )
        return results

    # ---------------------------------------------------------------------
    # Prompt / API plumbing
    # ---------------------------------------------------------------------
    def _protocol_order(self) -> List[str]:
        if self.api_protocol == "responses":
            return ["responses", "chat_completions"]
        if self.api_protocol == "chat_completions":
            return ["chat_completions"]
        return ["chat_completions", "responses"]

    def _resolve_api_protocol(self) -> str:
        if self.api_protocol in {"chat_completions", "responses"}:
            return self.api_protocol
        model_text = str(self.model or "").strip().lower()
        base_text = str(self.base_url or "").strip().lower()
        if "gmn.chuangzuoli.com" in base_text and "gpt" in model_text:
            return "responses"
        return "chat_completions"

    def _normalize_base_url(self, raw_base_url: Any) -> str:
        base_text = str(raw_base_url or "").strip()
        if not base_text:
            return "https://api.siliconflow.cn/v1"
        base_text = base_text.rstrip("/")
        for suffix in ["/chat/completions", "/responses"]:
            if base_text.endswith(suffix):
                base_text = base_text[: -len(suffix)]
        return base_text.rstrip("/")

    def _normalize_provider_model(self, raw_model: Any) -> str:
        model_text = str(raw_model or "").strip()
        if not model_text:
            return ""
        base_text = str(self.base_url or "").lower()
        if "gmn.chuangzuoli.com" not in base_text:
            return model_text
        if "/" in model_text:
            prefix, suffix = model_text.split("/", 1)
            if prefix.lower() == "gmn" and suffix:
                return suffix.lower()
        return model_text.lower()

    def _encode_image_as_data_url(self, image_path: str) -> str:
        with open(image_path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("utf-8")
        ext = os.path.splitext(image_path)[1].lower()
        mime = "image/png"
        if ext in {".jpg", ".jpeg"}:
            mime = "image/jpeg"
        return f"data:{mime};base64,{encoded}"

    def _build_review_system_prompt(self) -> str:
        prompt = str(self.review_prompt.get("system_prompt", "") or "").strip()
        if prompt:
            return prompt
        return (
            "你是严谨的分类学图版审稿助手。"
            "你将收到多个 PDF figure 候选，每个候选包含一张整图和分层文本证据。"
            "你的目标是只保留符合当前 profile 的目标分类学图版。"
            "请只输出 JSON，不要输出任何额外解释。"
        )

    def _build_user_instructions(self) -> str:
        profile_instructions = str(self.review_prompt.get("user_instructions", "") or "").strip()
        allowed_parts = sorted(self._allowed_detected_parts())
        category_text = " / ".join(self.category_values)
        accept_if = "\n".join(f"- {item}" for item in self.accept_if)
        reject_if = "\n".join(f"- {item}" for item in self.reject_if)
        part_text = " / ".join(allowed_parts) if allowed_parts else "profile 中定义或模型能明确说明的结构字段"
        base = (
            "请按顺序审查以下 figure 候选。"
            "你必须为每个 candidate_id 返回一条结果。\n"
            "输出必须是一个 JSON object，且只能输出 JSON，不要添加解释、Markdown 或第二段 JSON。\n"
            "JSON object 的 results 字段必须是数组；数组中每个元素必须包含：\n"
            "candidate_id, accept, confidence_score, category, reasoning, species_candidate, species_confidence, detected_views, has_auxiliary_inset, comparison_figure, multiple_species\n"
            "其中：\n"
            f"- 当前目标：{self.acceptance_goal}\n"
            f"- accept_if:\n{accept_if}\n"
            f"- reject_if:\n{reject_if}\n"
            f"- detected_views 仅使用这些视图或结构字段：{part_text}；\n"
            "- confidence_score 使用 0-1 浮点数；\n"
            f"- category 推荐值：{category_text}。"
        )
        if profile_instructions:
            return f"{profile_instructions}\n\n{base}"
        return base

    def _candidate_prompt_block(self, candidate: Dict[str, Any]) -> str:
        payload = {
            "candidate_id": str(candidate.get("candidate_id", "")),
            "page_number": int(candidate.get("page_number", 0) or 0),
            "raw_rect_count": int(candidate.get("raw_rect_count", 0) or 0),
            "caption_text": str(candidate.get("caption_text", "") or ""),
            "figure_local_text": str(candidate.get("figure_local_text", "") or ""),
            "species_core_text": str(candidate.get("species_core_text", "") or ""),
            "species_extended_text": str(candidate.get("species_extended_text", "") or ""),
        }
        return (
            f"候选 {payload['candidate_id']} 的文字证据如下。"
            "请结合紧随其后的图片完成判断。\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _build_chat_messages(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        user_content: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": self._build_user_instructions(),
            }
        ]
        for candidate in candidates:
            user_content.append({"type": "text", "text": self._candidate_prompt_block(candidate)})
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._encode_image_as_data_url(str(candidate.get("image_path", ""))),
                        "detail": self.image_detail,
                    },
                }
            )
        return [
            {"role": "system", "content": self._build_review_system_prompt()},
            {"role": "user", "content": user_content},
        ]

    def _build_triptych_json_schema(self) -> Dict[str, Any]:
        detected_view_items: Dict[str, Any] = {"type": "string"}
        allowed_parts = sorted(self._allowed_detected_parts())
        if allowed_parts:
            detected_view_items["enum"] = allowed_parts
        return {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "candidate_id": {"type": "string"},
                            "accept": {"type": "boolean"},
                            "confidence_score": {"type": "number"},
                            "category": {"type": "string"},
                            "reasoning": {"type": "string"},
                            "species_candidate": {"type": "string"},
                            "species_confidence": {"type": "number"},
                            "detected_views": {
                                "type": "array",
                                "items": detected_view_items,
                            },
                            "has_auxiliary_inset": {"type": "boolean"},
                            "comparison_figure": {"type": "boolean"},
                            "multiple_species": {"type": "boolean"},
                        },
                        "required": [
                            "candidate_id",
                            "accept",
                            "confidence_score",
                            "category",
                            "reasoning",
                            "species_candidate",
                            "species_confidence",
                            "detected_views",
                            "has_auxiliary_inset",
                            "comparison_figure",
                            "multiple_species",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["results"],
            "additionalProperties": False,
        }

    def _allowed_detected_parts(self) -> set[str]:
        allowed = set(str(item).strip() for item in self.required_figure_parts if str(item).strip())
        allowed.update(str(key).strip() for key in self.CORE_VIEW_TERMS.keys() if str(key).strip())
        return allowed

    def _build_responses_payload(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        content: List[Dict[str, Any]] = [
            {
                "type": "input_text",
                "text": self._build_user_instructions(),
            }
        ]
        for candidate in candidates:
            content.append({"type": "input_text", "text": self._candidate_prompt_block(candidate)})
            content.append(
                {
                    "type": "input_image",
                    "image_url": self._encode_image_as_data_url(str(candidate.get("image_path", ""))),
                }
            )
        return {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": self._build_review_system_prompt()}]},
                {"role": "user", "content": content},
            ],
            "max_output_tokens": self.batch_max_tokens,
            "temperature": 0.0,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "figure_review_results",
                    "strict": True,
                    "schema": self._build_triptych_json_schema(),
                }
            },
        }

    def _call_triptych_batch_api(self, candidates: List[Dict[str, Any]], protocol: str) -> Tuple[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if protocol == "responses":
            payload = self._build_responses_payload(candidates)
            response = requests.post(
                f"{self.base_url}/responses",
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code} - responses_http_error - {response.text}")
            body = response.json()
            return self._extract_responses_text(body), self._extract_responses_finish_reason(body)

        payload = {
            "model": self.model,
            "messages": self._build_chat_messages(candidates),
            "max_tokens": self.batch_max_tokens,
            "temperature": 0.0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "figure_review_results",
                    "strict": True,
                    "schema": self._build_triptych_json_schema(),
                },
            },
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} - chat_completions_error - {response.text}")
        body = response.json()
        raw_text = str(body.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        finish_reason = str(body.get("choices", [{}])[0].get("finish_reason", "") or "").strip().lower()
        if not raw_text:
            raise ValueError("empty_multimodal_output")
        return raw_text, finish_reason

    def _extract_responses_text(self, payload: Any) -> str:
        if isinstance(payload, dict):
            output_text = str(payload.get("output_text", "") or "").strip()
            if output_text:
                return output_text
            output_items = payload.get("output")
        else:
            output_text = str(getattr(payload, "output_text", "") or "").strip()
            if output_text:
                return output_text
            output_items = getattr(payload, "output", None)

        chunks: List[str] = []
        if isinstance(output_items, list):
            for item in output_items:
                content_items = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)
                if not isinstance(content_items, list):
                    continue
                for content_item in content_items:
                    item_type = content_item.get("type") if isinstance(content_item, dict) else getattr(content_item, "type", "")
                    text = content_item.get("text") if isinstance(content_item, dict) else getattr(content_item, "text", "")
                    if item_type == "output_text" and text:
                        chunks.append(str(text))
        return "\n".join(chunks).strip()

    def _extract_responses_finish_reason(self, payload: Any) -> str:
        if isinstance(payload, dict):
            status = str(payload.get("status", "") or "").strip().lower()
            incomplete_details = payload.get("incomplete_details")
        else:
            status = str(getattr(payload, "status", "") or "").strip().lower()
            incomplete_details = getattr(payload, "incomplete_details", None)
        if status == "completed":
            return "stop"
        if isinstance(incomplete_details, dict):
            reason = str(incomplete_details.get("reason", "") or "").strip().lower()
        else:
            reason = str(getattr(incomplete_details, "reason", "") or "").strip().lower()
        if reason in {"max_output_tokens", "length"}:
            return "length"
        return status or reason

    # ---------------------------------------------------------------------
    # Parsing and mock heuristics
    # ---------------------------------------------------------------------
    def _parse_triptych_results(
        self,
        raw_response: str,
        candidates: List[Dict[str, Any]],
        model_used: str,
    ) -> List[FigureReviewResult]:
        expected_ids = [str(candidate.get("candidate_id", "") or "") for candidate in candidates]
        parsed = self._select_triptych_payload(raw_response, expected_ids)
        if parsed is None:
            raise ValueError("triptych_batch_json_not_found")

        parsed_map: Dict[str, Dict[str, Any]] = {}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            candidate_id = str(item.get("candidate_id", "") or "").strip()
            if candidate_id:
                parsed_map[candidate_id] = item

        missing_ids = [candidate_id for candidate_id in expected_ids if candidate_id not in parsed_map]
        if missing_ids:
            raise ValueError(f"triptych_batch_missing_candidates:{','.join(missing_ids)}")

        results: List[FigureReviewResult] = []
        for candidate in candidates:
            candidate_id = str(candidate.get("candidate_id", "") or "")
            item = parsed_map[candidate_id]
            views = item.get("detected_views", [])
            if not isinstance(views, list):
                views = []
            allowed_parts = self._allowed_detected_parts()
            normalized_views = []
            for view in views:
                view_text = str(view).strip()
                if not view_text:
                    continue
                if allowed_parts and view_text not in allowed_parts:
                    continue
                normalized_views.append(view_text)
            results.append(
                FigureReviewResult(
                    candidate_id=candidate_id,
                    accept=bool(item.get("accept", False)),
                    confidence_score=self._clamp_confidence(item.get("confidence_score"), 0.0),
                    category=str(item.get("category", "uncertain") or "uncertain"),
                    reasoning=str(item.get("reasoning", "") or ""),
                    species_candidate=str(item.get("species_candidate", "") or ""),
                    species_confidence=self._clamp_confidence(item.get("species_confidence"), 0.0),
                    detected_views=normalized_views,
                    has_auxiliary_inset=bool(item.get("has_auxiliary_inset", False)),
                    comparison_figure=bool(item.get("comparison_figure", False)),
                    multiple_species=bool(item.get("multiple_species", False)),
                    model_used=model_used,
                    review_mode="real",
                )
            )
        return results

    def _select_triptych_payload(self, raw_response: str, expected_ids: List[str]) -> List[Dict[str, Any]] | None:
        last_error = ""
        for payload in self._iter_json_values(raw_response):
            try:
                records = self._coerce_triptych_payload(payload, expected_ids)
            except ValueError as exc:
                last_error = str(exc)
                continue
            if records is not None:
                return records
        if last_error:
            raise ValueError(last_error)
        return None

    def _coerce_triptych_payload(self, payload: Any, expected_ids: List[str]) -> List[Dict[str, Any]] | None:
        records: Any = payload
        if isinstance(payload, dict):
            if isinstance(payload.get("results"), list):
                records = payload.get("results")
            elif isinstance(payload.get("results"), dict):
                records = [payload.get("results")]
            elif "candidate_id" in payload:
                records = [payload]
            else:
                mapped_records = []
                for candidate_id in expected_ids:
                    value = payload.get(candidate_id)
                    if isinstance(value, dict):
                        item = dict(value)
                        item.setdefault("candidate_id", candidate_id)
                        mapped_records.append(item)
                if mapped_records:
                    records = mapped_records
        if not isinstance(records, list):
            raise ValueError("triptych_batch_result_not_array")

        dict_records = [dict(item) for item in records if isinstance(item, dict)]
        if len(expected_ids) == 1 and len(dict_records) == 1 and not str(dict_records[0].get("candidate_id", "") or "").strip():
            dict_records[0]["candidate_id"] = expected_ids[0]
        if not dict_records:
            raise ValueError("triptych_batch_result_not_array")

        seen_ids = {str(item.get("candidate_id", "") or "").strip() for item in dict_records}
        missing_ids = [candidate_id for candidate_id in expected_ids if candidate_id and candidate_id not in seen_ids]
        if missing_ids:
            raise ValueError(f"triptych_batch_missing_candidates:{','.join(missing_ids)}")
        return dict_records

    def _iter_json_values(self, raw_response: str) -> List[Any]:
        text = self._strip_code_fence(str(raw_response or ""))
        decoder = json.JSONDecoder()
        values: List[Any] = []
        index = 0
        while index < len(text):
            char = text[index]
            if char not in "[{":
                index += 1
                continue
            try:
                value, end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                repaired = self._repair_common_json_issues(text[index:])
                try:
                    value, end = decoder.raw_decode(repaired)
                except json.JSONDecodeError:
                    index += 1
                    continue
            values.append(value)
            index += max(end, 1)
        return values

    def _strip_code_fence(self, content: str) -> str:
        text = str(content or "").strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip()
        return text

    def _repair_common_json_issues(self, text: str) -> str:
        repaired = str(text or "").strip()
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        repaired = re.sub(r"}\s*(?={)", "},", repaired)
        return repaired

    def _mock_review_candidate(self, candidate: Dict[str, Any], error_context: str = "") -> FigureReviewResult:
        candidate_id = str(candidate.get("candidate_id", "") or "candidate")
        local_blob = " ".join(
            [
                str(candidate.get("caption_text", "") or ""),
                str(candidate.get("figure_local_text", "") or ""),
                str(candidate.get("species_core_text", "") or ""),
            ]
        ).strip()
        extended_blob = str(candidate.get("species_extended_text", "") or "")
        evidence_blob = " ".join(
            [
                local_blob,
                str(candidate.get("species_extended_text", "") or ""),
            ]
        ).strip()
        evidence_lower = evidence_blob.lower()

        local_species_mentions = self._extract_species_mentions(local_blob)
        extended_species_mentions = self._extract_species_mentions(extended_blob)
        species_mentions = local_species_mentions or extended_species_mentions
        multiple_species = len(local_species_mentions) > 1
        comparison_figure = multiple_species or any(token in local_blob.lower() for token in self.REJECTION_TERMS)
        if not comparison_figure and not local_species_mentions and len(extended_species_mentions) > 1:
            comparison_figure = True
            multiple_species = True

        detected_views: List[str] = []
        for view_name, markers in self.CORE_VIEW_TERMS.items():
            if any(marker in evidence_lower for marker in markers):
                detected_views.append(view_name)

        taxonomy_hits = sum(1 for token in self.TAXONOMIC_TERMS if token in evidence_lower)
        mock_required_parts = {
            str(item).strip()
            for item in self.mock_fallback.get("accept_requires_parts", [])
            if str(item).strip()
        }
        if not mock_required_parts and self.figure_acceptance_mode == "require_all_expected_parts":
            mock_required_parts = set(self.required_figure_parts)
        has_required_parts = True
        if mock_required_parts:
            has_required_parts = mock_required_parts.issubset(set(detected_views))
        elif self.figure_acceptance_mode == "model_accept_with_parts_recorded":
            has_required_parts = bool(detected_views) or taxonomy_hits > 0
        has_auxiliary = any(token in evidence_lower for token in self.AUXILIARY_TERMS) or bool(candidate.get("has_auxiliary_inset"))

        required_text_hits = int(self.mock_fallback.get("accept_requires_text_hits", 2) or 0)
        accept = has_required_parts and taxonomy_hits >= required_text_hits and not comparison_figure
        confidence = 0.85 if accept else 0.15
        if has_required_parts and taxonomy_hits >= max(1, required_text_hits - 1) and not comparison_figure:
            confidence = 0.82
        if comparison_figure:
            confidence = 0.12

        category = self._category_for_mock(accept, comparison_figure)
        reasoning = "基于本地模拟批量复核结果"
        if error_context:
            reasoning += f"（真实多模态调用失败后降级：{error_context}）"

        species_candidate = species_mentions[0] if species_mentions else ""
        species_confidence = 0.75 if species_candidate and not multiple_species else (0.35 if species_candidate else 0.0)

        return FigureReviewResult(
            candidate_id=candidate_id,
            accept=accept,
            confidence_score=confidence,
            category=category,
            reasoning=reasoning,
            species_candidate=species_candidate,
            species_confidence=species_confidence,
            detected_views=detected_views,
            has_auxiliary_inset=has_auxiliary,
            comparison_figure=comparison_figure,
            multiple_species=multiple_species,
            model_used="mock_batch_review",
            review_mode="mock",
        )

    def _category_for_mock(self, accept: bool, comparison_figure: bool) -> str:
        if accept:
            return self.category_values[0] if self.category_values else "target_taxon_figure"
        if comparison_figure:
            for category in self.category_values:
                if "comparison" in category or "multi" in category:
                    return category
            return "comparison_or_multi_species"
        for category in self.category_values:
            if "non" in category or "other" in category:
                return category
        return self.category_values[-1] if self.category_values else "uncertain"

    def _result_to_payload(self, result: FigureReviewResult) -> Dict[str, Any]:
        return {
            "candidate_id": result.candidate_id,
            "accept": result.accept,
            "confidence_score": round(result.confidence_score, 4),
            "category": result.category,
            "reasoning": result.reasoning,
            "species_candidate": result.species_candidate,
            "species_confidence": round(result.species_confidence, 4),
            "detected_views": result.detected_views,
            "has_auxiliary_inset": result.has_auxiliary_inset,
            "comparison_figure": result.comparison_figure,
            "multiple_species": result.multiple_species,
        }

    def _extract_species_mentions(self, text: str) -> List[str]:
        mentions: List[str] = []
        seen: set[str] = set()
        for pattern_text in self.species_name_patterns:
            try:
                pattern = re.compile(pattern_text)
            except re.error:
                self.logger.warning(f"Invalid species_name_pattern ignored: {pattern_text}")
                continue
            for match in pattern.findall(text or ""):
                if isinstance(match, tuple) and len(match) >= 2:
                    genus, species = str(match[0]), str(match[1])
                else:
                    parts = str(match).split()
                    if len(parts) < 2:
                        continue
                    genus, species = parts[0], parts[1]
                if genus.lower() in self.blocked_genus_words or species.lower() in self.blocked_species_words:
                    continue
                candidate = f"{genus} {species}"
                lowered = candidate.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                mentions.append(candidate)
        return mentions[:6]

    def _clamp_confidence(self, value: Any, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = default
        return max(0.0, min(1.0, numeric))

    # ---------------------------------------------------------------------
    # Legacy rule-based text-image compatibility
    # ---------------------------------------------------------------------
    def _rule_based_text_image_match(self, text_content: str, image_path: str, text_block_id: int, image_id: int) -> TextImageMatchResult:
        text_lower = str(text_content or "").lower()
        keyword_hits = sum(1 for term in (self.TAXONOMIC_TERMS + self.CORE_SECTION_TERMS) if term in text_lower)
        view_hits = sum(1 for markers in self.CORE_VIEW_TERMS.values() for marker in markers if marker in text_lower)
        match_score = min(100.0, float(keyword_hits * 12 + view_hits * 20))
        combined_relevance = min(100.0, float(keyword_hits * 15 + view_hits * 18))
        return TextImageMatchResult(
            text_block_id=text_block_id,
            image_id=image_id,
            match_score=match_score,
            content_consistency=match_score >= 50.0,
            match_reasoning="rule-based text/image relevance fallback",
            text_relevance_score=min(100.0, float(keyword_hits * 15)),
            image_relevance_score=min(100.0, float(view_hits * 20 + 20 if os.path.exists(image_path) else 0.0)),
            combined_relevance_score=combined_relevance,
            key_matching_elements=[term for term in self.CORE_SECTION_TERMS if term in text_lower][:6],
            model_used="rule_based",
        )


def create_validator_with_config(config_file: str | None = None) -> MultimodalValidator:
    if not config_file or not os.path.exists(config_file):
        return MultimodalValidator()
    try:
        with open(config_file, "r", encoding="utf-8") as handle:
            api_config = json.load(handle)
    except Exception:
        api_config = {}
    return MultimodalValidator(api_config)
