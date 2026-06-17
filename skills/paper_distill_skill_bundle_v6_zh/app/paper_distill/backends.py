from __future__ import annotations

import json
import re
import time
from urllib.parse import urlsplit
from dataclasses import dataclass
from typing import cast, final

import httpx

from app.paper_distill.cache import CacheMetadataStore
from app.paper_distill.models import (
    CacheRecord,
    CacheStatus,
    GeneratedQaCandidate,
    PreparedPrefix,
)


class DistillationBackend:
    kind: str = ""

    def prepare_prefix(
        self,
        *,
        cache_key: str,
        backend_identity: str,
        prefix_hash: str,
        paper_id: str,
        source_hash: str,
        prompt_version: str,
    ) -> PreparedPrefix:
        raise NotImplementedError

    def generate_batch(
        self,
        *,
        prefix_text: str,
        suffix_text: str,
        prepared_prefix: PreparedPrefix,
        next_ordinal: int,
        batch_size: int,
    ) -> tuple[GeneratedQaCandidate, ...]:
        raise NotImplementedError

    def generate_json_object(
        self,
        *,
        prefix_text: str,
        suffix_text: str,
        prepared_prefix: PreparedPrefix,
    ) -> dict[str, object]:
        raise NotImplementedError


@final
class MockDistillationBackend(DistillationBackend):
    kind: str = "mock"

    def __init__(self, cache_store: CacheMetadataStore, *, model_name: str) -> None:
        self.cache_store = cache_store
        self.model_name = model_name

    def prepare_prefix(
        self,
        *,
        cache_key: str,
        backend_identity: str,
        prefix_hash: str,
        paper_id: str,
        source_hash: str,
        prompt_version: str,
    ) -> PreparedPrefix:
        existing = self.cache_store.load(cache_key)
        if existing is not None and existing.prefix_hash == prefix_hash:
            self.cache_store.save(existing.touch())
            return PreparedPrefix(
                cache_key=cache_key,
                prefix_hash=prefix_hash,
                backend_kind=self.kind,
                backend_ref=existing.backend_ref,
                cache_status=CacheStatus.REUSED,
            )

        backend_ref = f"mock:{cache_key[:16]}"
        self.cache_store.save(
            CacheRecord(
                cache_key=cache_key,
                backend_identity=backend_identity,
                prefix_hash=prefix_hash,
                backend_kind=self.kind,
                backend_ref=backend_ref,
                paper_id=paper_id,
                source_hash=source_hash,
                prompt_version=prompt_version,
                model_name=self.model_name,
            )
        )
        return PreparedPrefix(
            cache_key=cache_key,
            prefix_hash=prefix_hash,
            backend_kind=self.kind,
            backend_ref=backend_ref,
            cache_status=CacheStatus.CREATED,
        )

    def generate_batch(
        self,
        *,
        prefix_text: str,
        suffix_text: str,
        prepared_prefix: PreparedPrefix,
        next_ordinal: int,
        batch_size: int,
    ) -> tuple[GeneratedQaCandidate, ...]:
        topics = _extract_topics(_extract_source_markdown(prefix_text))
        candidates: list[GeneratedQaCandidate] = []
        for offset in range(batch_size):
            ordinal = next_ordinal + offset
            topic = topics[(ordinal - 1) % len(topics)]
            candidates.append(
                GeneratedQaCandidate(
                    question=(
                        f"What core point #{ordinal} does the paper make about {topic.label}?"
                    ),
                    answer=(
                        f"The paper explains that {topic.summary}."
                    ),
                    evidence_text=topic.evidence_text,
                    evidence_locator=topic.evidence_locator,
                )
            )
        return tuple(candidates)

    def generate_json_object(
        self,
        *,
        prefix_text: str,
        suffix_text: str,
        prepared_prefix: PreparedPrefix,
    ) -> dict[str, object]:
        _ = prepared_prefix
        task = _extract_suffix_task(suffix_text)
        if task == "build_conversation_plan":
            return _build_mock_conversation_plan_payload(prefix_text, suffix_text)
        if task == "generate_conversation_turns":
            return _build_mock_conversation_turn_payload(prefix_text, suffix_text)
        return _build_mock_knowledge_map_payload(prefix_text)


