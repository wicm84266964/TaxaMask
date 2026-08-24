"""Auditable command-line entry point for TIF storage analysis and cleanup."""

from __future__ import annotations

import argparse
import json

from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_storage_lifecycle import TifStorageLifecycleManager


def _load_manager(project_path):
    manager = TifProjectManager()
    manager.load_project(project_path)
    if not manager.is_sqlite_project():
        raise ValueError("tif_storage_manager_requires_sqlite_project")
    return manager


def _print_result(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def run(args):
    manager = _load_manager(args.project)
    lifecycle = TifStorageLifecycleManager(manager)
    if args.command == "analyze":
        result = lifecycle.analyze(
            verify_duplicate_content=bool(args.verify_duplicate_content)
        )
    elif args.command == "plan":
        result = lifecycle.create_cleanup_plan()
    elif args.command == "list-plans":
        result = {
            "plans": lifecycle.list_cleanup_plans(
                states=args.state or None,
                limit=args.limit,
            )
        }
    elif args.command == "pin":
        result = {
            "pin_id": lifecycle.pin(
                args.target_kind,
                args.target_id,
                args.reason,
                pinned_by=args.pinned_by,
            )
        }
    elif args.command == "unpin":
        result = {"released": lifecycle.unpin(args.pin_id)}
    elif args.command == "quarantine":
        result = lifecycle.quarantine(args.plan_id, grace_days=args.grace_days)
    elif args.command == "restore":
        result = lifecycle.restore(args.plan_id)
    elif args.command == "purge":
        result = lifecycle.purge(
            args.plan_id,
            confirmation=args.confirm,
            override_grace_period=args.override_grace_period,
        )
    else:
        raise ValueError(f"unsupported_storage_command:{args.command}")
    _print_result(result)
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyze TIF storage and manage recoverable cache cleanup."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Path to the TIF SQLite project manifest JSON.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Write a read-only inventory.")
    analyze.add_argument("--verify-duplicate-content", action="store_true")

    subparsers.add_parser("plan", help="Create a dry-run cleanup plan.")
    list_plans = subparsers.add_parser(
        "list-plans", help="List persisted cleanup plans for recovery or audit."
    )
    list_plans.add_argument("--state", action="append", default=[])
    list_plans.add_argument("--limit", type=int, default=100)

    pin = subparsers.add_parser("pin", help="Protect a cache key or materialization.")
    pin.add_argument("target_kind", choices=("cache_key", "materialization"))
    pin.add_argument("target_id")
    pin.add_argument("reason")
    pin.add_argument("--pinned-by", default="")

    unpin = subparsers.add_parser("unpin", help="Release an existing retention pin.")
    unpin.add_argument("pin_id")

    quarantine = subparsers.add_parser(
        "quarantine", help="Move eligible plan items into recoverable quarantine."
    )
    quarantine.add_argument("plan_id")
    quarantine.add_argument("--grace-days", type=int, default=7)

    restore = subparsers.add_parser(
        "restore", help="Restore every quarantined item in a plan."
    )
    restore.add_argument("plan_id")

    purge = subparsers.add_parser(
        "purge", help="Delete a quarantined plan after its grace period."
    )
    purge.add_argument("plan_id")
    purge.add_argument(
        "--confirm",
        required=True,
        help="Must exactly equal plan_id; deletion remains blocked during grace period.",
    )
    purge.add_argument(
        "--override-grace-period",
        action="store_true",
        help=(
            "Allow irreversible deletion before the grace deadline after the project "
            "has been validated; the override is recorded in the cleanup audit log."
        ),
    )
    return parser.parse_args(argv)


def main(argv=None):
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
