from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict


RenamePair = tuple[Path, Path]
SkippedPair = tuple[Path, str]
PreviewPair = RenamePair | SkippedPair


class RenamePlan(TypedDict):
    specimen_dirs: list[Path]
    png_count: int
    planned: list[RenamePair]
    skipped: list[SkippedPair]
    conflicts: list[RenamePair]


class CliArgs(argparse.Namespace):
    specimens_root: str = ""
    apply: bool = False
    preview_limit: int = 20


def build_rename_plan(specimens_root: Path) -> RenamePlan:
    specimen_dirs = sorted(path for path in specimens_root.iterdir() if path.is_dir())
    planned: list[RenamePair] = []
    skipped: list[SkippedPair] = []
    conflicts: list[RenamePair] = []
    png_count = 0

    for specimen_dir in specimen_dirs:
        prefix = specimen_dir.name.strip()
        if not prefix:
            continue

        png_files = sorted(
            path for path in specimen_dir.iterdir() if path.is_file() and path.suffix.lower() == ".png"
        )

        for png_path in png_files:
            png_count += 1
            target_path = specimen_dir / f"{prefix}_{png_path.name}"

            if png_path.name == target_path.name:
                skipped.append((png_path, "already-prefixed"))
                continue

            if target_path.exists():
                conflicts.append((png_path, target_path))
                continue

            planned.append((png_path, target_path))

    return {
        "specimen_dirs": specimen_dirs,
        "png_count": png_count,
        "planned": planned,
        "skipped": skipped,
        "conflicts": conflicts,
    }


def print_preview(title: str, pairs: Sequence[PreviewPair], preview_limit: int) -> None:
    if not pairs:
        return

    print(title)
    for src, dst in pairs[:preview_limit]:
        if isinstance(dst, Path):
            print(f"  {src} -> {dst}")
        else:
            print(f"  {src} ({dst})")

    remaining = len(pairs) - min(len(pairs), preview_limit)
    if remaining > 0:
        print(f"  ... and {remaining} more")


def rename_files(planned_pairs: Sequence[RenamePair]) -> int:
    renamed_count = 0
    for src, dst in planned_pairs:
        _ = src.rename(dst)
        renamed_count += 1
    return renamed_count


def parse_args(argv: list[str]) -> CliArgs:
    parser = argparse.ArgumentParser(
        description="Rename specimen PNGs to <folder_name>_<original_view_name>."
    )
    _ = parser.add_argument(
        "specimens_root",
        help="Path to the specimens root directory whose immediate subfolders contain PNG views.",
    )
    _ = parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rename the files. Without this flag, the script only prints a dry-run preview.",
    )
    _ = parser.add_argument(
        "--preview-limit",
        type=int,
        default=20,
        help="How many sample rename mappings to print in the preview output.",
    )
    return parser.parse_args(argv, namespace=CliArgs())


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    specimens_root = Path(args.specimens_root).expanduser()

    if not specimens_root.is_dir():
        print(f"ERROR: specimens root does not exist or is not a directory: {specimens_root}")
        return 1

    plan = build_rename_plan(specimens_root)
    specimen_dir_count = len(plan["specimen_dirs"])
    png_count = plan["png_count"]
    planned = plan["planned"]
    skipped = plan["skipped"]
    conflicts = plan["conflicts"]

    print(f"Specimen folders scanned: {specimen_dir_count}")
    print(f"PNG files found: {png_count}")
    print(f"Rename operations planned: {len(planned)}")
    print(f"Already prefixed / skipped: {len(skipped)}")
    print(f"Conflicts: {len(conflicts)}")

    print_preview("\nSample planned renames:", planned, args.preview_limit)
    print_preview("\nSample skipped files:", skipped, args.preview_limit)
    print_preview("\nSample conflicts:", conflicts, args.preview_limit)

    if conflicts:
        print("\nAbort: resolve conflicts before applying renames.")
        return 1

    if not args.apply:
        print("\nDry run only. Re-run with --apply to perform the renames.")
        return 0

    renamed_count = rename_files(planned)
    print(f"\nDone. Renamed {renamed_count} PNG files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
