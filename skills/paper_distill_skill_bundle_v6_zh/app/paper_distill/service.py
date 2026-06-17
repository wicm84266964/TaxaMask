from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from app.paper_distill.backends import build_backend, build_backend_identity
from app.paper_distill.cache import CacheMetadataStore, build_cache_key, build_prefix_hash
from app.paper_distill.fs import absolute_path, ensure_safe_file_target
from app.paper_distill.layout import PaperPaths, build_paper_id, build_paths, build_source_hash, extract_title, normalize_markdown_source
from app.paper_distill.models import (
    Checkpoint,
    ConversationPlan,
    ConversationThreadPlan,
    ConversationTurnEntry,
    DistillRunResult,
    GeneratedConversationTurnCandidate,
    KnowledgeMap,
    PreparedPrefix,
    QaEntry,
    RunRequest,
    RunStatus,
)
from app.paper_distill.prompts import (
    CONVERSATION_PLAN_VERSION,
    KNOWLEDGE_MAP_VERSION,
    PROMPT_VERSION,
    build_conversation_generation_suffix,
    build_conversation_plan_prefix,
    build_conversation_plan_suffix,
    build_knowledge_map_prefix,
    build_knowledge_map_suffix,
    build_stable_prefix,
    normalize_question_text,
)
from app.paper_distill.store import PaperArtifactStore
from app.utils import utc_now