@final
class OpenAICompatibleBackend(DistillationBackend):
    kind: str = "openai-compatible"
    _retry_statuses = frozenset({502, 503, 504})

    def __init__(
        self,
        cache_store: CacheMetadataStore,
        *,
        model_name: str,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        temperature: float,
    ) -> None:
        validated_base_url = _validate_openai_compatible_base_url(base_url)
        if not api_key.strip():
            raise ValueError("OpenAI-compatible backend requires a non-empty API key.")
        self.cache_store = cache_store
        self.model_name = model_name
        self.base_url = validated_base_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    def prepare_prefix(
        self,
        *,
        cache_key: str,
        backend_identity: str,
        prefix_hash: str,
        paper_id: str,
        source_hash: str,
        prompt_version: str,
    ) -> PreparedPrefix:
        existing = self.cache_store.load(cache_key)
        if existing is not None and existing.prefix_hash == prefix_hash:
            self.cache_store.save(existing.touch())
            return PreparedPrefix(
                cache_key=cache_key,
                prefix_hash=prefix_hash,
                backend_kind=self.kind,
                backend_ref=existing.backend_ref,
                cache_status=CacheStatus.REUSED,
            )

        backend_ref = f"openai-compatible:{cache_key[:16]}"
        self.cache_store.save(
            CacheRecord(
                cache_key=cache_key,
                backend_identity=backend_identity,
                prefix_hash=prefix_hash,
                backend_kind=self.kind,
                backend_ref=backend_ref,
                paper_id=paper_id,
                source_hash=source_hash,
                prompt_version=prompt_version,
                model_name=self.model_name,
            )
        )
        return PreparedPrefix(
            cache_key=cache_key,
            prefix_hash=prefix_hash,
            backend_kind=self.kind,
            backend_ref=backend_ref,
            cache_status=CacheStatus.CREATED,
        )

    def generate_batch(
        self,
        *,
        prefix_text: str,
        suffix_text: str,
        prepared_prefix: PreparedPrefix,
        next_ordinal: int,
        batch_size: int,
    ) -> tuple[GeneratedQaCandidate, ...]:
        decoded = self._request_json_payload(prefix_text=prefix_text, suffix_text=suffix_text)
        items = _decode_candidate_items(decoded)
        return tuple(items)

    def generate_json_object(
        self,
        *,
        prefix_text: str,
        suffix_text: str,
        prepared_prefix: PreparedPrefix,
    ) -> dict[str, object]:
        _ = prepared_prefix
        decoded = self._request_json_payload(prefix_text=prefix_text, suffix_text=suffix_text)
        return _decode_json_object(decoded)

    def _request_json_payload(self, *, prefix_text: str, suffix_text: str) -> str:
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a paper distillation engine. Return only valid JSON."
                    ),
                },
                {"role": "user", "content": prefix_text},
                {"role": "user", "content": suffix_text},
            ],
            "temperature": self.temperature,
        }
        response: httpx.Response | None = None
        last_json_error: json.JSONDecodeError | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                _ = response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code not in self._retry_statuses or attempt >= 2:
                    raise
                time.sleep(1.0 + attempt)
                continue
            except httpx.HTTPError:
                if attempt >= 2:
                    raise
                time.sleep(1.0 + attempt)
                continue

            if response is None:
                raise RuntimeError("OpenAI-compatible backend did not receive a response.")
            decoded = cast(object, response.json())
            if not isinstance(decoded, dict):
                raise ValueError("OpenAI-compatible response must decode to a dictionary.")
            choices = decoded.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError("OpenAI-compatible response did not contain any choices.")
            first_choice = choices[0]
            if not isinstance(first_choice, dict):
                raise ValueError("First choice must decode to a dictionary.")
            message = first_choice.get("message")
            if not isinstance(message, dict):
                raise ValueError("OpenAI-compatible choice is missing a message dictionary.")
            content = _message_content_to_text(message.get("content"))
            try:
                return _coerce_json_payload_text(content)
            except json.JSONDecodeError as error:
                last_json_error = error
                if attempt >= 2:
                    raise
                time.sleep(1.0 + attempt)
                continue
        if last_json_error is not None:
            raise last_json_error
        raise RuntimeError("OpenAI-compatible backend did not receive a usable JSON payload.")


