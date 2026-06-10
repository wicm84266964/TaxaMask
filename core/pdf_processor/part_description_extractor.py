"""Pure-text taxon morphology part-description extraction for PDF evidence."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import requests

from .part_description_profile import (
    DEFAULT_PART_SCHEMA as PROFILE_DEFAULT_PART_SCHEMA,
    load_part_description_profile,
    normalize_part_description_profile,
    profile_display_name as part_profile_display_name,
)


@dataclass
class PartExtractionResult:
    status: str
    reason: str = ""
    model_used: str = ""
    used_protocol: str = ""
    raw_response: str = ""
    records: List[Dict[str, Any]] = field(default_factory=list)
    block_labels: List[Dict[str, Any]] = field(default_factory=list)
    truncated_input: bool = False
    profile_name: str = ""
    profile_schema_version: str = ""


class TextPartDescriptionExtractor:
    """Extract `taxon -> body part -> textual description` records from PDF text."""

    DEFAULT_TIMEOUT_SECONDS = 180
    DEFAULT_MAX_OUTPUT_TOKENS = 12000
    DEFAULT_MAX_INPUT_CHARS = 600000

    DEFAULT_PART_SCHEMA: List[Dict[str, Any]] = PROFILE_DEFAULT_PART_SCHEMA

    VALID_BLOCK_ROLES = {
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
    }

    def __init__(
        self,
        config: Dict[str, Any] | None = None,
        figure_profile: Dict[str, Any] | None = None,
        part_profile: Dict[str, Any] | None = None,
        part_profile_path: str | None = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self.figure_profile = figure_profile or {}
        self.part_profile = self._load_runtime_part_profile(part_profile, part_profile_path)
        self.part_profile_name = part_profile_display_name(self.part_profile) or "内置默认部位描述方案"
        self.part_profile_schema_version = str(self.part_profile.get("schema_version", "") or "")
        profile_settings = self.part_profile.get("extraction_settings", {})
        self.enabled = bool(self.config.get("enabled", True))
        self.default_provider = str(self.config.get("default_provider", "text_llm") or "text_llm").strip().lower()
        provider_config = self.config.get("providers", {}).get(self.default_provider, {})
        self.api_key = str(provider_config.get("api_key", self.config.get("api_key", "")) or "").strip()
        self.base_url = self._normalize_base_url(provider_config.get("base_url", self.config.get("base_url", "")))
        self.model = str(provider_config.get("model", self.config.get("model", "")) or "").strip()
        raw_protocol = str(self.config.get("api_protocol", provider_config.get("api_protocol", "auto")) or "auto").strip().lower()
        self.api_protocol = raw_protocol if raw_protocol in {"auto", "chat_completions", "responses"} else "auto"
        self.timeout_seconds = max(30, int(self.config.get("timeout", profile_settings.get("timeout", self.DEFAULT_TIMEOUT_SECONDS))))
        self.max_output_tokens = max(
            500,
            int(self.config.get("max_output_tokens", profile_settings.get("max_output_tokens", self.DEFAULT_MAX_OUTPUT_TOKENS))),
        )
        self.max_input_chars = max(
            5000,
            int(self.config.get("max_input_chars", profile_settings.get("max_input_chars", self.DEFAULT_MAX_INPUT_CHARS))),
        )
        self.max_retries = max(1, int(self.config.get("max_retries", profile_settings.get("max_retries", 2)) or 2))
        self.persist_unlabeled_blocks = bool(
            self.config.get("persist_unlabeled_blocks", profile_settings.get("persist_unlabeled_blocks", True))
        )
        self.part_schema = self._normalize_part_schema(
            self.config.get("part_schema") or self.part_profile.get("part_schema") or PROFILE_DEFAULT_PART_SCHEMA
        )
        self.block_role_values = self._normalize_block_role_values(self.part_profile.get("block_role_values"))
        self.valid_block_roles = set(self.block_role_values)
        prompt_config = self.part_profile.get("prompt", {})
        self.prompt_system_prompt = str(prompt_config.get("system_prompt", "你是严谨的分类学文本结构化助手。只输出 JSON。") or "").strip()
        self.prompt_user_instructions = str(prompt_config.get("user_instructions", "") or "").strip()
        mock_fallback = self.part_profile.get("mock_fallback", {})
        self.mock_measurement_terms = [str(item).lower() for item in mock_fallback.get("measurement_terms", [])]
        self.mock_reference_terms = [str(item).lower() for item in mock_fallback.get("reference_terms", [])]

    def _load_runtime_part_profile(
        self,
        part_profile: Dict[str, Any] | None,
        part_profile_path: str | None,
    ) -> Dict[str, Any]:
        if part_profile_path:
            return load_part_description_profile(part_profile_path)
        if part_profile is not None:
            return normalize_part_description_profile(part_profile)
        config_profile_path = str(
            self.config.get("part_description_profile_path", self.config.get("profile_path", "")) or ""
        ).strip()
        if config_profile_path:
            return load_part_description_profile(config_profile_path)
        config_profile = self.config.get("part_description_profile", self.config.get("profile"))
        if isinstance(config_profile, dict):
            return normalize_part_description_profile(config_profile)
        return normalize_part_description_profile(None)

    def _finalize_result(self, result: PartExtractionResult) -> PartExtractionResult:
        if not result.profile_name:
            result.profile_name = self.part_profile_name
        if not result.profile_schema_version:
            result.profile_schema_version = self.part_profile_schema_version
        return result

    def is_configured(self) -> bool:
        if not self.enabled:
            return False
        if self.default_provider == "mock":
            return True
        return bool(self.api_key and self.base_url and self.model)

    def extract(
        self,
        *,
        pdf_file_id: int,
        file_name: str,
        file_path: str,
        file_hash: str,
        document_blocks: List[Dict[str, Any]],
    ) -> PartExtractionResult:
        blocks, block_by_ref = self._prepare_blocks(
            pdf_file_id=pdf_file_id,
            file_name=file_name,
            file_path=file_path,
            file_hash=file_hash,
            document_blocks=document_blocks,
        )
        if not blocks:
            return self._finalize_result(PartExtractionResult(status="skipped", reason="no_text_blocks"))
        if not self.enabled:
            return self._finalize_result(
                PartExtractionResult(
                    status="skipped",
                    reason="disabled",
                    block_labels=self._unprocessed_block_labels(blocks, "disabled"),
                )
            )
        if self.default_provider == "mock":
            return self._extract_mock(blocks, block_by_ref)
        if not self.is_configured():
            return self._finalize_result(
                PartExtractionResult(
                    status="skipped",
                    reason="missing_text_llm_config",
                    block_labels=self._unprocessed_block_labels(blocks, "missing_text_llm_config"),
                )
            )

        prompt, truncated = self._build_prompt(file_name=file_name, file_hash=file_hash, blocks=blocks)
        last_error = ""
        for attempt in range(self.max_retries):
            try:
                raw_response, used_protocol = self._call_api(prompt)
                payload = self._parse_json_payload(raw_response)
                result = self._normalize_payload(
                    payload,
                    block_by_ref=block_by_ref,
                    model_used=self.model,
                    used_protocol=used_protocol,
                    raw_response=raw_response,
                    truncated_input=truncated,
                )
                if not result.records and not result.block_labels:
                    result.status = "empty"
                    result.reason = "no_structured_records"
                return self._finalize_result(result)
            except Exception as exc:
                last_error = str(exc)
                self.logger.warning(
                    "PDF part-description LLM extraction failed for %s (attempt %s/%s): %s",
                    file_name,
                    attempt + 1,
                    self.max_retries,
                    last_error,
                )
        return self._finalize_result(
            PartExtractionResult(status="failed", reason=last_error, model_used=self.model, truncated_input=truncated)
        )

    def _prepare_blocks(
        self,
        *,
        pdf_file_id: int,
        file_name: str,
        file_path: str,
        file_hash: str,
        document_blocks: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        blocks: List[Dict[str, Any]] = []
        block_by_ref: Dict[str, Dict[str, Any]] = {}
        for block in document_blocks:
            text = str(block.get("text_content", "") or "").strip()
            if not text:
                continue
            page_number = int(block.get("page_number", 0) or 0)
            block_index = int(block.get("block_index", 0) or 0)
            block_ref = self.make_block_ref(page_number, block_index)
            payload = {
                "pdf_file_id": int(pdf_file_id),
                "file_name": str(file_name or ""),
                "file_path": str(file_path or ""),
                "file_hash": str(file_hash or ""),
                "block_ref": block_ref,
                "page_number": page_number,
                "block_index": block_index,
                "section_hint": str(block.get("section_hint", "") or ""),
                "text_type": str(block.get("text_type", "") or ""),
                "species_mentions": list(block.get("species_mentions", []) or []),
                "text_content": text,
            }
            blocks.append(payload)
            block_by_ref[block_ref] = payload
        return blocks, block_by_ref

    @staticmethod
    def make_block_ref(page_number: int, block_index: int) -> str:
        return f"p{int(page_number):03d}_b{int(block_index):04d}"

    def _unprocessed_block_labels(self, blocks: List[Dict[str, Any]], model_used: str) -> List[Dict[str, Any]]:
        return [
            {
                **self._source_block_payload(block),
                "llm_role": "unprocessed",
                "llm_taxon_name": "",
                "llm_confidence": 0.0,
                "model_used": model_used,
            }
            for block in blocks
        ]

    def _build_prompt(self, *, file_name: str, file_hash: str, blocks: List[Dict[str, Any]]) -> Tuple[str, bool]:
        target_taxon = self.part_profile.get("target_taxon", {}) if isinstance(self.part_profile, dict) else {}
        if not isinstance(target_taxon, dict) or not (target_taxon.get("display_name") or target_taxon.get("scientific_scope")):
            target_taxon = self.figure_profile.get("target_taxon", {}) if isinstance(self.figure_profile, dict) else {}
        target_display = str(target_taxon.get("display_name", "") or "").strip()
        target_scope = str(target_taxon.get("scientific_scope", "") or "").strip()
        part_lines = "\n".join(
            f"- {item['key']} / {item['label']}: {', '.join(item.get('aliases', [])[:10])}"
            for item in self.part_schema
        )
        role_values = "|".join(role for role in self.block_role_values if role != "unprocessed")
        packed_blocks: List[Dict[str, Any]] = []
        current_chars = 0
        truncated = False
        for block in blocks:
            item = {
                "block_ref": block["block_ref"],
                "page_number": block["page_number"],
                "block_index": block["block_index"],
                "section_hint": block["section_hint"],
                "text_type": block["text_type"],
                "species_mentions": block["species_mentions"],
                "text": block["text_content"],
            }
            item_text = json.dumps(item, ensure_ascii=False)
            if current_chars + len(item_text) > self.max_input_chars and packed_blocks:
                truncated = True
                break
            packed_blocks.append(item)
            current_chars += len(item_text)

        blocks_json = json.dumps(packed_blocks, ensure_ascii=False, indent=2)
        prompt = f"""{self.prompt_system_prompt or "你是严谨的分类学文献结构化助手。请只根据输入的 PDF 原文文本块工作，不要根据图片或常识补充原文没有写出的形态信息。"}