class PaperDistillService:
    def run(self, request: RunRequest) -> DistillRunResult:
        if request.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")

        paper_path = absolute_path(request.paper_path)
        ensure_safe_file_target(paper_path)
        raw_source = paper_path.read_text(encoding="utf-8")
        normalized_source = normalize_markdown_source(raw_source)
        if not normalized_source.strip():
            raise ValueError("Paper source is empty after normalization.")

        title = extract_title(paper_path, normalized_source)
        source_hash = build_source_hash(normalized_source)
        paper_id = build_paper_id(title, source_hash)
        paths = build_paths(
            artifacts_root=request.artifacts_root,
            cache_root=request.cache_root,
            paper_id=paper_id,
        )
        artifact_store = PaperArtifactStore(request.artifacts_root)
        cache_store = CacheMetadataStore(request.cache_root)
        backend_identity = build_backend_identity(
            backend_kind=request.backend.kind,
            model_name=request.backend.model_name,
            base_url=request.backend.base_url,
            temperature=request.backend.temperature,
        )

        if request.restart:
            artifact_store.clear_artifact(paths)

        backend = build_backend(
            backend_kind=request.backend.kind,
            cache_store=cache_store,
            model_name=request.backend.model_name,
            base_url=request.backend.base_url,
            api_key=request.backend.api_key,
            timeout_seconds=request.backend.timeout_seconds,
            temperature=request.backend.temperature,
        )
        prefix_text = build_stable_prefix(title=title, normalized_source=normalized_source)
        prefix_hash = build_prefix_hash(prefix_text)
        cache_key = build_cache_key(
            source_hash=source_hash,
            prompt_version=PROMPT_VERSION,
            backend_identity=backend_identity,
        )
        prepared_prefix = backend.prepare_prefix(
            cache_key=cache_key,
            backend_identity=backend_identity,
            prefix_hash=prefix_hash,
            paper_id=paper_id,
            source_hash=source_hash,
            prompt_version=PROMPT_VERSION,
        )

        knowledge_map = self._load_or_build_knowledge_map(
            artifact_store=artifact_store,
            backend=backend,
            paths=paths,
            prepared_prefix=prepared_prefix,
            title=title,
            paper_id=paper_id,
            source_hash=source_hash,
            normalized_source=normalized_source,
        )
        resolved_target_count = resolve_target_count(
            request=request,
            normalized_source=normalized_source,
            knowledge_map=knowledge_map,
        )
        if resolved_target_count <= 0:
            raise ValueError("target_count must be greater than zero.")

        conversation_entries = artifact_store.load_conversation_entries(paths)
        qa_entries = artifact_store.load_entries(paths)
        if conversation_entries and not qa_entries:
            artifact_store.append_entries(paths, [_qa_entry_from_turn(turn) for turn in conversation_entries])
            qa_entries = artifact_store.load_entries(paths)
        _validate_existing_ledgers(qa_entries=qa_entries, conversation_entries=conversation_entries)

        effective_target_count = max(resolved_target_count, len(conversation_entries))
        conversation_plan = self._load_or_build_conversation_plan(
            artifact_store=artifact_store,
            backend=backend,
            paths=paths,
            prepared_prefix=prepared_prefix,
            title=title,
            paper_id=paper_id,
            source_hash=source_hash,
            knowledge_map=knowledge_map,
            target_turn_count=effective_target_count,
            existing_entries=conversation_entries,
        )

        checkpoint = artifact_store.load_checkpoint(paths)
        checkpoint = self._reconcile_checkpoint(
            checkpoint=checkpoint,
            entries=conversation_entries,
            paper_id=paper_id,
            title=title,
            paper_path=paper_path,
            source_hash=source_hash,
            cache_key=cache_key,
            backend_identity=backend_identity,
            prefix_hash=prefix_hash,
            backend_kind=request.backend.kind,
            backend_ref=prepared_prefix.backend_ref,
            model_name=request.backend.model_name,
            target_count=effective_target_count,
            batch_size=request.batch_size,
        )
        artifact_store.save_checkpoint(paths, checkpoint)

        existing_questions = {
            normalize_question_text(entry.question)
            for entry in conversation_entries
            if entry.record_type == "conversation_turn"
        }
        existing_question_texts = [
            entry.question
            for entry in conversation_entries
            if entry.record_type == "conversation_turn"
        ]
        next_ordinal = max(
            max((entry.ordinal for entry in conversation_entries), default=0),
            max((entry.ordinal for entry in qa_entries), default=0),
        ) + 1
        accepted_count = len(conversation_entries)
        entries_written = 0
        stale_attempts_by_thread: Counter[str] = Counter()
        saturated_threads: set[str] = set()
        while accepted_count < effective_target_count:
            thread_plan = _next_thread_to_expand(
                conversation_plan=conversation_plan,
                conversation_entries=conversation_entries,
                skipped_thread_ids=saturated_threads,
            )
            if thread_plan is None:
                if accepted_count <= 0:
                    raise RuntimeError("Conversation plan exhausted before reaching the target turn count.")
                effective_target_count = accepted_count
                checkpoint = Checkpoint(
                    paper_id=paper_id,
                    paper_title=title,
                    paper_path=str(paper_path),
                    source_hash=source_hash,
                    cache_key=cache_key,
                    backend_identity=backend_identity,
                    prefix_hash=prefix_hash,
                    backend_kind=request.backend.kind,
                    backend_ref=prepared_prefix.backend_ref,
                    model_name=request.backend.model_name,
                    prompt_version=PROMPT_VERSION,
                    target_count=effective_target_count,
                    batch_size=request.batch_size,
                    accepted_count=accepted_count,
                    next_ordinal=next_ordinal,
                    status=RunStatus.COMPLETED,
                    created_at=checkpoint.created_at,
                    updated_at=utc_now(),
                )
                artifact_store.save_checkpoint(paths, checkpoint)
                break

            existing_thread_turns = _thread_history_payload(
                conversation_entries=conversation_entries,
                thread_id=thread_plan.thread_id,
                limit=6,
            )
            completed_in_thread = len([entry for entry in conversation_entries if entry.thread_id == thread_plan.thread_id])
            remaining_in_thread = thread_plan.turn_budget - completed_in_thread
            remaining = min(
                request.batch_size,
                effective_target_count - accepted_count,
                remaining_in_thread,
            )
            raw_payload = backend.generate_json_object(
                prefix_text=prefix_text,
                suffix_text=build_conversation_generation_suffix(
                    conversation_id=f"{paper_id}--{thread_plan.thread_id}",
                    thread_plan=_thread_plan_outline(thread_plan),
                    batch_size=remaining,
                    remaining_turns_in_thread=remaining_in_thread,
                    existing_thread_turns=existing_thread_turns,
                    existing_questions=tuple(entry.question for entry in conversation_entries),
                    knowledge_map_outline=_knowledge_map_outline(knowledge_map),
                ),
                prepared_prefix=prepared_prefix,
            )
            candidates = _normalize_conversation_candidates(raw_payload)

            accepted_turn_batch: list[ConversationTurnEntry] = []
            accepted_qa_batch: list[QaEntry] = []
            thread_turn_index = completed_in_thread + 1
            for candidate in candidates:
                normalized_question = normalize_question_text(candidate.question)
                if not normalized_question or normalized_question in existing_questions:
                    continue
                if request.backend.kind != "mock":
                    if _looks_near_duplicate_question(
                        question=candidate.question,
                        existing_questions=tuple(existing_question_texts),
                    ):
                        continue
                if _is_redundant_setup_turn(
                    question=candidate.question,
                    existing_thread_turns=existing_thread_turns,
                    knowledge_map=knowledge_map,
                ):
                    continue
                if _fails_numeric_grounding(
                    question=candidate.question,
                    answer=candidate.answer,
                    evidence_text=candidate.evidence_text,
                ):
                    continue
                if request.backend.kind != "mock":
                    if _question_lacks_explicit_anchor(
                        question=candidate.question,
                        knowledge_map=knowledge_map,
                    ):
                        continue
                    if _question_requests_unsupported_conditions(
                        question=candidate.question,
                        evidence_text=candidate.evidence_text,
                    ):
                        continue
                    if _has_vague_quantitative_placeholder(
                        question=candidate.question,
                        answer=candidate.answer,
                    ):
                        continue
                    if _reuses_evidence_cluster(
                        question=candidate.question,
                        evidence_text=candidate.evidence_text,
                        evidence_locator=candidate.evidence_locator,
                        existing_thread_turns=existing_thread_turns,
                    ):
                        continue
                    if _has_unresolved_reference(
                        question=candidate.question,
                        answer=candidate.answer,
                        knowledge_map=knowledge_map,
                    ):
                        continue
                    if _answer_is_undercontextualized(
                        question=candidate.question,
                        answer=candidate.answer,
                        knowledge_map=knowledge_map,
                    ):
                        continue
                turn_entry = ConversationTurnEntry(
                    turn_id=f"turn_{next_ordinal:04d}",
                    conversation_id=f"{paper_id}--{thread_plan.thread_id}",
                    paper_id=paper_id,
                    thread_id=thread_plan.thread_id,
                    thread_topic=thread_plan.topic,
                    ordinal=next_ordinal,
                    thread_turn_index=thread_turn_index,
                    question=candidate.question.strip(),
                    answer=candidate.answer.strip(),
                    evidence_text=candidate.evidence_text.strip(),
                    evidence_locator=candidate.evidence_locator.strip(),
                    source_hash=source_hash,
                    prompt_version=PROMPT_VERSION,
                    backend_kind=request.backend.kind,
                    model_name=request.backend.model_name,
                )
                accepted_turn_batch.append(turn_entry)
                accepted_qa_batch.append(_qa_entry_from_turn(turn_entry))
                existing_questions.add(normalized_question)
                existing_question_texts.append(candidate.question.strip())
                next_ordinal += 1
                thread_turn_index += 1
                if len(accepted_turn_batch) >= remaining:
                    break

            if not accepted_turn_batch:
                stale_attempts_by_thread[thread_plan.thread_id] += 1
                if stale_attempts_by_thread[thread_plan.thread_id] >= 2:
                    saturated_threads.add(thread_plan.thread_id)
                continue

            artifact_store.append_conversation_entries(paths, accepted_turn_batch)
            artifact_store.append_entries(paths, accepted_qa_batch)
            conversation_entries.extend(accepted_turn_batch)
            qa_entries.extend(accepted_qa_batch)
            entries_written += len(accepted_turn_batch)
            accepted_count = len(conversation_entries)
            checkpoint = Checkpoint(
                paper_id=paper_id,
                paper_title=title,
                paper_path=str(paper_path),
                source_hash=source_hash,
                cache_key=cache_key,
                backend_identity=backend_identity,
                prefix_hash=prefix_hash,
                backend_kind=request.backend.kind,
                backend_ref=prepared_prefix.backend_ref,
                model_name=request.backend.model_name,
                prompt_version=PROMPT_VERSION,
                target_count=effective_target_count,
                batch_size=request.batch_size,
                accepted_count=accepted_count,
                next_ordinal=next_ordinal,
                status=RunStatus.COMPLETED if accepted_count >= effective_target_count else RunStatus.IN_PROGRESS,
                created_at=checkpoint.created_at,
                updated_at=utc_now(),
            )
            artifact_store.save_checkpoint(paths, checkpoint)
            stale_attempts_by_thread[thread_plan.thread_id] = 0

        return DistillRunResult(
            paper_id=paper_id,
            artifact_dir=paths.paper_dir,
            accepted_count=len(conversation_entries),
            entries_written=entries_written,
            cache_status=prepared_prefix.cache_status,
            run_status=RunStatus.COMPLETED,
            target_count=effective_target_count,
        )

    def _load_or_build_knowledge_map(
        self,
        *,
        artifact_store: PaperArtifactStore,
        backend: object,
        paths: PaperPaths,
        prepared_prefix: PreparedPrefix,
        title: str,
        paper_id: str,
        source_hash: str,
        normalized_source: str,
    ) -> KnowledgeMap:
        loaded_map = artifact_store.load_knowledge_map(paths)
        if (
            loaded_map is not None
            and loaded_map.paper_id == paper_id
            and loaded_map.source_hash == source_hash
            and loaded_map.knowledge_map_version == KNOWLEDGE_MAP_VERSION
        ):
            return loaded_map

        raw_payload = backend.generate_json_object(
            prefix_text=build_knowledge_map_prefix(title=title, normalized_source=normalized_source),
            suffix_text=build_knowledge_map_suffix(),
            prepared_prefix=prepared_prefix,
        )
        knowledge_map = _normalize_knowledge_map_payload(
            payload=raw_payload,
            paper_id=paper_id,
            paper_title=title,
            source_hash=source_hash,
            source_language=_infer_source_language(normalized_source),
        )
        artifact_store.save_knowledge_map(paths, knowledge_map)
        return knowledge_map

    def _load_or_build_conversation_plan(
        self,
        *,
        artifact_store: PaperArtifactStore,
        backend: object,
        paths: PaperPaths,
        prepared_prefix: PreparedPrefix,
        title: str,
        paper_id: str,
        source_hash: str,
        knowledge_map: KnowledgeMap,
        target_turn_count: int,
        existing_entries: list[ConversationTurnEntry],
    ) -> ConversationPlan:
        loaded_plan = artifact_store.load_conversation_plan(paths)
        if (
            loaded_plan is not None
            and loaded_plan.paper_id == paper_id
            and loaded_plan.source_hash == source_hash
            and loaded_plan.conversation_plan_version == CONVERSATION_PLAN_VERSION
        ):
            plan = loaded_plan
        else:
            raw_payload = backend.generate_json_object(
                prefix_text=build_conversation_plan_prefix(
                    title=title,
                    knowledge_map_outline=_knowledge_map_outline(knowledge_map),
                ),
                suffix_text=build_conversation_plan_suffix(target_turn_count=target_turn_count),
                prepared_prefix=prepared_prefix,
            )
            plan = _normalize_conversation_plan_payload(
                payload=raw_payload,
                paper_id=paper_id,
                paper_title=title,
                source_hash=source_hash,
                target_turn_count=target_turn_count,
                knowledge_map=knowledge_map,
            )

        resized_plan = _resize_conversation_plan(
            conversation_plan=plan,
            target_turn_count=target_turn_count,
            existing_entries=existing_entries,
            knowledge_map=knowledge_map,
        )
        artifact_store.save_conversation_plan(paths, resized_plan)
        return resized_plan

    def _reconcile_checkpoint(
        self,
        *,
        checkpoint: Checkpoint | None,
        entries: list[ConversationTurnEntry],
        paper_id: str,
        title: str,
        paper_path: Path,
        source_hash: str,
        cache_key: str,
        backend_identity: str,
        prefix_hash: str,
        backend_kind: str,
        backend_ref: str,
        model_name: str,
        target_count: int,
        batch_size: int,
    ) -> Checkpoint:
        accepted_count = len(entries)
        next_ordinal = max((entry.ordinal for entry in entries), default=0) + 1
        if checkpoint is None:
            return Checkpoint(
                paper_id=paper_id,
                paper_title=title,
                paper_path=str(paper_path),
                source_hash=source_hash,
                cache_key=cache_key,
                backend_identity=backend_identity,
                prefix_hash=prefix_hash,
                backend_kind=backend_kind,
                backend_ref=backend_ref,
                model_name=model_name,
                prompt_version=PROMPT_VERSION,
                target_count=target_count,
                batch_size=batch_size,
                accepted_count=accepted_count,
                next_ordinal=next_ordinal,
                status=RunStatus.COMPLETED if accepted_count >= target_count else RunStatus.IN_PROGRESS,
            )

        mismatched_checkpoint = (
            checkpoint.paper_id != paper_id
            or checkpoint.source_hash != source_hash
            or checkpoint.cache_key != cache_key
            or checkpoint.backend_identity != backend_identity
            or checkpoint.prefix_hash != prefix_hash
            or checkpoint.model_name != model_name
            or checkpoint.prompt_version != PROMPT_VERSION
            or checkpoint.backend_kind != backend_kind
        )
        if mismatched_checkpoint:
            raise ValueError(
                "Existing checkpoint does not match the requested paper, backend, or prompt version. Use --restart to regenerate."
            )

        return Checkpoint(
            paper_id=paper_id,
            paper_title=title,
            paper_path=str(paper_path),
            source_hash=source_hash,
            cache_key=cache_key,
            backend_identity=backend_identity,
            prefix_hash=prefix_hash,
            backend_kind=backend_kind,
            backend_ref=backend_ref,
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
            target_count=target_count,
            batch_size=batch_size,
            accepted_count=accepted_count,
            next_ordinal=next_ordinal,
            status=RunStatus.COMPLETED if accepted_count >= target_count else RunStatus.IN_PROGRESS,
            created_at=checkpoint.created_at,
            updated_at=utc_now(),
            last_error=None,
        )


