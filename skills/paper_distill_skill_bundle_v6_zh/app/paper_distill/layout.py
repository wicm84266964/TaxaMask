from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.paper_distill.fs import absolute_path
from app.utils import slugify_text


DEFAULT_ARTIFACTS_ROOT = Path("data") / "paper_distill" / "papers"
DEFAULT_CACHE_ROOT = Path("data") / "paper_distill" / "cache"


@dataclass(slots=True, frozen=True)
class PaperPaths:
    artifacts_root: Path
    cache_root: Path
    paper_dir: Path
    qa_entries_path: Path
    conversation_entries_path: Path
    checkpoint_path: Path
    knowledge_map_path: Path
    conversation_plan_path: Path


def normalize_markdown_source(raw_text: str) -> str:
    normalized_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_lines = [line.rstrip() for line in normalized_text.split("\n")]
    trimmed = "\n".join(normalized_lines).strip()
    return f"{trimmed}\n" if trimmed else ""


def build_source_hash(normalized_source: str) -> str:
    digest = hashlib.sha256(normalized_source.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def extract_title(source_path: Path, normalized_source: str) -> str:
    for line in normalized_source.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        title = stripped.lstrip("#").strip()
        if title:
            return title

    fallback = source_path.stem.replace("_", " ").replace("-", " ").strip()
    if fallback:
        return fallback
    return "Untitled Paper"


def build_paper_id(title: str, source_hash: str) -> str:
    digest = source_hash.split(":", 1)[1]
    return f"{slugify_text(title, fallback='paper')}--{digest[:12]}"


def build_paths(*, artifacts_root: Path, cache_root: Path, paper_id: str) -> PaperPaths:
    resolved_artifacts_root = absolute_path(artifacts_root)
    resolved_cache_root = absolute_path(cache_root)
    paper_dir = absolute_path(resolved_artifacts_root / paper_id)
    return PaperPaths(
        artifacts_root=resolved_artifacts_root,
        cache_root=resolved_cache_root,
        paper_dir=paper_dir,
        qa_entries_path=paper_dir / "qa_entries.jsonl",
        conversation_entries_path=paper_dir / "conversation_entries.jsonl",
        checkpoint_path=paper_dir / "checkpoint.json",
        knowledge_map_path=paper_dir / "knowledge_map.json",
        conversation_plan_path=paper_dir / "conversation_plan.json",
    )
