import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_migration_callable():
    module_path = os.path.join(
        REPO_ROOT, "AntSleap", "core", "governance", "migration.py"
    )
    spec = importlib.util.spec_from_file_location("migration_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load migration module from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "migrate_project_views")


migrate_project_views = _load_migration_callable()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate legacy project labels to v2 view-enriched artifact."
    )
    parser.add_argument("--input", required=True, help="Input legacy project JSON path.")
    parser.add_argument("--output", required=True, help="Output migrated v2 JSON path.")
    parser.add_argument("--report", required=True, help="Output migration report JSON path.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing output file.",
    )
    args = parser.parse_args()

    report = migrate_project_views(
        input_path=args.input,
        output_path=args.output,
        report_path=args.report,
        overwrite=bool(args.overwrite),
    )

    print("status=ok")
    print(f"schema_version={report.get('schema_version', '')}")
    print(f"total={report.get('total', 0)}")
    print(f"resolved={report.get('resolved', 0)}")
    print(f"unknown={report.get('unknown', 0)}")
    print(f"conflicts={report.get('conflicts', 0)}")
    print(f"totals_match={str(bool(report.get('totals_match', False))).lower()}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print("status=error")
        print(f"message={exc}")
        raise SystemExit(1)