def build_service() -> PaperDistillService:
    return PaperDistillService()


def resolve_target_count(
    *,
    request: RunRequest,
    normalized_source: str,
    knowledge_map: KnowledgeMap | None = None,
) -> int:
    if request.target_count is not None:
        return request.target_count
    if not request.auto_target_count:
        raise ValueError(
            "target_count must be provided unless auto_target_count is enabled."
        )
    return estimate_target_count(
        normalized_source=normalized_source,
        knowledge_map=knowledge_map,
        min_target_count=request.min_target_count,
        max_target_count=request.max_target_count,
    )


def estimate_target_count(
    *,
    normalized_source: str,
    knowledge_map: KnowledgeMap | None = None,
    min_target_count: int = 6,
    max_target_count: int = 24,
) -> int:
    if min_target_count <= 0 or max_target_count <= 0:
        raise ValueError("min_target_count and max_target_count must be greater than zero.")
    if min_target_count > max_target_count:
        raise ValueError("min_target_count must be less than or equal to max_target_count.")

    nonempty_lines = [line.strip() for line in normalized_source.splitlines() if line.strip()]
    compact_text = "\n".join(nonempty_lines)
    effective_char_count = len(re.sub(r"\s+", "", compact_text))
    heading_count = sum(1 for line in nonempty_lines if line.startswith("#"))
    signal_count = len(
        re.findall(
            r"\btable\b|\bfig(?:ure)?\b|图\s*\d+|表\s*\d+|结果|方法|讨论|结论|abstract",
            compact_text,
            flags=re.IGNORECASE,
        )
    )
    content_profile = (
        knowledge_map.content_profile
        if knowledge_map is not None
        else "abstract_only"
        if _looks_abstract_only(nonempty_lines=nonempty_lines, compact_text=compact_text)
        else "body_available"
    )
    chars_per_turn = 1100 if content_profile == "abstract_only" else 650
    char_units = max(1, math.ceil(effective_char_count / chars_per_turn))
    structure_units = max(1, math.ceil(heading_count / 2))
    signal_units = min(signal_count, 10) // 2

    if knowledge_map is not None:
        coverage_units = (
            2
            + min(len(knowledge_map.treatments_or_conditions), 6) // 2
            + min(len(knowledge_map.core_metrics), 6) // 2
            + min(len(knowledge_map.key_findings), 6)
            + min(len(knowledge_map.limitations), 2)
            + min(len(knowledge_map.recommendations), 2)
        )
    else:
        coverage_units = 3 + structure_units + signal_units

    estimated = max(char_units, coverage_units) + min(heading_count, 9) // 3
    bounded_estimate = max(min_target_count, min(max_target_count, estimated))
    if content_profile == "abstract_only":
        abstract_cap = min(max_target_count, max(min_target_count, 8 if char_units <= 4 else 10))
        return min(bounded_estimate, abstract_cap)
    if knowledge_map is not None:
        density_char_units = max(1, math.ceil(effective_char_count / 2000))
        cluster_cap = (
            2
            + min(len(knowledge_map.key_findings), 8)
            + min(math.ceil(len(knowledge_map.limitations) / 2), 2)
            + min(math.ceil(len(knowledge_map.recommendations) / 2), 2)
            + (1 if knowledge_map.experimental_design else 0)
            + (1 if knowledge_map.core_metrics else 0)
            + min(max(density_char_units - 8, 0) // 4, 3)
        )
        bounded_estimate = min(
            bounded_estimate,
            max(min_target_count, min(max_target_count, cluster_cap)),
        )
    return bounded_estimate


def _looks_abstract_only(*, nonempty_lines: list[str], compact_text: str) -> bool:
    heading_count = sum(1 for line in nonempty_lines if line.startswith("#"))
    body_markers = len(
        re.findall(
            r"方法|材料与方法|结果|讨论|结论|\bmethods?\b|\bresults?\b|\bdiscussion\b|\bconclusion\b",
            compact_text,
            flags=re.IGNORECASE,
        )
    )
    abstract_markers = len(re.findall(r"摘要|abstract", compact_text, flags=re.IGNORECASE))
    return abstract_markers > 0 and heading_count <= 1 and body_markers < 2


def _normalize_knowledge_map_payload(
    *,
    payload: dict[str, object],
    paper_id: str,
    paper_title: str,
    source_hash: str,
    source_language: str,
) -> KnowledgeMap:
    model_language = _normalize_language(_coerce_string(payload.get("primary_language"), default="mixed"))
    resolved_language = source_language if source_language != "mixed" else model_language
    normalized_payload = {
        "paper_id": paper_id,
        "paper_title": paper_title,
        "source_hash": source_hash,
        "knowledge_map_version": KNOWLEDGE_MAP_VERSION,
        "content_profile": _coerce_string(payload.get("content_profile"), default="mixed_or_unclear"),
        "primary_language": resolved_language,
        "study_goal": _coerce_string(payload.get("study_goal"), default=paper_title),
        "study_object": _coerce_string(payload.get("study_object"), default=paper_title),
        "experimental_design": _coerce_string(payload.get("experimental_design"), default=paper_title),
        "sections_present": _coerce_string_list(payload.get("sections_present")),
        "treatments_or_conditions": _coerce_string_list(payload.get("treatments_or_conditions")),
        "core_metrics": _coerce_string_list(payload.get("core_metrics")),
        "key_findings": _coerce_string_list(payload.get("key_findings")),
        "limitations": _coerce_string_list(payload.get("limitations")),
        "recommendations": _coerce_string_list(payload.get("recommendations")),
        "created_at": utc_now(),
    }
    return KnowledgeMap.from_dict(normalized_payload)


def _normalize_conversation_plan_payload(
    *,
    payload: dict[str, object],
    paper_id: str,
    paper_title: str,
    source_hash: str,
    target_turn_count: int,
    knowledge_map: KnowledgeMap,
) -> ConversationPlan:
    raw_threads = payload.get("threads")
    thread_limit = _estimate_thread_count(
        knowledge_map=knowledge_map,
        target_turn_count=target_turn_count,
    )
    normalized_threads: list[ConversationThreadPlan] = []
    if isinstance(raw_threads, list):
        for item in raw_threads:
            if not isinstance(item, dict):
                continue
            topic = _coerce_string(item.get("topic"), default="")
            if not topic:
                continue
            normalized_threads.append(
                ConversationThreadPlan(
                    thread_id=f"thread-{len(normalized_threads) + 1:02d}",
                    topic=topic,
                    rationale=_coerce_string(item.get("rationale"), default=topic),
                    turn_budget=_coerce_positive_int(item.get("turn_budget"), default=1),
                    must_cover=tuple(_coerce_string_list(item.get("must_cover"))[:5]),
                    start_context=_coerce_string(item.get("start_context"), default=topic),
                )
            )
            if len(normalized_threads) >= thread_limit:
                break
    if not normalized_threads:
        normalized_threads = _fallback_conversation_threads(
            knowledge_map=knowledge_map,
            target_turn_count=target_turn_count,
        )

    rebalanced_threads = _rebalance_thread_budgets(
        threads=tuple(normalized_threads),
        target_turn_count=target_turn_count,
    )
    return ConversationPlan(
        paper_id=paper_id,
        paper_title=paper_title,
        source_hash=source_hash,
        conversation_plan_version=CONVERSATION_PLAN_VERSION,
        target_turn_count=max(target_turn_count, len(rebalanced_threads)),
        threads=rebalanced_threads,
        created_at=utc_now(),
    )


def _resize_conversation_plan(
    *,
    conversation_plan: ConversationPlan,
    target_turn_count: int,
    existing_entries: list[ConversationTurnEntry],
    knowledge_map: KnowledgeMap,
) -> ConversationPlan:
    if not conversation_plan.threads:
        rebuilt_threads = tuple(
            _fallback_conversation_threads(
                knowledge_map=knowledge_map,
                target_turn_count=target_turn_count,
            )
        )
        return ConversationPlan(
            paper_id=conversation_plan.paper_id,
            paper_title=conversation_plan.paper_title,
            source_hash=conversation_plan.source_hash,
            conversation_plan_version=CONVERSATION_PLAN_VERSION,
            target_turn_count=target_turn_count,
            threads=rebuilt_threads,
            created_at=utc_now(),
        )

    observed_counts = Counter(entry.thread_id for entry in existing_entries)
    minimum_turns = {
        thread.thread_id: max(observed_counts.get(thread.thread_id, 0), 1)
        for thread in conversation_plan.threads
    }
    adjusted_target = max(target_turn_count, sum(observed_counts.values()), len(conversation_plan.threads))
    resized_threads = _rebalance_thread_budgets(
        threads=conversation_plan.threads,
        target_turn_count=adjusted_target,
        minimum_turns=minimum_turns,
    )
    if (
        conversation_plan.target_turn_count == adjusted_target
        and conversation_plan.threads == resized_threads
        and conversation_plan.conversation_plan_version == CONVERSATION_PLAN_VERSION
    ):
        return conversation_plan
    return ConversationPlan(
        paper_id=conversation_plan.paper_id,
        paper_title=conversation_plan.paper_title,
        source_hash=conversation_plan.source_hash,
        conversation_plan_version=CONVERSATION_PLAN_VERSION,
        target_turn_count=adjusted_target,
        threads=resized_threads,
        created_at=conversation_plan.created_at,
    )


def _fallback_conversation_threads(
    *,
    knowledge_map: KnowledgeMap,
    target_turn_count: int,
) -> list[ConversationThreadPlan]:
    thread_count = _estimate_thread_count(
        knowledge_map=knowledge_map,
        target_turn_count=target_turn_count,
    )
    budgets = _round_robin_budgets(
        target_turn_count=max(target_turn_count, thread_count),
        bucket_count=thread_count,
    )
    specs = [
        {
            "topic": "研究目标与设计",
            "rationale": "先建立研究背景、对象和实验设计的连续上下文。",
            "must_cover": [knowledge_map.study_goal, knowledge_map.study_object, knowledge_map.experimental_design],
            "start_context": f"围绕{knowledge_map.study_object}，这条线索先交代研究目标，重点是{knowledge_map.study_goal}。",
        },
        {
            "topic": "主要结果与比较",
            "rationale": "集中蒸馏处理条件、评价指标和关键结果，避免结果碎片化。",
            "must_cover": list(knowledge_map.treatments_or_conditions[:2]) + list(knowledge_map.core_metrics[:2]) + list(knowledge_map.key_findings[:2]),
            "start_context": f"关于{knowledge_map.study_object}的核心结果，这条线索重点比较不同处理和指标变化。",
        },
        {
            "topic": "局限性与建议",
            "rationale": "补足解释、限制和应用建议，增强论文知识闭环。",
            "must_cover": list(knowledge_map.limitations[:2]) + list(knowledge_map.recommendations[:2]) + list(knowledge_map.key_findings[-1:]),
            "start_context": f"除了主要结果，围绕{knowledge_map.study_object}的这条线索还补充局限和应用建议。",
        },
    ]

    threads: list[ConversationThreadPlan] = []
    for index in range(thread_count):
        spec = specs[index]
        must_cover = [item for item in spec["must_cover"] if item]
        if not must_cover:
            must_cover = [knowledge_map.study_object or knowledge_map.paper_title]
        threads.append(
            ConversationThreadPlan(
                thread_id=f"thread-{index + 1:02d}",
                topic=str(spec["topic"]),
                rationale=str(spec["rationale"]),
                turn_budget=budgets[index],
                must_cover=tuple(must_cover[:5]),
                start_context=str(spec["start_context"]),
            )
        )
    return threads


def _estimate_thread_count(*, knowledge_map: KnowledgeMap, target_turn_count: int) -> int:
    if knowledge_map.content_profile == "abstract_only" or target_turn_count <= 4:
        return 1
    if target_turn_count <= 10:
        return 2
    return 3


def _rebalance_thread_budgets(
    *,
    threads: tuple[ConversationThreadPlan, ...],
    target_turn_count: int,
    minimum_turns: dict[str, int] | None = None,
) -> tuple[ConversationThreadPlan, ...]:
    if not threads:
        return tuple()
    minimums = {
        thread.thread_id: (
            minimum_turns[thread.thread_id]
            if minimum_turns is not None and thread.thread_id in minimum_turns
            else 1
        )
        for thread in threads
    }
    adjusted_target = max(target_turn_count, sum(minimums.values()))
    budgets = [max(thread.turn_budget, minimums[thread.thread_id]) for thread in threads]
    total = sum(budgets)
    index = 0
    while total < adjusted_target:
        budgets[index % len(budgets)] += 1
        total += 1
        index += 1
    while total > adjusted_target:
        reduced = False
        for reverse_index in range(len(budgets) - 1, -1, -1):
            minimum = minimums[threads[reverse_index].thread_id]
            if budgets[reverse_index] > minimum:
                budgets[reverse_index] -= 1
                total -= 1
                reduced = True
                if total == adjusted_target:
                    break
        if not reduced:
            break
    return tuple(
        ConversationThreadPlan(
            thread_id=thread.thread_id,
            topic=thread.topic,
            rationale=thread.rationale,
            turn_budget=budgets[index],
            must_cover=thread.must_cover,
            start_context=thread.start_context,
        )
        for index, thread in enumerate(threads)
    )


def _round_robin_budgets(*, target_turn_count: int, bucket_count: int) -> list[int]:
    budgets = [1] * bucket_count
    remaining = max(target_turn_count - sum(budgets), 0)
    index = 0
    while remaining > 0:
        budgets[index % bucket_count] += 1
        remaining -= 1
        index += 1
    return budgets


def _normalize_conversation_candidates(
    payload: dict[str, object],
) -> tuple[GeneratedConversationTurnCandidate, ...]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Conversation generation payload must contain an 'items' list.")
    candidates: list[GeneratedConversationTurnCandidate] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("Each generated conversation item must decode to a dictionary.")
        question = item.get("question")
        answer = item.get("answer")
        evidence_text = item.get("evidence_text")
        evidence_locator = item.get("evidence_locator")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (question, answer, evidence_text, evidence_locator)
        ):
            raise ValueError(
                "Each generated conversation item must include non-empty question, answer, evidence_text, and evidence_locator strings."
            )
        candidates.append(
            GeneratedConversationTurnCandidate(
                question=question.strip(),
                answer=answer.strip(),
                evidence_text=evidence_text.strip(),
                evidence_locator=evidence_locator.strip(),
            )
        )
    return tuple(candidates)


