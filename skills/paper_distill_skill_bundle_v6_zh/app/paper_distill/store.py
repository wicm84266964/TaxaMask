from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from app.paper_distill.fs import absolute_path, ensure_safe_file_target, write_text_atomically
from app.paper_distill.layout import PaperPaths
from app.paper_distill.models import (
    Checkpoint,
    ConversationPlan,
    ConversationTurnEntry,
    KnowledgeMap,
    QaEntry,
)
from app.types import JSONValue


class PaperArtifactStore:
    def __init__(self, artifacts_root: Path) -> None:
        self.artifacts_root = absolute_path(artifacts_root)

    def load_entries(self, paths: PaperPaths) -> list[QaEntry]:
        ensure_safe_file_target(paths.qa_entries_path)
        if not paths.qa_entries_path.exists():
            return []

        entries: list[QaEntry] = []
        with paths.qa_entries_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    raw_entry = cast(object, json.loads(stripped))
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"QA ledger row {line_number} is not valid JSON: {error.msg}."
                    ) from error
                if not isinstance(raw_entry, dict):
                    raise ValueError(
                        f"QA ledger row {line_number} must decode to a dictionary."
                    )
                entries.append(QaEntry.from_dict(cast(dict[str, JSONValue], raw_entry)))
        return sorted(entries, key=lambda item: (item.ordinal, item.qa_id))

    def append_entries(self, paths: PaperPaths, entries: list[QaEntry]) -> None:
        if not entries:
            return
        self._ensure_paper_dir(paths)
        ensure_safe_file_target(paths.qa_entries_path)
        existing_lines = []
        if paths.qa_entries_path.exists():
            existing_lines = paths.qa_entries_path.read_text(encoding="utf-8").splitlines()
        new_lines = [
            json.dumps(entry.to_dict(), sort_keys=True, ensure_ascii=False)
            for entry in entries
        ]
        combined_lines = [line for line in existing_lines if line.strip()] + new_lines
        content = "\n".join(combined_lines) + "\n"
        write_text_atomically(paths.qa_entries_path, content)

    def load_conversation_entries(self, paths: PaperPaths) -> list[ConversationTurnEntry]:
        ensure_safe_file_target(paths.conversation_entries_path)
        if not paths.conversation_entries_path.exists():
            return []

        entries: list[ConversationTurnEntry] = []
        with paths.conversation_entries_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    raw_entry = cast(object, json.loads(stripped))
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Conversation ledger row {line_number} is not valid JSON: {error.msg}."
                    ) from error
                if not isinstance(raw_entry, dict):
                    raise ValueError(
                        f"Conversation ledger row {line_number} must decode to a dictionary."
                    )
                entries.append(
                    ConversationTurnEntry.from_dict(cast(dict[str, JSONValue], raw_entry))
                )
        return sorted(entries, key=lambda item: (item.ordinal, item.turn_id))

    def append_conversation_entries(
        self,
        paths: PaperPaths,
        entries: list[ConversationTurnEntry],
    ) -> None:
        if not entries:
            return
        self._ensure_paper_dir(paths)
        ensure_safe_file_target(paths.conversation_entries_path)
        existing_lines = []
        if paths.conversation_entries_path.exists():
            existing_lines = paths.conversation_entries_path.read_text(encoding="utf-8").splitlines()
        new_lines = [
            json.dumps(entry.to_dict(), sort_keys=True, ensure_ascii=False)
            for entry in entries
        ]
        combined_lines = [line for line in existing_lines if line.strip()] + new_lines
        content = "\n".join(combined_lines) + "\n"
        write_text_atomically(paths.conversation_entries_path, content)

    def load_checkpoint(self, paths: PaperPaths) -> Checkpoint | None:
        ensure_safe_file_target(paths.checkpoint_path)
        if not paths.checkpoint_path.exists():
            return None
        raw_content = paths.checkpoint_path.read_text(encoding="utf-8").strip()
        if not raw_content:
            return None
        decoded = cast(object, json.loads(raw_content))
        if not isinstance(decoded, dict):
            raise ValueError("Checkpoint must decode to a dictionary.")
        return Checkpoint.from_dict(cast(dict[str, JSONValue], decoded))

    def save_checkpoint(self, paths: PaperPaths, checkpoint: Checkpoint) -> None:
        self._ensure_paper_dir(paths)
        content = json.dumps(checkpoint.to_dict(), indent=2, sort_keys=True) + "\n"
        write_text_atomically(paths.checkpoint_path, content)

    def load_knowledge_map(self, paths: PaperPaths) -> KnowledgeMap | None:
        ensure_safe_file_target(paths.knowledge_map_path)
        if not paths.knowledge_map_path.exists():
            return None
        raw_content = paths.knowledge_map_path.read_text(encoding="utf-8").strip()
        if not raw_content:
            return None
        decoded = cast(object, json.loads(raw_content))
        if not isinstance(decoded, dict):
            raise ValueError("Knowledge map must decode to a dictionary.")
        return KnowledgeMap.from_dict(cast(dict[str, JSONValue], decoded))

    def save_knowledge_map(self, paths: PaperPaths, knowledge_map: KnowledgeMap) -> None:
        self._ensure_paper_dir(paths)
        content = json.dumps(knowledge_map.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        write_text_atomically(paths.knowledge_map_path, content)

    def load_conversation_plan(self, paths: PaperPaths) -> ConversationPlan | None:
        ensure_safe_file_target(paths.conversation_plan_path)
        if not paths.conversation_plan_path.exists():
            return None
        raw_content = paths.conversation_plan_path.read_text(encoding="utf-8").strip()
        if not raw_content:
            return None
        decoded = cast(object, json.loads(raw_content))
        if not isinstance(decoded, dict):
            raise ValueError("Conversation plan must decode to a dictionary.")
        return ConversationPlan.from_dict(cast(dict[str, JSONValue], decoded))

    def save_conversation_plan(self, paths: PaperPaths, conversation_plan: ConversationPlan) -> None:
        self._ensure_paper_dir(paths)
        content = json.dumps(
            conversation_plan.to_dict(),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n"
        write_text_atomically(paths.conversation_plan_path, content)

    def clear_artifact(self, paths: PaperPaths) -> None:
        ensure_safe_file_target(paths.qa_entries_path)
        ensure_safe_file_target(paths.conversation_entries_path)
        ensure_safe_file_target(paths.checkpoint_path)
        ensure_safe_file_target(paths.knowledge_map_path)
        ensure_safe_file_target(paths.conversation_plan_path)
        if paths.qa_entries_path.exists():
            _ = paths.qa_entries_path.unlink()
        if paths.conversation_entries_path.exists():
            _ = paths.conversation_entries_path.unlink()
        if paths.checkpoint_path.exists():
            _ = paths.checkpoint_path.unlink()
        if paths.knowledge_map_path.exists():
            _ = paths.knowledge_map_path.unlink()
        if paths.conversation_plan_path.exists():
            _ = paths.conversation_plan_path.unlink()

    def _ensure_paper_dir(self, paths: PaperPaths) -> None:
        ensure_safe_file_target(paths.paper_dir)
        paths.paper_dir.mkdir(parents=True, exist_ok=True)