@dataclass(slots=True, frozen=True)
class _MockTopic:
    label: str
    summary: str
    evidence_text: str
    evidence_locator: str


def build_backend(
    *,
    backend_kind: str,
    cache_store: CacheMetadataStore,
    model_name: str,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 120.0,
    temperature: float = 0.2,
) -> DistillationBackend:
    if backend_kind == MockDistillationBackend.kind:
        return MockDistillationBackend(cache_store, model_name=model_name)
    if backend_kind == OpenAICompatibleBackend.kind:
        if base_url is None or api_key is None:
            raise ValueError(
                "OpenAI-compatible backend requires both base_url and api_key."
            )
        return OpenAICompatibleBackend(
            cache_store,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )
    raise ValueError(f"Unsupported backend '{backend_kind}'.")


def build_backend_identity(
    *,
    backend_kind: str,
    model_name: str,
    base_url: str | None = None,
    temperature: float = 0.2,
) -> str:
    identity_parts = [f"kind={backend_kind}", f"model={model_name}"]
    if backend_kind == OpenAICompatibleBackend.kind:
        if base_url is None:
            raise ValueError("OpenAI-compatible backend requires both base_url and api_key.")
        identity_parts.append(f"base_url={_validate_openai_compatible_base_url(base_url)}")
        identity_parts.append(f"temperature={temperature:.6f}")
    return "|".join(identity_parts)


def _validate_openai_compatible_base_url(base_url: str) -> str:
    stripped = base_url.strip()
    if not stripped:
        raise ValueError("OpenAI-compatible backend requires a non-empty base URL.")
    parsed = urlsplit(stripped)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("OpenAI-compatible backend base_url must use http or https.")
    if not parsed.netloc:
        raise ValueError("OpenAI-compatible backend base_url must include a host.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("OpenAI-compatible backend base_url must not embed credentials.")
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("OpenAI-compatible backend base_url must include a valid hostname.")
    if parsed.scheme == "http" and hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            "OpenAI-compatible backend base_url must use https unless it targets localhost."
        )
    return stripped.rstrip("/")


def _extract_source_markdown(prefix_text: str) -> str:
    marker = "[[SOURCE_MARKDOWN]]"
    if marker not in prefix_text:
        return prefix_text
    _, _, source = prefix_text.partition(marker)
    return source.strip()


def _extract_topics(source_markdown: str) -> list[_MockTopic]:
    headings: list[tuple[str, str]] = []
    current_heading = "the paper"
    collected_lines: list[str] = []
    for raw_line in source_markdown.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            if collected_lines:
                headings.append((current_heading, " ".join(collected_lines)))
                collected_lines = []
            current_heading = stripped.lstrip("#").strip() or current_heading
            continue
        if stripped:
            collected_lines.append(stripped)
    if collected_lines:
        headings.append((current_heading, " ".join(collected_lines)))

    if not headings:
        normalized = " ".join(part.strip() for part in source_markdown.splitlines() if part.strip())
        headings = [("the paper", normalized or "the source material")]

    topics: list[_MockTopic] = []
    for index, (heading, paragraph) in enumerate(headings, start=1):
        snippet = paragraph[:280].strip() or heading
        summary = snippet.rstrip(".")
        topics.append(
            _MockTopic(
                label=heading,
                summary=summary,
                evidence_text=snippet,
                evidence_locator=f"section-{index}",
            )
        )
    return topics