def _thread_history_payload(
    *,
    conversation_entries: list[ConversationTurnEntry],
    thread_id: str,
    limit: int,
) -> tuple[dict[str, str], ...]:
    thread_entries = [entry for entry in conversation_entries if entry.thread_id == thread_id]
    thread_entries.sort(key=lambda item: (item.thread_turn_index, item.ordinal))
    if limit > 0:
        thread_entries = thread_entries[-limit:]
    return tuple(
        {
            "question": entry.question,
            "answer": entry.answer,
            "evidence_text": entry.evidence_text,
            "evidence_locator": entry.evidence_locator,
        }
        for entry in thread_entries
    )


def _thread_plan_outline(thread_plan: ConversationThreadPlan) -> dict[str, object]:
    return {
        "thread_id": thread_plan.thread_id,
        "topic": thread_plan.topic,
        "rationale": thread_plan.rationale,
        "turn_budget": thread_plan.turn_budget,
        "must_cover": list(thread_plan.must_cover),
        "start_context": thread_plan.start_context,
    }


def _knowledge_map_outline(knowledge_map: KnowledgeMap) -> dict[str, object]:
    return {
        "content_profile": knowledge_map.content_profile,
        "primary_language": knowledge_map.primary_language,
        "study_goal": knowledge_map.study_goal,
        "study_object": knowledge_map.study_object,
        "experimental_design": knowledge_map.experimental_design,
        "sections_present": list(knowledge_map.sections_present[:6]),
        "treatments_or_conditions": list(knowledge_map.treatments_or_conditions[:6]),
        "core_metrics": list(knowledge_map.core_metrics[:6]),
        "key_findings": list(knowledge_map.key_findings[:6]),
        "limitations": list(knowledge_map.limitations[:4]),
        "recommendations": list(knowledge_map.recommendations[:4]),
    }


