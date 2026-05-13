from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PopplerStatus:
    found: bool
    source: str
    bin_path: str
    pdfinfo_path: str
    pdftoppm_path: str
    message: str


def _exe(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def _has_poppler_tools(directory: Path) -> tuple[str, str] | None:
    pdfinfo = directory / _exe("pdfinfo")
    pdftoppm = directory / _exe("pdftoppm")
    if pdfinfo.exists() and pdftoppm.exists():
        return str(pdfinfo), str(pdftoppm)
    return None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def candidate_poppler_dirs(user_path: str | os.PathLike[str] | None = None, repo_root: str | os.PathLike[str] | None = None) -> list[tuple[str, Path]]:
    root = Path(repo_root) if repo_root is not None else _repo_root()
    candidates: list[tuple[str, Path]] = []

    if user_path:
        raw = Path(user_path).expanduser()
        candidates.extend(
            [
                ("configured", raw),
                ("configured", raw / "bin"),
                ("configured", raw / "Library" / "bin"),
            ]
        )

    candidates.extend(
        [
            ("bundled", root / "external_tools" / "poppler" / "Library" / "bin"),
            ("bundled", root / "external_tools" / "poppler" / "bin"),
            ("bundled", root / "external_tools" / "poppler"),
        ]
    )
    if repo_root is None:
        candidates.extend(
            [
                ("relative", Path("external_tools") / "poppler" / "Library" / "bin"),
                ("relative", Path("external_tools") / "poppler" / "bin"),
            ]
        )
    return candidates


def discover_poppler(user_path: str | os.PathLike[str] | None = None, repo_root: str | os.PathLike[str] | None = None) -> PopplerStatus:
    for source, directory in candidate_poppler_dirs(user_path=user_path, repo_root=repo_root):
        tools = _has_poppler_tools(directory)
        if tools is None:
            continue
        pdfinfo, pdftoppm = tools
        return PopplerStatus(
            found=True,
            source=source,
            bin_path=str(directory),
            pdfinfo_path=pdfinfo,
            pdftoppm_path=pdftoppm,
            message=f"Poppler found via {source}: {directory}",
        )

    pdfinfo = shutil.which("pdfinfo")
    pdftoppm = shutil.which("pdftoppm")
    if pdfinfo and pdftoppm:
        return PopplerStatus(
            found=True,
            source="PATH",
            bin_path=str(Path(pdfinfo).parent),
            pdfinfo_path=pdfinfo,
            pdftoppm_path=pdftoppm,
            message=f"Poppler found on PATH: {Path(pdfinfo).parent}",
        )

    return PopplerStatus(
        found=False,
        source="missing",
        bin_path="",
        pdfinfo_path="",
        pdftoppm_path="",
        message=(
            "Poppler was not found. PyMuPDF-based figure extraction can still run, "
            "but pdf2image/OCR fallback may be unavailable."
        ),
    )


def poppler_path_for_pdf2image(user_path: str | os.PathLike[str] | None = None) -> str | None:
    status = discover_poppler(user_path=user_path)
    if not status.found:
        return None
    return status.bin_path if status.source != "PATH" else None