目标类群：{target_display or "未指定"} {target_scope or ""}
部位描述方案：{self.part_profile_name}
PDF 文件名：{file_name}
PDF 文件哈希：{file_hash}

抽取规则：
{self.prompt_user_instructions}

可用部位桶：
{part_lines}

输出必须是一个 JSON object，结构如下：
{{
  "taxon_part_descriptions": [
    {{
      "taxon_name": "属名 种名或文中分类单元名",
      "caste_or_stage": "worker|queen|male|larva|gyne|unknown",
      "part_key": "上方部位桶 key",
      "part_label": "中文或原文部位名",
      "description_text": "文中对该部位的描述",
      "source_block_refs": ["p001_b0001"],
      "source_pages": [1],
      "confidence": 0.0
    }}
  ],
  "text_block_labels": [
    {{
      "block_ref": "p001_b0001",
      "role": "{role_values}",
      "taxon_name": "如果该块明确属于某个分类单元则填写，否则空字符串",
      "confidence": 0.0
    }}
  ]
}}

输入文本块：
{blocks_json}
"""
        return prompt, truncated

    def _call_api(self, prompt: str) -> Tuple[str, str]:
        protocol = self._resolve_api_protocol()
        protocols = [protocol]
        if self.api_protocol == "auto":
            protocols.append("responses" if protocol == "chat_completions" else "chat_completions")
        last_exc: Exception | None = None
        for current_protocol in protocols:
            try:
                if current_protocol == "responses":
                    return self._call_responses(prompt), current_protocol
                return self._call_chat_completions(prompt), current_protocol
            except Exception as exc:
                last_exc = exc
                detail = str(exc).lower()
                can_fallback = current_protocol != protocols[-1] and any(
                    token in detail for token in ["404", "400", "422", "unsupported", "not found", "responses", "chat/completions"]
                )
                if can_fallback:
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("part_description_llm_call_failed")

    def _call_responses(self, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url}/responses",
            headers=self._headers(),
            json={
                "model": self.model,
                "input": [
                    {
                        "role": "system",
                        "content": "你是严谨的分类学文本结构化助手。只输出 JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_output_tokens": self.max_output_tokens,
                "temperature": 0.0,
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} - responses_error - {response.text}")
        text = self._extract_responses_text(response.json())
        if not text:
            raise ValueError("empty_part_description_output")
        return text

    def _call_chat_completions(self, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是严谨的分类学文本结构化助手。只输出 JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": self.max_output_tokens,
                "temperature": 0.0,
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} - chat_completions_error - {response.text}")
        body = response.json()
        text = str(body.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        if not text:
            raise ValueError("empty_part_description_output")
        return text

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _resolve_api_protocol(self) -> str:
        if self.api_protocol in {"chat_completions", "responses"}:
            return self.api_protocol
        model_text = str(self.model or "").strip().lower()
        model_id = model_text.rsplit("/", 1)[-1]
        if model_id.startswith("gpt-5"):
            return "responses"
        return "chat_completions"

    def _normalize_base_url(self, raw_base_url: Any) -> str:
        base_text = str(raw_base_url or "").strip()
        if not base_text:
            return ""
        for suffix in ["/chat/completions", "/responses"]:
            if base_text.lower().endswith(suffix):
                base_text = base_text[: -len(suffix)]
        return base_text.rstrip("/")

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
                content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)
                if not isinstance(content, list):
                    continue
                for content_item in content:
                    if isinstance(content_item, dict):
                        text = str(content_item.get("text", "") or "")
                    else:
                        text = str(getattr(content_item, "text", "") or "")
                    if text:
                        chunks.append(text)
        return "\n".join(chunks).strip()

    def _parse_json_payload(self, raw_response: str) -> Dict[str, Any]:
        text = self._strip_code_fence(raw_response)
        payload = self._first_json_value(text)
        if not isinstance(payload, dict):
            raise ValueError("part_description_response_root_not_object")
        return payload

    def _first_json_value(self, text: str) -> Any:
        decoder = json.JSONDecoder()
        source = str(text or "").strip()
        try:
            return json.loads(source)
        except json.JSONDecodeError:
            pass
        for index, char in enumerate(source):
            if char not in "{[":
                continue
            try:
                value, _end = decoder.raw_decode(source[index:])
                return value
            except json.JSONDecodeError:
                repaired = self._repair_common_json_issues(source[index:])
                try:
                    value, _end = decoder.raw_decode(repaired)
                    return value
                except json.JSONDecodeError:
                    continue
        raise ValueError("part_description_json_not_found")

    def _repair_common_json_issues(self, text: str) -> str:
        repaired = str(text or "").strip()
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        repaired = re.sub(r"}\s*(?={)", "},", repaired)
        return repaired

    def _normalize_payload(
        self,
        payload: Dict[str, Any],
        *,
        block_by_ref: Dict[str, Dict[str, Any]],
        model_used: str,
        used_protocol: str,
        raw_response: str,
        truncated_input: bool,
    ) -> PartExtractionResult:
        records_payload = payload.get("taxon_part_descriptions")
        if records_payload is None:
            records_payload = payload.get("part_descriptions", [])
        if not isinstance(records_payload, list):
            records_payload = []

        labels_payload = payload.get("text_block_labels", [])
        if not isinstance(labels_payload, list):
            labels_payload = []

        records: List[Dict[str, Any]] = []
        for item in records_payload:
            if not isinstance(item, dict):
                continue
            description = self._clean_text(item.get("description_text", ""))
            if not description:
                continue
            refs = self._normalize_ref_list(item.get("source_block_refs"))
            refs = [ref for ref in refs if ref in block_by_ref]
            if not refs:
                continue
            source_blocks = [self._source_block_payload(block_by_ref[ref]) for ref in refs]
            pages = self._normalize_int_list(item.get("source_pages"))
            if not pages:
                pages = sorted({int(block_by_ref[ref].get("page_number", 0) or 0) for ref in refs})
            part_key = self._normalize_part_key(item.get("part_key", "other_diagnostic_structure"))
            part_label = self._clean_text(item.get("part_label", "")) or self._part_label_for_key(part_key)
            records.append(
                {
                    "taxon_name": self._clean_text(item.get("taxon_name", "")),
                    "caste_or_stage": self._normalize_caste(item.get("caste_or_stage", "")),
                    "part_key": part_key,
                    "part_label": part_label,
                    "description_text": description,
                    "source_block_refs": refs,
                    "source_pages": pages,
                    "source_blocks": source_blocks,
                    "confidence": self._clamp_confidence(item.get("confidence"), 0.5),
                    "review_status": "auto_extracted",
                    "model_used": model_used,
                }
            )

        block_labels = self._normalize_block_labels(labels_payload, block_by_ref, model_used)
        labeled_refs = {str(label.get("block_ref", "")) for label in block_labels}
        for record in records:
            for ref in record.get("source_block_refs", []):
                if ref in labeled_refs:
                    continue
                block = block_by_ref.get(ref)
                if not block:
                    continue
                block_labels.append(
                    {
                        **self._source_block_payload(block),
                        "llm_role": "morphological_description",
                        "llm_taxon_name": record.get("taxon_name", ""),
                        "llm_confidence": record.get("confidence", 0.5),
                        "model_used": model_used,
                    }
                )
                labeled_refs.add(ref)

        if self.persist_unlabeled_blocks:
            for ref, block in block_by_ref.items():
                if ref in labeled_refs:
                    continue
                block_labels.append(
                    {
                        **self._source_block_payload(block),
                        "llm_role": "other",
                        "llm_taxon_name": "",
                        "llm_confidence": 0.0,
                        "model_used": model_used,
                    }
                )

        return PartExtractionResult(
            status="real",
            model_used=model_used,
            used_protocol=used_protocol,
            raw_response=raw_response,
            records=records,
            block_labels=block_labels,
            truncated_input=truncated_input,
            profile_name=self.part_profile_name,
            profile_schema_version=self.part_profile_schema_version,
        )

    def _normalize_block_labels(
        self,
        labels_payload: List[Any],
        block_by_ref: Dict[str, Dict[str, Any]],
        model_used: str,
    ) -> List[Dict[str, Any]]:
        labels: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in labels_payload:
            if not isinstance(item, dict):
                continue
            ref = str(item.get("block_ref", "") or "").strip()
            if not ref or ref not in block_by_ref or ref in seen:
                continue
            role = str(item.get("role", "other") or "other").strip().lower()
            if role not in self.valid_block_roles:
                role = "other"
            block = block_by_ref[ref]
            labels.append(
                {
                    **self._source_block_payload(block),
                    "llm_role": role,
                    "llm_taxon_name": self._clean_text(item.get("taxon_name", "")),
                    "llm_confidence": self._clamp_confidence(item.get("confidence"), 0.5),
                    "model_used": model_used,
                }
            )
            seen.add(ref)
        return labels

    def _extract_mock(self, blocks: List[Dict[str, Any]], block_by_ref: Dict[str, Dict[str, Any]]) -> PartExtractionResult:
        records: List[Dict[str, Any]] = []
        labels: List[Dict[str, Any]] = []
        current_taxon = ""
        seen_records: set[Tuple[str, str, str, str]] = set()
        for block in blocks:
            text = block["text_content"]
            mentions = self._extract_species_mentions(text)
            if mentions:
                current_taxon = mentions[0]
            role = self._mock_role_for_block(block)
            labels.append(
                {
                    **self._source_block_payload(block),
                    "llm_role": role,
                    "llm_taxon_name": current_taxon,
                    "llm_confidence": 0.55 if role == "other" else 0.75,
                    "model_used": "mock_part_description_extractor",
                }
            )
            if role not in {"morphological_description", "diagnosis", "measurements"}:
                continue
            sentences = self._split_sentences(text)
            for sentence in sentences:
                part_key = self._part_key_for_text(sentence)
                if not part_key:
                    continue
                key = (current_taxon, part_key, block["block_ref"], sentence)
                if key in seen_records:
                    continue
                seen_records.add(key)
                records.append(
                    {
                        "taxon_name": current_taxon,
                        "caste_or_stage": self._infer_caste(sentence),
                        "part_key": part_key,
                        "part_label": self._part_label_for_key(part_key),
                        "description_text": sentence,
                        "source_block_refs": [block["block_ref"]],
                        "source_pages": [block["page_number"]],
                        "source_blocks": [self._source_block_payload(block)],
                        "confidence": 0.62,
                        "review_status": "auto_extracted",
                        "model_used": "mock_part_description_extractor",
                    }
                )
        return PartExtractionResult(
            status="mock",
            model_used="mock_part_description_extractor",
            used_protocol="mock",
            raw_response=json.dumps({"record_count": len(records), "label_count": len(labels)}, ensure_ascii=False),
            records=records,
            block_labels=labels,
            profile_name=self.part_profile_name,
            profile_schema_version=self.part_profile_schema_version,
        )

    def _mock_role_for_block(self, block: Dict[str, Any]) -> str:
        section_hint = str(block.get("section_hint", "") or "").lower()
        text = str(block.get("text_content", "") or "").lower()
        if str(block.get("text_type", "") or "").lower() == "caption":
            return "figure_caption"
        if section_hint in self.valid_block_roles:
            return section_hint
        if section_hint == "description" and "morphological_description" in self.valid_block_roles:
            return "morphological_description"
        if "measurements" in self.valid_block_roles and any(token in text for token in self.mock_measurement_terms):
            return "measurements"
        part_aliases = [str(alias).lower() for item in self.part_schema for alias in item.get("aliases", [])]
        if "morphological_description" in self.valid_block_roles and any(token and token in text for token in part_aliases):
            return "morphological_description"
        if "references" in self.valid_block_roles and any(token in text for token in self.mock_reference_terms):
            return "references"
        return "other"

    def _part_key_for_text(self, text: str) -> str:
        lowered = f" {text.lower()} "
        for item in self.part_schema:
            for alias in item.get("aliases", []):
                alias_text = str(alias or "").lower()
                if not alias_text:
                    continue
                if re.search(rf"(?<![A-Za-z]){re.escape(alias_text)}(?![A-Za-z])", lowered, flags=re.IGNORECASE):
                    return str(item.get("key", "other_diagnostic_structure"))
        return ""

    def _part_label_for_key(self, part_key: str) -> str:
        for item in self.part_schema:
            if item.get("key") == part_key:
                return str(item.get("label", part_key))
        return part_key or "其他诊断结构"

    def _normalize_part_key(self, value: Any) -> str:
        raw = str(value or "").strip()
        allowed = {str(item.get("key", "")) for item in self.part_schema}
        if raw in allowed:
            return raw
        lower_raw = raw.lower()
        for item in self.part_schema:
            if lower_raw == str(item.get("label", "")).lower():
                return str(item.get("key", "other_diagnostic_structure"))
            for alias in item.get("aliases", []):
                if lower_raw == str(alias).lower():
                    return str(item.get("key", "other_diagnostic_structure"))
        return "other_diagnostic_structure"

    def _normalize_part_schema(self, raw_schema: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_schema, list):
            raw_schema = PROFILE_DEFAULT_PART_SCHEMA
        normalized: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw_schema:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            aliases = [str(alias).strip() for alias in item.get("aliases", []) if str(alias).strip()]
            normalized.append({"key": key, "label": str(item.get("label", key) or key), "aliases": aliases})
        return normalized or list(PROFILE_DEFAULT_PART_SCHEMA)

    def _normalize_block_role_values(self, raw_values: Any) -> List[str]:
        if not isinstance(raw_values, list):
            raw_values = list(self.VALID_BLOCK_ROLES)
        normalized: List[str] = []
        seen: set[str] = set()
        for item in raw_values:
            role = str(item or "").strip().lower()
            if not role or role in seen:
                continue
            seen.add(role)
            normalized.append(role)
        if "other" not in seen:
            normalized.append("other")
        if "unprocessed" not in seen:
            normalized.append("unprocessed")
        return normalized

    def _source_block_payload(self, block: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "pdf_file_id": int(block.get("pdf_file_id", 0) or 0),
            "file_name": str(block.get("file_name", "") or ""),
            "file_path": str(block.get("file_path", "") or ""),
            "file_hash": str(block.get("file_hash", "") or ""),
            "block_ref": str(block.get("block_ref", "") or ""),
            "page_number": int(block.get("page_number", 0) or 0),
            "block_index": int(block.get("block_index", 0) or 0),
            "section_hint": str(block.get("section_hint", "") or ""),
            "text_type": str(block.get("text_type", "") or ""),
            "text_content": str(block.get("text_content", "") or ""),
        }

    def _extract_species_mentions(self, text: str) -> List[str]:
        mentions: List[str] = []
        seen: set[str] = set()
        for match in re.findall(r"\b([A-Z][a-z]{2,})\s+([a-z][a-z-]{2,})\b", text or ""):
            genus, species = match
            if genus.lower() in {"figure", "table", "plate", "diagnosis", "description"}:
                continue
            candidate = f"{genus} {species}"
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            mentions.append(candidate)
        return mentions[:5]

    def _split_sentences(self, text: str) -> List[str]:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        if not normalized:
            return []
        pieces = re.split(r"(?<=[.;。；])\s+", normalized)
        return [piece.strip() for piece in pieces if len(piece.strip()) >= 8]

    def _infer_caste(self, text: str) -> str:
        lowered = str(text or "").lower()
        for token in ["worker", "queen", "male", "gyne", "larva"]:
            if token in lowered:
                return token
        return "unknown"

    def _normalize_caste(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        return text if text in {"worker", "queen", "male", "larva", "gyne", "unknown"} else "unknown"

    def _normalize_ref_list(self, value: Any) -> List[str]:
        raw_items = value if isinstance(value, list) else [value]
        refs: List[str] = []
        for item in raw_items:
            text = str(item or "").strip()
            if text and text not in refs:
                refs.append(text)
        return refs

    def _normalize_int_list(self, value: Any) -> List[int]:
        raw_items = value if isinstance(value, list) else [value]
        numbers: List[int] = []
        for item in raw_items:
            try:
                number = int(item)
            except (TypeError, ValueError):
                continue
            if number not in numbers:
                numbers.append(number)
        return numbers

    def _clean_text(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _clamp_confidence(self, value: Any, default: float = 0.5) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = default
        if confidence < 0:
            return 0.0
        if confidence > 1:
            return 1.0
        return confidence

    def _strip_code_fence(self, content: str) -> str:
        text = str(content or "").strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            if text.endswith("```"):
                text = text[:-3].strip()
        return text