def _next_thread_to_expand(
    *,
    conversation_plan: ConversationPlan,
    conversation_entries: list[ConversationTurnEntry],
    skipped_thread_ids: set[str] | None = None,
) -> ConversationThreadPlan | None:
    completed_by_thread = Counter(entry.thread_id for entry in conversation_entries)
    skipped = skipped_thread_ids or set()
    for thread in conversation_plan.threads:
        if thread.thread_id in skipped:
            continue
        if completed_by_thread.get(thread.thread_id, 0) < thread.turn_budget:
            return thread
    return None


def _is_redundant_setup_turn(
    *,
    question: str,
    existing_thread_turns: tuple[dict[str, str], ...],
    knowledge_map: KnowledgeMap,
) -> bool:
    if knowledge_map.content_profile == "abstract_only":
        return False
    if not existing_thread_turns:
        return False
    previous_question = existing_thread_turns[-1]["question"]
    return _looks_setup_heavy(previous_question) and _looks_setup_heavy(question)


def _looks_setup_heavy(text: str) -> bool:
    lowered = text.casefold()
    setup_markers = (
        "试验", "设计", "设置", "对照", "地点", "时间", "方法", "指标",
        "design", "setup", "control", "site", "time", "method", "metric",
    )
    result_markers = (
        "结果", "下降", "上升", "差异", "影响", "比较", "恢复", "死亡率",
        "result", "decrease", "increase", "difference", "comparison", "recovery", "mortality",
    )
    setup_hits = sum(1 for marker in setup_markers if marker in lowered)
    result_hits = sum(1 for marker in result_markers if marker in lowered)
    return setup_hits >= 2 and result_hits == 0


