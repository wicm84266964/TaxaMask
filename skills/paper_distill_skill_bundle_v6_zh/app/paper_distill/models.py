from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from app.types import JSONValue
from app.utils import utc_now


class QaStatus(StrEnum):
    ACCEPTED = "accepted"


class RunStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CacheStatus(StrEnum):
    CREATED = "created"
    REUSED = "reused"


class ExportFormat(StrEnum):
    JSON = "json"
    JSONL = "jsonl"
    CONVERSATION_JSONL = "conversation-jsonl"


@dataclass(slots=True, frozen=True)
class PaperRef:
    paper_id: str
    title: str
    source_path: str
    source_hash: str

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "source_path": self.source_path,
            "source_hash": self.source_hash,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JSONValue]) -> "PaperRef":
        return cls(
            paper_id=_require_string(payload, "paper_id"),
            title=_require_string(payload, "title"),
            source_path=_require_string(payload, "source_path"),
            source_hash=_require_string(payload, "source_hash"),
        )


@dataclass(slots=True, frozen=True)
class KnowledgeMap:
    paper_id: str
    paper_title: str
    source_hash: str
    knowledge_map_version: str
    content_profile: str
    primary_language: str
    study_goal: str
    study_object: str
    experimental_design: str
    sections_present: tuple[str, ...]
    treatments_or_conditions: tuple[str, ...]
    core_metrics: tuple[str, ...]
    key_findings: tuple[str, ...]
    limitations: tuple[str, ...]
    recommendations: tuple[str, ...]
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "paper_id": self.paper_id,
            "paper_title": self.paper_title,
            "source_hash": self.source_hash,
            "knowledge_map_version": self.knowledge_map_version,
            "content_profile": self.content_profile,
            "primary_language": self.primary_language,
            "study_goal": self.study_goal,
            "study_object": self.study_object,
            "experimental_design": self.experimental_design,
            "sections_present": list(self.sections_present),
            "treatments_or_conditions": list(self.treatments_or_conditions),
            "core_metrics": list(self.core_metrics),
            "key_findings": list(self.key_findings),
            "limitations": list(self.limitations),
            "recommendations": list(self.recommendations),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JSONValue]) -> "KnowledgeMap":
        return cls(
            paper_id=_require_string(payload, "paper_id"),
            paper_title=_require_string(payload, "paper_title"),
            source_hash=_require_string(payload, "source_hash"),
            knowledge_map_version=_require_string(payload, "knowledge_map_version"),
            content_profile=_require_string(payload, "content_profile"),
            primary_language=_require_string(payload, "primary_language"),
            study_goal=_require_string(payload, "study_goal"),
            study_object=_require_string(payload, "study_object"),
            experimental_design=_require_string(payload, "experimental_design"),
            sections_present=tuple(_require_list_of_strings(payload, "sections_present")),
            treatments_or_conditions=tuple(_require_list_of_strings(payload, "treatments_or_conditions")),
            core_metrics=tuple(_require_list_of_strings(payload, "core_metrics")),
            key_findings=tuple(_require_list_of_strings(payload, "key_findings")),
            limitations=tuple(_require_list_of_strings(payload, "limitations")),
            recommendations=tuple(_require_list_of_strings(payload, "recommendations")),
            created_at=_require_string(payload, "created_at"),
        )


@dataclass(slots=True, frozen=True)
class ConversationThreadPlan:
    thread_id: str
    topic: str
    rationale: str
    turn_budget: int
    must_cover: tuple[str, ...]
    start_context: str

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "thread_id": self.thread_id,
            "topic": self.topic,
            "rationale": self.rationale,
            "turn_budget": self.turn_budget,
            "must_cover": list(self.must_cover),
            "start_context": self.start_context,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JSONValue]) -> "ConversationThreadPlan":
        return cls(
            thread_id=_require_string(payload, "thread_id"),
            topic=_require_string(payload, "topic"),
            rationale=_require_string(payload, "rationale"),
            turn_budget=_require_int(payload, "turn_budget"),
            must_cover=tuple(_require_list_of_strings(payload, "must_cover")),
            start_context=_require_string(payload, "start_context"),
        )


@dataclass(slots=True, frozen=True)
class ConversationPlan:
    paper_id: str
    paper_title: str
    source_hash: str
    conversation_plan_version: str
    target_turn_count: int
    threads: tuple[ConversationThreadPlan, ...]
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "paper_id": self.paper_id,
            "paper_title": self.paper_title,
            "source_hash": self.source_hash,
            "conversation_plan_version": self.conversation_plan_version,
            "target_turn_count": self.target_turn_count,
            "threads": [thread.to_dict() for thread in self.threads],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JSONValue]) -> "ConversationPlan":
        threads_raw = payload.get("threads")
        if not isinstance(threads_raw, list):
            raise ValueError("Field 'threads' must be a list.")
        threads: list[ConversationThreadPlan] = []
        for item in threads_raw:
            if not isinstance(item, dict):
                raise ValueError("Each thread entry must decode to a dictionary.")
            threads.append(ConversationThreadPlan.from_dict(item))
        return cls(
            paper_id=_require_string(payload, "paper_id"),
            paper_title=_require_string(payload, "paper_title"),
            source_hash=_require_string(payload, "source_hash"),
            conversation_plan_version=_require_string(payload, "conversation_plan_version"),
            target_turn_count=_require_int(payload, "target_turn_count"),
            threads=tuple(threads),
            created_at=_require_string(payload, "created_at"),
        )