def _build_mock_knowledge_map_payload(prefix_text: str) -> dict[str, object]:
    source_markdown = _extract_source_markdown(prefix_text)
    title = _extract_title_from_prefix(prefix_text) or "Untitled Paper"
    topics = _extract_topics(source_markdown)
    sections_present = [topic.label for topic in topics[:8]]
    findings = [topic.summary for topic in topics[:6]]
    return {
        "content_profile": _infer_content_profile(source_markdown),
        "primary_language": _infer_primary_language(source_markdown),
        "study_goal": _pick_sentence(
            source_markdown,
            ("摘要", "目的", "evaluate", "study", "研究", "为", "探讨"),
            fallback=findings[0] if findings else title,
        ),
        "study_object": _pick_sentence(
            source_markdown,
            ("红火蚁", "Solenopsis invicta", "worker ants", "蚁巢", "种群"),
            fallback=title,
        ),
        "experimental_design": _pick_sentence(
            source_markdown,
            ("方法", "试验", "treated", "处理", "施药", "dose", "application"),
            fallback=findings[1] if len(findings) > 1 else findings[0] if findings else title,
        ),
        "sections_present": sections_present or ["paper"],
        "treatments_or_conditions": _collect_sentences(
            source_markdown,
            ("%", "处理", "treatment", "dose", "g/巢", "g/mound", "次"),
            limit=6,
        ),
        "core_metrics": _collect_sentences(
            source_markdown,
            ("死亡率", "数量", "率", "mortality", "density", "increase", "distance"),
            limit=6,
        ),
        "key_findings": findings or [title],
        "limitations": _collect_sentences(
            source_markdown,
            ("持效性", "不能", "慎重", "poor sustainability", "could not", "caution"),
            limit=4,
        ),
        "recommendations": _collect_sentences(
            source_markdown,
            ("建议", "recommended", "recommendation", "应", "should"),
            limit=4,
        ),
    }


def _build_mock_conversation_plan_payload(prefix_text: str, suffix_text: str) -> dict[str, object]:
    target_turn_count = _extract_target_turn_count(suffix_text)
    knowledge_map = _extract_embedded_knowledge_map(prefix_text)
    if knowledge_map is None:
        knowledge_map = _build_mock_knowledge_map_payload(prefix_text)
    content_profile = str(knowledge_map.get("content_profile") or "mixed_or_unclear")
    thread_count = _estimate_thread_count_for_mock(
        content_profile=content_profile,
        target_turn_count=target_turn_count,
    )
    budgets = _distribute_turn_budgets(target_turn_count, thread_count)
    threads: list[dict[str, object]] = []
    topic_specs = _mock_thread_specs(knowledge_map=knowledge_map)
    for index in range(thread_count):
        spec = topic_specs[index % len(topic_specs)]
        threads.append(
            {
                "topic": spec["topic"],
                "rationale": spec["rationale"],
                "turn_budget": budgets[index],
                "must_cover": spec["must_cover"],
                "start_context": spec["start_context"],
            }
        )
    return {"threads": threads}