def _fails_numeric_grounding(
    *,
    question: str,
    answer: str,
    evidence_text: str,
) -> bool:
    if not _question_requests_precise_numbers(question):
        return False
    evidence_numbers = _extract_number_tokens(evidence_text)
    if len(evidence_numbers) < 2 or len(evidence_numbers) > 8:
        return False
    return any(number not in answer for number in evidence_numbers)


def _question_requests_unsupported_conditions(
    *,
    question: str,
    evidence_text: str,
) -> bool:
    if not _question_requests_precise_numbers(question):
        return False
    question_groups = _extract_condition_number_groups(question)
    if not question_groups:
        return False
    evidence_groups = _extract_condition_number_groups(evidence_text)
    for unit, requested_numbers in question_groups.items():
        if len(requested_numbers) < 3:
            continue
        evidence_numbers = evidence_groups.get(unit, tuple())
        if not evidence_numbers:
            return True
        if any(number not in evidence_numbers for number in requested_numbers):
            return True
    return False


def _has_unresolved_reference(
    *,
    question: str,
    answer: str,
    knowledge_map: KnowledgeMap,
) -> bool:
    return _contains_unresolved_reference(question, knowledge_map) or _contains_unresolved_reference(
        answer,
        knowledge_map,
    )


def _contains_unresolved_reference(text: str, knowledge_map: KnowledgeMap) -> bool:
    lowered = text.casefold()
    if re.search(r"(?:图|表)\s*\d+", text):
        return True
    always_ambiguous_markers = (
        "本文", "该文", "这篇文章", "前者", "后者", "上述", "以下", "上文", "下文",
    )
    if any(marker in lowered for marker in always_ambiguous_markers):
        return True
    conditional_markers = (
        "本研究", "该研究", "这篇研究", "这项研究", "本试验", "该试验",
    )
    if any(marker in lowered for marker in conditional_markers):
        return not _has_contextual_anchor(text, knowledge_map)
    return False


def _answer_is_undercontextualized(
    *,
    question: str,
    answer: str,
    knowledge_map: KnowledgeMap,
) -> bool:
    stripped = answer.strip()
    if not stripped:
        return True
    if _opening_uses_meta_study_reference(stripped):
        return True
    if not _has_named_contextual_anchor(_opening_context_window(stripped, max_chars=120), knowledge_map):
        return True
    if len(stripped) < 70:
        return True
    complex_question = _looks_complex_knowledge_question(question)
    if complex_question and not _has_contextual_anchor(stripped, knowledge_map):
        return True
    if complex_question and len(stripped) < 120:
        return True
    sentence_count = max(1, len(re.findall(r"[。！？!?]", stripped)))
    if complex_question and sentence_count < 2 and len(stripped) < 170:
        return True
    return False


def _question_lacks_explicit_anchor(
    *,
    question: str,
    knowledge_map: KnowledgeMap,
) -> bool:
    stripped = question.strip()
    if not stripped:
        return True
    if _opening_uses_meta_study_reference(stripped):
        return True
    return not _has_named_contextual_anchor(_opening_context_window(stripped, max_chars=120), knowledge_map)