@dataclass(slots=True, frozen=True)
class QaEntry:
    qa_id: str
    paper_id: str
    ordinal: int
    question: str
    answer: str
    evidence_text: str
    evidence_locator: str
    source_hash: str
    prompt_version: str
    backend_kind: str
    model_name: str
    status: QaStatus = QaStatus.ACCEPTED
    record_type: str = "qa"
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "record_type": self.record_type,
            "qa_id": self.qa_id,
            "paper_id": self.paper_id,
            "ordinal": self.ordinal,
            "question": self.question,
            "answer": self.answer,
            "evidence_text": self.evidence_text,
            "evidence_locator": self.evidence_locator,
            "source_hash": self.source_hash,
            "prompt_version": self.prompt_version,
            "backend_kind": self.backend_kind,
            "model_name": self.model_name,
            "status": self.status.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JSONValue]) -> "QaEntry":
        return cls(
            qa_id=_require_string(payload, "qa_id"),
            paper_id=_require_string(payload, "paper_id"),
            ordinal=_require_int(payload, "ordinal"),
            question=_require_string(payload, "question"),
            answer=_require_string(payload, "answer"),
            evidence_text=_require_string(payload, "evidence_text"),
            evidence_locator=_require_string(payload, "evidence_locator"),
            source_hash=_require_string(payload, "source_hash"),
            prompt_version=_require_string(payload, "prompt_version"),
            backend_kind=_require_string(payload, "backend_kind"),
            model_name=_require_string(payload, "model_name"),
            status=QaStatus(_require_string(payload, "status")),
            record_type=_require_string(payload, "record_type"),
            created_at=_require_string(payload, "created_at"),
        )


@dataclass(slots=True, frozen=True)
class ConversationTurnEntry:
    turn_id: str
    conversation_id: str
    paper_id: str
    thread_id: str
    thread_topic: str
    ordinal: int
    thread_turn_index: int
    question: str
    answer: str
    evidence_text: str
    evidence_locator: str
    source_hash: str
    prompt_version: str
    backend_kind: str
    model_name: str
    record_type: str = "conversation_turn"
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "record_type": self.record_type,
            "turn_id": self.turn_id,
            "conversation_id": self.conversation_id,
            "paper_id": self.paper_id,
            "thread_id": self.thread_id,
            "thread_topic": self.thread_topic,
            "ordinal": self.ordinal,
            "thread_turn_index": self.thread_turn_index,
            "question": self.question,
            "answer": self.answer,
            "evidence_text": self.evidence_text,
            "evidence_locator": self.evidence_locator,
            "source_hash": self.source_hash,
            "prompt_version": self.prompt_version,
            "backend_kind": self.backend_kind,
            "model_name": self.model_name,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JSONValue]) -> "ConversationTurnEntry":
        return cls(
            turn_id=_require_string(payload, "turn_id"),
            conversation_id=_require_string(payload, "conversation_id"),
            paper_id=_require_string(payload, "paper_id"),
            thread_id=_require_string(payload, "thread_id"),
            thread_topic=_require_string(payload, "thread_topic"),
            ordinal=_require_int(payload, "ordinal"),
            thread_turn_index=_require_int(payload, "thread_turn_index"),
            question=_require_string(payload, "question"),
            answer=_require_string(payload, "answer"),
            evidence_text=_require_string(payload, "evidence_text"),
            evidence_locator=_require_string(payload, "evidence_locator"),
            source_hash=_require_string(payload, "source_hash"),
            prompt_version=_require_string(payload, "prompt_version"),
            backend_kind=_require_string(payload, "backend_kind"),
            model_name=_require_string(payload, "model_name"),
            record_type=_require_string(payload, "record_type"),
            created_at=_require_string(payload, "created_at"),
        )


@dataclass(slots=True, frozen=True)
class CacheRecord:
    cache_key: str
    backend_identity: str
    prefix_hash: str
    backend_kind: str
    backend_ref: str
    paper_id: str
    source_hash: str
    prompt_version: str
    model_name: str
    created_at: str = field(default_factory=utc_now)
    last_used_at: str = field(default_factory=utc_now)

    def touch(self) -> "CacheRecord":
        return CacheRecord(
            cache_key=self.cache_key,
            backend_identity=self.backend_identity,
            prefix_hash=self.prefix_hash,
            backend_kind=self.backend_kind,
            backend_ref=self.backend_ref,
            paper_id=self.paper_id,
            source_hash=self.source_hash,
            prompt_version=self.prompt_version,
            model_name=self.model_name,
            created_at=self.created_at,
            last_used_at=utc_now(),
        )

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "cache_key": self.cache_key,
            "backend_identity": self.backend_identity,
            "prefix_hash": self.prefix_hash,
            "backend_kind": self.backend_kind,
            "backend_ref": self.backend_ref,
            "paper_id": self.paper_id,
            "source_hash": self.source_hash,
            "prompt_version": self.prompt_version,
            "model_name": self.model_name,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JSONValue]) -> "CacheRecord":
        return cls(
            cache_key=_require_string(payload, "cache_key"),
            backend_identity=_optional_string(payload.get("backend_identity")) or "",
            prefix_hash=_require_string(payload, "prefix_hash"),
            backend_kind=_require_string(payload, "backend_kind"),
            backend_ref=_require_string(payload, "backend_ref"),
            paper_id=_require_string(payload, "paper_id"),
            source_hash=_require_string(payload, "source_hash"),
            prompt_version=_require_string(payload, "prompt_version"),
            model_name=_require_string(payload, "model_name"),
            created_at=_require_string(payload, "created_at"),
            last_used_at=_require_string(payload, "last_used_at"),
        )