def _build_mock_conversation_turn_payload(prefix_text: str, suffix_text: str) -> dict[str, object]:
    request = _decode_json_suffix(suffix_text)
    thread_plan = request.get("thread_plan")
    if not isinstance(thread_plan, dict):
        raise ValueError("Conversation generation suffix must include a thread_plan dictionary.")
    topic = _string_or_fallback(thread_plan.get("topic"), "the paper")
    start_context = _string_or_fallback(thread_plan.get("start_context"), topic)
    must_cover = _string_list_or_empty(thread_plan.get("must_cover"))
    existing_thread_turns = request.get("existing_thread_turns")
    if not isinstance(existing_thread_turns, list):
        existing_thread_turns = []
    batch_size = _int_or_fallback(request.get("batch_size"), 1)
    knowledge_map = request.get("knowledge_map")
    study_object = topic
    if isinstance(knowledge_map, dict):
        study_object = _string_or_fallback(knowledge_map.get("study_object"), topic)
    source_markdown = _extract_source_markdown(prefix_text)
    items: list[dict[str, str]] = []
    for offset in range(batch_size):
        turn_index = len(existing_thread_turns) + offset + 1
        coverage_point = must_cover[(turn_index - 1) % len(must_cover)] if must_cover else topic
        evidence = _pick_best_evidence_snippet(source_markdown, (coverage_point, topic, study_object))
        question = _build_mock_question(
            topic=topic,
            study_object=study_object,
            coverage_point=coverage_point,
            start_context=start_context,
            turn_index=turn_index,
        )
        answer = _build_mock_answer(
            topic=topic,
            study_object=study_object,
            coverage_point=coverage_point,
            evidence_text=evidence[0],
            start_context=start_context,
        )
        items.append(
            {
                "question": question,
                "answer": answer,
                "evidence_text": evidence[0],
                "evidence_locator": evidence[1],
            }
        )
    return {"items": items}