def _opening_uses_meta_study_reference(text: str) -> bool:
    opening = _opening_context_window(text, max_chars=80)
    normalized = re.sub(r"\s+", "", opening)
    if re.match(r"^(?:本研究|本试验|本实验|该研究|该试验|该实验|这项研究|这项试验|这项实验)", normalized):
        return True
    if re.match(r"^(?:这项|该项|本项).{0,18}?(?:研究|试验|实验)", normalized):
        return True
    return bool(re.match(r"^(?:this|the)\s+(?:study|trial|experiment)\b", opening.casefold()))


def _question_requests_precise_numbers(question: str) -> bool:
    lowered = question.casefold()
    markers = (
        "多少", "分别", "多大", "几次", "percent", "percentage", "respectively",
        "降幅", "升高", "下降", "上升", "死亡率", "数量", "剂量",
        "第1次", "第2次", "第3次", "1 d", "2 d", "3 d",
    )
    return any(marker.casefold() in lowered for marker in markers)


def _extract_number_tokens(text: str) -> tuple[str, ...]:
    matches = re.findall(r"\d+(?:\.\d+)?%?", text)
    numbers: list[str] = []
    for match in matches:
        if match not in numbers:
            numbers.append(match)
    return tuple(numbers)


def _extract_condition_number_groups(text: str) -> dict[str, tuple[str, ...]]:
    unit_pattern = r"(g\s*/\s*巢|g\s*/\s*mound|次|d|天|μg\s*/\s*mL|μg\s*/\s*头|头|m)"
    groups: dict[str, list[str]] = {}
    for match in re.finditer(
        rf"((?:\d+(?:\.\d+)?\s*(?:、|,|，|和|及|至|到|-|—)\s*)+\d+(?:\.\d+)?)\s*{unit_pattern}",
        text,
        flags=re.IGNORECASE,
    ):
        sequence, unit = match.group(1), match.group(2)
        normalized_unit = re.sub(r"\s+", "", unit)
        bucket = groups.setdefault(normalized_unit, [])
        for number in re.findall(r"\d+(?:\.\d+)?", sequence):
            if number not in bucket:
                bucket.append(number)
    for match in re.finditer(
        rf"(?<![\d.])(\d+(?:\.\d+)?)\s*{unit_pattern}",
        text,
        flags=re.IGNORECASE,
    ):
        number, unit = match.group(1), match.group(2)
        normalized_unit = re.sub(r"\s+", "", unit)
        bucket = groups.setdefault(normalized_unit, [])
        if number not in bucket:
            bucket.append(number)
    return {unit: tuple(numbers) for unit, numbers in groups.items()}


def _has_vague_quantitative_placeholder(
    *,
    question: str,
    answer: str,
) -> bool:
    if not _question_requests_precise_numbers(question):
        return False
    condition_count = sum(
        len(numbers)
        for unit, numbers in _extract_condition_number_groups(question).items()
        if unit not in {"d", "天"}
    )
    if condition_count < 2:
        return False
    vague_markers = (
        "更高的压低趋势",
        "更强的短期抑制",
        "更高的抑制趋势",
        "更强的压低作用",
        "更明显的压低趋势",
        "更高剂量下进一步压低",
        "进一步压低趋势",
        "进一步压低",
        "进一步抑制",
        "短期抑制更强",
    )
    return any(marker in answer for marker in vague_markers)


def _looks_near_duplicate_question(
    *,
    question: str,
    existing_questions: tuple[str, ...],
) -> bool:
    candidate_tokens = set(_question_overlap_tokens(question))
    if len(candidate_tokens) < 4:
        return False
    candidate_numbers = set(_extract_number_tokens(question))
    for existing in existing_questions:
        existing_tokens = set(_question_overlap_tokens(existing))
        if len(existing_tokens) < 4:
            continue
        overlap = len(candidate_tokens & existing_tokens)
        if overlap == 0:
            continue
        union = len(candidate_tokens | existing_tokens)
        similarity = overlap / max(union, 1)
        shared_numbers = bool(candidate_numbers & set(_extract_number_tokens(existing)))
        if similarity >= 0.52 and (shared_numbers or overlap >= 6):
            return True
        if similarity >= 0.33 and shared_numbers and overlap >= 18:
            return True
    return False


def _question_overlap_tokens(text: str) -> tuple[str, ...]:
    raw_tokens: list[str] = []
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        if len(segment) <= 3:
            raw_tokens.append(segment)
            continue
        raw_tokens.extend(segment[index:index + 2] for index in range(len(segment) - 1))
    raw_tokens.extend(re.findall(r"[A-Za-z]{4,}|\d+(?:\.\d+)?%?", text))
    generic_tokens = {
        "研究", "试验", "处理", "结果", "影响", "多少", "分别", "什么", "如何", "是否",
        "为什么", "田间", "单蚁", "蚁巢", "different", "study", "trial", "result", "results", "effect", "effects",
        "what", "core", "point", "does", "paper", "make", "about",
    }
    tokens: list[str] = []
    for token in raw_tokens:
        normalized = token.casefold()
        if normalized in generic_tokens:
            continue
        if token not in tokens:
            tokens.append(token)
    return tuple(tokens)


def _evidence_overlap_tokens(*, evidence_text: str, evidence_locator: str) -> tuple[str, ...]:
    raw_tokens: list[str] = []
    combined = f"{evidence_locator} {evidence_text}"
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", combined):
        if len(segment) <= 3:
            raw_tokens.append(segment)
            continue
        raw_tokens.extend(segment[index:index + 2] for index in range(len(segment) - 1))
    raw_tokens.extend(re.findall(r"[A-Za-z]{4,}|\d+(?:\.\d+)?%?", combined))
    generic_tokens = {
        "结果", "分析", "讨论", "摘要", "材料", "方法", "处理", "数量",
        "section", "table", "figure", "result", "results", "discussion", "method", "methods",
    }
    tokens: list[str] = []
    for token in raw_tokens:
        normalized = token.casefold()
        if normalized in generic_tokens:
            continue
        if token not in tokens:
            tokens.append(token)
    return tuple(tokens)