@dataclass(slots=True, frozen=True)
class Checkpoint:
    paper_id: str
    paper_title: str
    paper_path: str
    source_hash: str
    cache_key: str
    prefix_hash: str
    backend_kind: str
    backend_ref: str
    model_name: str
    prompt_version: str
    target_count: int
    batch_size: int
    accepted_count: int
    next_ordinal: int
    status: RunStatus
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    last_error: str | None = None
    backend_identity: str = ""

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "paper_id": self.paper_id,
            "paper_title": self.paper_title,
            "paper_path": self.paper_path,
            "source_hash": self.source_hash,
            "cache_key": self.cache_key,
            "backend_identity": self.backend_identity,
            "prefix_hash": self.prefix_hash,
            "backend_kind": self.backend_kind,
            "backend_ref": self.backend_ref,
            "model_name": self.model_name,
            "prompt_version": self.prompt_version,
            "target_count": self.target_count,
            "batch_size": self.batch_size,
            "accepted_count": self.accepted_count,
            "next_ordinal": self.next_ordinal,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JSONValue]) -> "Checkpoint":
        return cls(
            paper_id=_require_string(payload, "paper_id"),
            paper_title=_require_string(payload, "paper_title"),
            paper_path=_require_string(payload, "paper_path"),
            source_hash=_require_string(payload, "source_hash"),
            cache_key=_require_string(payload, "cache_key"),
            backend_identity=_optional_string(payload.get("backend_identity")) or "",
            prefix_hash=_require_string(payload, "prefix_hash"),
            backend_kind=_require_string(payload, "backend_kind"),
            backend_ref=_require_string(payload, "backend_ref"),
            model_name=_require_string(payload, "model_name"),
            prompt_version=_require_string(payload, "prompt_version"),
            target_count=_require_int(payload, "target_count"),
            batch_size=_require_int(payload, "batch_size"),
            accepted_count=_require_int(payload, "accepted_count"),
            next_ordinal=_require_int(payload, "next_ordinal"),
            status=RunStatus(_require_string(payload, "status")),
            created_at=_require_string(payload, "created_at"),
            updated_at=_require_string(payload, "updated_at"),
            last_error=_optional_string(payload.get("last_error")),
        )


@dataclass(slots=True, frozen=True)
class BackendConfig:
    kind: str
    model_name: str
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float = 120.0
    temperature: float = 0.2


@dataclass(slots=True, frozen=True)
class RunRequest:
    paper_path: Path
    artifacts_root: Path
    cache_root: Path
    target_count: int | None
    batch_size: int
    backend: BackendConfig
    auto_target_count: bool = False
    min_target_count: int = 6
    max_target_count: int = 24
    restart: bool = False


@dataclass(slots=True, frozen=True)
class DistillRunResult:
    paper_id: str
    artifact_dir: Path
    accepted_count: int
    entries_written: int
    cache_status: CacheStatus
    run_status: RunStatus
    target_count: int = 0


@dataclass(slots=True, frozen=True)
class ExportRequest:
    output_path: Path
    format: ExportFormat
    artifact_dir: Path | None = None
    artifacts_root: Path | None = None


@dataclass(slots=True, frozen=True)
class ExportResult:
    output_path: Path
    format: ExportFormat
    record_count: int


@dataclass(slots=True, frozen=True)
class GeneratedQaCandidate:
    question: str
    answer: str
    evidence_text: str
    evidence_locator: str


@dataclass(slots=True, frozen=True)
class GeneratedConversationTurnCandidate:
    question: str
    answer: str
    evidence_text: str
    evidence_locator: str


@dataclass(slots=True, frozen=True)
class PreparedPrefix:
    cache_key: str
    prefix_hash: str
    backend_kind: str
    backend_ref: str
    cache_status: CacheStatus


def _require_string(payload: dict[str, JSONValue], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Field '{key}' must be a non-empty string.")
    return value


def _require_int(payload: dict[str, JSONValue], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Field '{key}' must be an integer.")
    return value


def _optional_string(value: JSONValue | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional string field must be a string or null.")
    return value


def _require_list_of_strings(payload: dict[str, JSONValue], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Field '{key}' must be a list.")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"Field '{key}' must contain only strings.")
        items.append(item)
    return items