def _message_content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts)
    raise ValueError("Message content must be a string or a list of text blocks.")


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _coerce_json_payload_text(content: str) -> str:
    stripped = _strip_json_fence(content)
    candidates: list[str] = []
    for candidate in (
        stripped,
        _extract_json_segment(stripped),
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    for candidate in list(candidates):
        repaired = _remove_trailing_commas(candidate)
        if repaired not in candidates:
            candidates.append(repaired)

    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            _ = json.loads(candidate)
            return candidate
        except json.JSONDecodeError as error:
            last_error = error
    if last_error is not None:
        raise last_error
    raise json.JSONDecodeError("Model response did not contain JSON.", stripped, 0)


def _extract_json_segment(text: str) -> str:
    start_index = -1
    stack: list[str] = []
    in_string = False
    escape = False
    for index, char in enumerate(text):
        if start_index < 0:
            if char not in "{[":
                continue
            start_index = index
            stack.append(char)
            continue

        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == "\"":
                in_string = False
            continue

        if char == "\"":
            in_string = True
            continue
        if char in "{[":
            stack.append(char)
            continue
        if char in "}]":
            if not stack:
                break
            opening = stack.pop()
            if (opening, char) not in {("{", "}"), ("[", "]")}:
                break
            if not stack:
                return text[start_index:index + 1].strip()
    return ""


def _remove_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _decode_json_object(payload_text: str) -> dict[str, object]:
    decoded = cast(object, json.loads(payload_text))
    if not isinstance(decoded, dict):
        raise ValueError("Model response must decode to a dictionary.")
    return cast(dict[str, object], decoded)


def _decode_candidate_items(payload_text: str) -> list[GeneratedQaCandidate]:
    decoded = cast(object, json.loads(payload_text))
    items: object
    if isinstance(decoded, dict):
        items = decoded.get("items")
        if not isinstance(items, list):
            raise ValueError("Model response dictionary must contain an 'items' list.")
    elif isinstance(decoded, list):
        items = decoded
    else:
        raise ValueError("Model response must decode to a dictionary or a list.")
    candidates: list[GeneratedQaCandidate] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each response item must decode to a dictionary.")
        question = item.get("question")
        answer = item.get("answer")
        evidence_text = item.get("evidence_text")
        evidence_locator = item.get("evidence_locator")
        if not all(isinstance(value, str) and value.strip() for value in (question, answer, evidence_text, evidence_locator)):
            raise ValueError(
                "Each response item must include non-empty question, answer, evidence_text, and evidence_locator strings."
            )
        question_text = cast(str, question).strip()
        answer_text = cast(str, answer).strip()
        evidence_text_value = cast(str, evidence_text).strip()
        evidence_locator_value = cast(str, evidence_locator).strip()
        candidates.append(
            GeneratedQaCandidate(
                question=question_text,
                answer=answer_text,
                evidence_text=evidence_text_value,
                evidence_locator=evidence_locator_value,
            )
        )
    return candidates


def _extract_title_from_prefix(prefix_text: str) -> str | None:
    for line in prefix_text.splitlines():
        if line.startswith("Title:"):
            title = line.partition(":")[2].strip()
            if title:
                return title
    return None


def _infer_primary_language(source_markdown: str) -> str:
    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", source_markdown))
    latin_count = len(re.findall(r"[A-Za-z]", source_markdown))
    return "zh" if chinese_count >= latin_count else "en"


def _infer_content_profile(source_markdown: str) -> str:
    has_body_markers = bool(
        re.search(
            r"方法|材料与方法|结果|讨论|结论|\bmethods?\b|\bresults?\b|\bdiscussion\b|\bconclusion\b",
            source_markdown,
            flags=re.IGNORECASE,
        )
    )
    if has_body_markers:
        return "body_available"
    if re.search(r"摘要|abstract", source_markdown, flags=re.IGNORECASE):
        return "abstract_only"
    return "mixed_or_unclear"


def _pick_sentence(source_markdown: str, keywords: tuple[str, ...], *, fallback: str) -> str:
    sentences = _split_sentences(source_markdown)
    lowered_keywords = tuple(keyword.casefold() for keyword in keywords)
    for sentence in sentences:
        normalized = sentence.casefold()
        if any(keyword in normalized for keyword in lowered_keywords):
            return sentence
    return fallback


def _collect_sentences(source_markdown: str, keywords: tuple[str, ...], *, limit: int) -> list[str]:
    sentences = _split_sentences(source_markdown)
    lowered_keywords = tuple(keyword.casefold() for keyword in keywords)
    collected: list[str] = []
    for sentence in sentences:
        normalized = sentence.casefold()
        if any(keyword in normalized for keyword in lowered_keywords):
            collected.append(sentence)
        if len(collected) >= limit:
            break
    return collected


def _split_sentences(source_markdown: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", source_markdown).strip()
    if not normalized:
        return []
    raw_parts = re.split(r"(?<=[。！？!?\.])\s+", normalized)
    sentences = [part.strip() for part in raw_parts if part.strip()]
    return [sentence[:320] for sentence in sentences]


def _extract_suffix_task(suffix_text: str) -> str | None:
    decoded = _decode_json_suffix(suffix_text)
    task = decoded.get("task")
    if isinstance(task, str) and task.strip():
        return task.strip()
    return None


def _decode_json_suffix(suffix_text: str) -> dict[str, object]:
    decoded = cast(object, json.loads(suffix_text))
    if not isinstance(decoded, dict):
        raise ValueError("Suffix payload must decode to a dictionary.")
    return cast(dict[str, object], decoded)


def _extract_embedded_knowledge_map(prefix_text: str) -> dict[str, object] | None:
    marker = "[[KNOWLEDGE_MAP]]"
    if marker not in prefix_text:
        return None
    _, _, payload_text = prefix_text.partition(marker)
    payload_text = payload_text.strip()
    title_marker = "Title:"
    if title_marker in payload_text:
        title_index = payload_text.find(title_marker)
        payload_text = payload_text[title_index + len(title_marker):].strip()
        newline_index = payload_text.find("\n")
        if newline_index >= 0:
            payload_text = payload_text[newline_index + 1 :].strip()
        else:
            return None
    if not payload_text:
        return None
    decoded = cast(object, json.loads(payload_text))
    if not isinstance(decoded, dict):
        return None
    return cast(dict[str, object], decoded)


def _extract_target_turn_count(suffix_text: str) -> int:
    decoded = _decode_json_suffix(suffix_text)
    value = decoded.get("target_turn_count")
    if isinstance(value, int) and value > 0:
        return value
    return 1


def _estimate_thread_count_for_mock(*, content_profile: str, target_turn_count: int) -> int:
    if content_profile == "abstract_only" or target_turn_count <= 4:
        return 1
    if target_turn_count <= 10:
        return 2
    return 3


def _distribute_turn_budgets(target_turn_count: int, thread_count: int) -> list[int]:
    if thread_count <= 0:
        return [target_turn_count]
    minimum = 1
    budgets = [minimum] * thread_count
    remaining = max(target_turn_count - sum(budgets), 0)
    index = 0
    while remaining > 0:
        budgets[index % thread_count] += 1
        remaining -= 1
        index += 1
    return budgets


def _mock_thread_specs(
    *,
    knowledge_map: dict[str, object],
) -> list[dict[str, object]]:
    study_goal = _string_or_fallback(knowledge_map.get("study_goal"), "研究目标")
    study_object = _string_or_fallback(knowledge_map.get("study_object"), "研究对象")
    design = _string_or_fallback(knowledge_map.get("experimental_design"), "研究设计")
    treatments = _string_list_or_empty(knowledge_map.get("treatments_or_conditions"))
    metrics = _string_list_or_empty(knowledge_map.get("core_metrics"))
    findings = _string_list_or_empty(knowledge_map.get("key_findings"))
    limitations = _string_list_or_empty(knowledge_map.get("limitations"))
    recommendations = _string_list_or_empty(knowledge_map.get("recommendations"))
    return [
        {
            "topic": "研究目标与设计",
            "rationale": "先建立研究背景、研究对象和实验设计的连续语境。",
            "must_cover": _bounded_list([study_goal, study_object, design], limit=4),
            "start_context": f"围绕{study_object}，这条线索先交代研究目标与设计，核心目标是{study_goal}。",
        },
        {
            "topic": "主要结果与比较",
            "rationale": "集中覆盖处理条件、评价指标和关键结果，形成连续结果线。",
            "must_cover": _bounded_list(treatments + metrics + findings, limit=5),
            "start_context": f"围绕{study_object}的主要结果比较，这条线索重点覆盖处理条件、指标和变化趋势。",
        },
        {
            "topic": "局限性与应用建议",
            "rationale": "补足解释、局限和应用建议，避免只停留在结果摘录。",
            "must_cover": _bounded_list(limitations + recommendations + findings[-2:], limit=5),
            "start_context": f"在解释{study_object}相关结果时，这条线索继续补充局限性和应用建议。",
        },
    ]


def _pick_best_evidence_snippet(
    source_markdown: str,
    keywords: tuple[str, ...],
) -> tuple[str, str]:
    topics = _extract_topics(source_markdown)
    lowered_keywords = tuple(keyword.casefold() for keyword in keywords if keyword)
    for topic in topics:
        combined = f"{topic.label} {topic.summary}".casefold()
        if any(keyword in combined for keyword in lowered_keywords):
            return (topic.evidence_text, topic.evidence_locator)
    first = topics[0]
    return (first.evidence_text, first.evidence_locator)


def _build_mock_question(
    *,
    topic: str,
    study_object: str,
    coverage_point: str,
    start_context: str,
    turn_index: int,
) -> str:
    if turn_index == 1:
        return f"在{study_object}相关内容里，“{topic}”这条线索是如何交代{coverage_point}这一点的？"
    return f"围绕{study_object}的“{topic}”线索，第{turn_index}轮还能补充哪些与{coverage_point}直接相关的内容？"


def _build_mock_answer(
    *,
    topic: str,
    study_object: str,
    coverage_point: str,
    evidence_text: str,
    start_context: str,
) -> str:
    return f"在{study_object}的“{topic}”线索下，相关内容指出{coverage_point}，依据可归结为：{evidence_text.rstrip('。.')}。"


def _string_or_fallback(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _int_or_fallback(value: object, fallback: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    return fallback


def _string_list_or_empty(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            items.append(item.strip())
    return items


def _bounded_list(items: list[str], *, limit: int) -> list[str]:
    bounded: list[str] = []
    for item in items:
        if item and item not in bounded:
            bounded.append(item)
        if len(bounded) >= limit:
            break
    return bounded or ["core paper evidence"]