def _reuses_evidence_cluster(
    *,
    question: str,
    evidence_text: str,
    evidence_locator: str,
    existing_thread_turns: tuple[dict[str, str], ...],
) -> bool:
    if not existing_thread_turns:
        return False
    candidate_question_tokens = set(_question_overlap_tokens(question))
    candidate_evidence_tokens = set(
        _evidence_overlap_tokens(
            evidence_text=evidence_text,
            evidence_locator=evidence_locator,
        )
    )
    if len(candidate_evidence_tokens) < 4:
        return False
    candidate_numbers = set(_extract_number_tokens(question)) | set(_extract_number_tokens(evidence_text))
    for turn in existing_thread_turns:
        existing_evidence_tokens = set(
            _evidence_overlap_tokens(
                evidence_text=turn.get("evidence_text", ""),
                evidence_locator=turn.get("evidence_locator", ""),
            )
        )
        if len(existing_evidence_tokens) < 4:
            continue
        evidence_overlap = len(candidate_evidence_tokens & existing_evidence_tokens)
        evidence_union = len(candidate_evidence_tokens | existing_evidence_tokens)
        evidence_similarity = evidence_overlap / max(evidence_union, 1)
        if evidence_similarity < 0.42:
            continue
        existing_question_tokens = set(_question_overlap_tokens(turn.get("question", "")))
        question_overlap = len(candidate_question_tokens & existing_question_tokens)
        question_union = len(candidate_question_tokens | existing_question_tokens)
        question_similarity = question_overlap / max(question_union, 1)
        existing_numbers = set(_extract_number_tokens(turn.get("question", ""))) | set(
            _extract_number_tokens(turn.get("evidence_text", ""))
        )
        shared_numbers = candidate_numbers & existing_numbers
        if question_similarity >= 0.24 or question_overlap >= 18 or len(shared_numbers) >= 4:
            return True
    return False


def _looks_complex_knowledge_question(question: str) -> bool:
    lowered = question.casefold()
    markers = (
        "分别", "比较", "差异", "变化", "趋势", "恢复", "影响", "为什么", "说明",
        "如何理解", "是否", "结合", "综合", "同时", "差别", "解释", "limitation",
        "compare", "difference", "trend", "recovery", "interpret", "implication",
    )
    marker_hits = sum(1 for marker in markers if marker in lowered)
    clause_hits = question.count("，") + question.count("；") + question.count("?") + question.count("？")
    number_hits = len(_extract_number_tokens(question))
    return marker_hits >= 2 or clause_hits >= 2 or number_hits >= 3


def _has_contextual_anchor(text: str, knowledge_map: KnowledgeMap) -> bool:
    snippet = text[:140]
    lowered = snippet.casefold()
    return any(token.casefold() in lowered for token in _knowledge_anchor_tokens(knowledge_map))


def _has_named_contextual_anchor(text: str, knowledge_map: KnowledgeMap) -> bool:
    snippet = text[:140]
    lowered = snippet.casefold()
    return any(
        re.search(r"[A-Za-z\u4e00-\u9fff]", token) and token.casefold() in lowered
        for token in _knowledge_anchor_tokens(knowledge_map)
    )


def _knowledge_anchor_tokens(knowledge_map: KnowledgeMap) -> tuple[str, ...]:
    generic_tokens = {
        "研究", "试验", "处理", "结果", "方法", "指标", "影响", "分析", "比较", "对照",
        "study", "experiment", "treatment", "result", "results", "method", "methods",
        "metric", "metrics", "analysis", "control", "comparison",
        "防治", "效果", "评价", "应用", "设计", "条件", "管理", "体系", "技术", "方案",
        "趋势", "变化", "差异", "作用", "场景", "对象", "目标", "意义",
    }
    fields = [
        knowledge_map.study_goal,
        knowledge_map.study_object,
        knowledge_map.experimental_design,
        *knowledge_map.treatments_or_conditions[:6],
        *knowledge_map.core_metrics[:6],
    ]
    tokens: list[str] = []
    for field in fields:
        for token in _extract_anchor_fragments(field):
            normalized = token.casefold()
            if normalized in generic_tokens:
                continue
            if token not in tokens:
                tokens.append(token)
    tokens.sort(key=len, reverse=True)
    return tuple(tokens)


def _extract_anchor_fragments(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        if len(segment) <= 4:
            if segment not in tokens:
                tokens.append(segment)
            continue
        for size in (6, 5, 4):
            if len(segment) < size:
                continue
            for index in range(len(segment) - size + 1):
                token = segment[index:index + size]
                if token not in tokens:
                    tokens.append(token)
    for token in re.findall(
        r"[A-Za-z]{3,}(?:[A-Za-z0-9._-]{0,24})|\d+(?:\.\d+)?%?(?:\s*/\s*[A-Za-z\u4e00-\u9fff]+)?",
        text,
    ):
        if token not in tokens:
            tokens.append(token)
    return tuple(tokens)


def _opening_context_window(text: str, *, max_chars: int) -> str:
    sentence = re.split(r"[。！？!?]", text.strip(), maxsplit=1)[0]
    return sentence[:max_chars]


def _qa_entry_from_turn(turn: ConversationTurnEntry) -> QaEntry:
    return QaEntry(
        qa_id=f"qa_{turn.ordinal:04d}",
        paper_id=turn.paper_id,
        ordinal=turn.ordinal,
        question=turn.question,
        answer=turn.answer,
        evidence_text=turn.evidence_text,
        evidence_locator=turn.evidence_locator,
        source_hash=turn.source_hash,
        prompt_version=turn.prompt_version,
        backend_kind=turn.backend_kind,
        model_name=turn.model_name,
        created_at=turn.created_at,
    )


def _validate_existing_ledgers(
    *,
    qa_entries: list[QaEntry],
    conversation_entries: list[ConversationTurnEntry],
) -> None:
    if not qa_entries or not conversation_entries:
        return
    if len(qa_entries) != len(conversation_entries):
        raise ValueError("QA and conversation ledgers are out of sync. Use --restart to regenerate.")
    ordered_qas = sorted(qa_entries, key=lambda item: (item.ordinal, item.qa_id))
    ordered_turns = sorted(conversation_entries, key=lambda item: (item.ordinal, item.turn_id))
    for qa_entry, turn_entry in zip(ordered_qas, ordered_turns):
        if qa_entry.ordinal != turn_entry.ordinal or qa_entry.question != turn_entry.question or qa_entry.answer != turn_entry.answer:
            raise ValueError("QA and conversation ledgers are inconsistent. Use --restart to regenerate.")


def _coerce_string(value: object, *, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _coerce_positive_int(value: object, *, default: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    return default


def _coerce_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped and stripped not in items:
                items.append(stripped)
    return items


def _normalize_language(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized in {"zh", "zh-cn", "chinese"}:
        return "zh"
    if normalized in {"en", "english"}:
        return "en"
    return "mixed"


def _infer_source_language(normalized_source: str) -> str:
    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", normalized_source))
    latin_token_count = len(re.findall(r"[A-Za-z]+", normalized_source))
    if chinese_count == 0 and latin_token_count == 0:
        return "mixed"
    if chinese_count == 0:
        return "en"
    if latin_token_count == 0:
        return "zh"
    if chinese_count >= max(160, int(latin_token_count * 1.2)):
        return "zh"
    if latin_token_count >= max(160, int(chinese_count * 1.2)):
        return "en"
    return "mixed"
