from __future__ import annotations

import json
from pathlib import Path

from app.paper_distill.fs import absolute_path, ensure_safe_file_target, write_text_atomically
from app.paper_distill.layout import build_paths
from app.paper_distill.models import ExportFormat, ExportRequest, ExportResult, QaEntry
from app.paper_distill.store import PaperArtifactStore


class PaperDistillExporter:
    def __init__(self, artifact_store: PaperArtifactStore) -> None:
        self.artifact_store = artifact_store

    def export(self, request: ExportRequest) -> ExportResult:
        if request.format is ExportFormat.CONVERSATION_JSONL:
            records = self._collect_conversation_records(request)
            content = "".join(
                json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
                for record in records
            )
        else:
            records = self._collect_records(request)
            if request.format is ExportFormat.JSONL:
                content = "".join(
                    json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
                    for record in records
                )
            else:
                content = json.dumps(
                    {
                        "schema": "paper_distill_export/v1",
                        "record_count": len(records),
                        "records": records,
                    },
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                ) + "\n"
        write_text_atomically(request.output_path, content)
        return ExportResult(
            output_path=request.output_path,
            format=request.format,
            record_count=len(records),
        )

    def _collect_conversation_records(self, request: ExportRequest) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for artifact_dir in self._artifact_dirs_for(request):
            paths = build_paths(
                artifacts_root=artifact_dir.parent,
                cache_root=Path("."),
                paper_id=artifact_dir.name,
            )
            checkpoint = self.artifact_store.load_checkpoint(paths)
            conversation_entries = self.artifact_store.load_conversation_entries(paths)
            if conversation_entries:
                records.extend(self._conversation_records_from_turn_entries(
                    artifact_dir=artifact_dir,
                    paths=paths,
                    checkpoint=checkpoint,
                ))
                continue

            entries = self.artifact_store.load_entries(paths)
            accepted_entries = [entry for entry in entries if entry.status.value == "accepted"]
            accepted_entries.sort(key=lambda item: (item.ordinal, item.qa_id))
            if not accepted_entries:
                continue

            paper_title = checkpoint.paper_title if checkpoint is not None else artifact_dir.name
            source_hash = checkpoint.source_hash if checkpoint is not None else accepted_entries[0].source_hash
            prompt_version = checkpoint.prompt_version if checkpoint is not None else accepted_entries[-1].prompt_version
            backend_kind = checkpoint.backend_kind if checkpoint is not None else accepted_entries[-1].backend_kind
            model_name = checkpoint.model_name if checkpoint is not None else accepted_entries[-1].model_name
            messages = []
            turns = []
            for entry in accepted_entries:
                messages.append({"role": "user", "content": entry.question})
                messages.append({"role": "assistant", "content": entry.answer})
                turns.append(
                    {
                        "qa_id": entry.qa_id,
                        "ordinal": entry.ordinal,
                        "question": entry.question,
                        "answer": entry.answer,
                        "evidence_text": entry.evidence_text,
                        "evidence_locator": entry.evidence_locator,
                        "created_at": entry.created_at,
                    }
                )
            records.append(
                {
                    "schema": "paper_distill_conversation/v1",
                    "record_type": "conversation",
                    "conversation_id": f"{artifact_dir.name}--full",
                    "paper_id": artifact_dir.name,
                    "paper_title": paper_title,
                    "source_hash": source_hash,
                    "prompt_version": prompt_version,
                    "backend_kind": backend_kind,
                    "model_name": model_name,
                    "turn_count": len(accepted_entries),
                    "messages": messages,
                    "turns": turns,
                }
            )
        return records

    def _conversation_records_from_turn_entries(
        self,
        *,
        artifact_dir: Path,
        paths: object,
        checkpoint: object,
    ) -> list[dict[str, object]]:
        conversation_entries = self.artifact_store.load_conversation_entries(paths)
        conversation_entries.sort(key=lambda item: (item.ordinal, item.turn_id))
        conversation_plan = self.artifact_store.load_conversation_plan(paths)
        plan_threads = {
            thread.thread_id: thread
            for thread in conversation_plan.threads
        } if conversation_plan is not None else {}

        grouped_entries: dict[str, list[object]] = {}
        for entry in conversation_entries:
            grouped_entries.setdefault(entry.thread_id, []).append(entry)

        records: list[dict[str, object]] = []
        for thread_id in sorted(
            grouped_entries,
            key=lambda item: min(entry.ordinal for entry in grouped_entries[item]),
        ):
            thread_entries = grouped_entries[thread_id]
            thread_entries.sort(key=lambda item: (item.thread_turn_index, item.ordinal))
            first_entry = thread_entries[0]
            last_entry = thread_entries[-1]
            thread_plan = plan_threads.get(thread_id)
            messages: list[dict[str, str]] = []
            turns: list[dict[str, object]] = []
            for entry in thread_entries:
                messages.append({"role": "user", "content": entry.question})
                messages.append({"role": "assistant", "content": entry.answer})
                turns.append(
                    {
                        "turn_id": entry.turn_id,
                        "ordinal": entry.ordinal,
                        "thread_turn_index": entry.thread_turn_index,
                        "question": entry.question,
                        "answer": entry.answer,
                        "evidence_text": entry.evidence_text,
                        "evidence_locator": entry.evidence_locator,
                        "created_at": entry.created_at,
                    }
                )
            records.append(
                {
                    "schema": "paper_distill_conversation/v2",
                    "record_type": "conversation",
                    "conversation_id": first_entry.conversation_id,
                    "paper_id": artifact_dir.name,
                    "paper_title": checkpoint.paper_title if checkpoint is not None else artifact_dir.name,
                    "source_hash": checkpoint.source_hash if checkpoint is not None else first_entry.source_hash,
                    "prompt_version": checkpoint.prompt_version if checkpoint is not None else last_entry.prompt_version,
                    "backend_kind": checkpoint.backend_kind if checkpoint is not None else last_entry.backend_kind,
                    "model_name": checkpoint.model_name if checkpoint is not None else last_entry.model_name,
                    "thread_id": thread_id,
                    "thread_topic": first_entry.thread_topic,
                    "planned_turn_budget": thread_plan.turn_budget if thread_plan is not None else len(thread_entries),
                    "start_context": thread_plan.start_context if thread_plan is not None else first_entry.thread_topic,
                    "turn_count": len(thread_entries),
                    "messages": messages,
                    "turns": turns,
                }
            )
        return records

    def _collect_records(self, request: ExportRequest) -> list[dict[str, object]]:
        artifact_dirs = self._artifact_dirs_for(request)
        entries: list[QaEntry] = []
        for artifact_dir in artifact_dirs:
            entries.extend(
                self.artifact_store.load_entries(
                    build_paths(
                        artifacts_root=artifact_dir.parent,
                        cache_root=Path("."),
                        paper_id=artifact_dir.name,
                    )
                )
            )
        accepted_entries = [entry for entry in entries if entry.status.value == "accepted"]
        accepted_entries.sort(key=lambda item: (item.paper_id, item.ordinal, item.qa_id))
        return [
            {
                "paper_id": entry.paper_id,
                "qa_id": entry.qa_id,
                "ordinal": entry.ordinal,
                "question": entry.question,
                "answer": entry.answer,
                "evidence_text": entry.evidence_text,
                "evidence_locator": entry.evidence_locator,
                "source_hash": entry.source_hash,
                "prompt_version": entry.prompt_version,
                "backend_kind": entry.backend_kind,
                "model_name": entry.model_name,
                "created_at": entry.created_at,
            }
            for entry in accepted_entries
        ]

    def _artifact_dirs_for(self, request: ExportRequest) -> list[Path]:
        if request.artifact_dir is not None:
            artifact_dir = absolute_path(request.artifact_dir)
            self._validate_artifact_dir(artifact_dir)
            return [artifact_dir]
        if request.artifacts_root is None:
            raise ValueError("Either artifact_dir or artifacts_root must be provided.")
        root = absolute_path(request.artifacts_root)
        ensure_safe_file_target(root)
        if not root.exists():
            raise ValueError(f"Artifacts root '{root}' does not exist.")
        artifact_dirs = sorted(
            [path for path in root.iterdir() if path.is_dir()],
            key=lambda item: item.name,
        )
        validated_artifact_dirs = [
            artifact_dir for artifact_dir in artifact_dirs if self._is_valid_artifact_dir(artifact_dir)
        ]
        if not validated_artifact_dirs:
            raise ValueError(f"Artifacts root '{root}' does not contain any paper_distill artifacts.")
        return validated_artifact_dirs

    def _validate_artifact_dir(self, artifact_dir: Path) -> None:
        ensure_safe_file_target(artifact_dir)
        if not artifact_dir.exists() or not artifact_dir.is_dir():
            raise ValueError(f"Artifact directory '{artifact_dir}' does not exist.")
        if not self._is_valid_artifact_dir(artifact_dir):
            raise ValueError(
                f"Artifact directory '{artifact_dir}' does not contain qa_entries.jsonl or conversation_entries.jsonl."
            )

    @staticmethod
    def _is_valid_artifact_dir(artifact_dir: Path) -> bool:
        qa_ledger_path = artifact_dir / "qa_entries.jsonl"
        conversation_ledger_path = artifact_dir / "conversation_entries.jsonl"
        ensure_safe_file_target(qa_ledger_path)
        ensure_safe_file_target(conversation_ledger_path)
        return (
            (qa_ledger_path.exists() and qa_ledger_path.is_file())
            or (conversation_ledger_path.exists() and conversation_ledger_path.is_file())
        )
