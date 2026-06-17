from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from app.paper_distill.fs import absolute_path, ensure_safe_file_target, write_text_atomically
from app.paper_distill.models import CacheRecord
from app.types import JSONValue


def build_cache_key(
    *,
    source_hash: str,
    prompt_version: str,
    backend_identity: str,
) -> str:
    raw_key = "|".join((source_hash, prompt_version, backend_identity))
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def build_prefix_hash(prefix_text: str) -> str:
    return hashlib.sha256(prefix_text.encode("utf-8")).hexdigest()


class CacheMetadataStore:
    def __init__(self, root_path: Path) -> None:
        self.root_path = absolute_path(root_path)

    def load(self, cache_key: str) -> CacheRecord | None:
        path = self._path_for(cache_key)
        ensure_safe_file_target(path)
        if not path.exists():
            return None
        raw_content = path.read_text(encoding="utf-8").strip()
        if not raw_content:
            return None
        decoded = cast(object, json.loads(raw_content))
        if not isinstance(decoded, dict):
            raise ValueError("Cache metadata must decode to a dictionary.")
        return CacheRecord.from_dict(cast(dict[str, JSONValue], decoded))

    def save(self, record: CacheRecord) -> None:
        path = self._path_for(record.cache_key)
        content = json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n"
        write_text_atomically(path, content)

    def _path_for(self, cache_key: str) -> Path:
        return self.root_path / f"{cache_key}.json"
