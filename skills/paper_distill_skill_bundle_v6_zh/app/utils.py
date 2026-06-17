from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def normalize_path_text(path_value: str | Path | None) -> str | None:
    if path_value is None:
        return None

    return str(Path(path_value))


def slugify_text(value: str, fallback: str = "document") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if slug:
        return slug
    return fallback
