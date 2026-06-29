"""Core package compatibility helpers."""

from pathlib import Path


if __name__ == "core":
    legacy_core = Path(__file__).resolve().parents[2] / "core"
    if legacy_core.is_dir():
        legacy_text = str(legacy_core)
        if legacy_text not in __path__:
            __path__.append(legacy_text)
