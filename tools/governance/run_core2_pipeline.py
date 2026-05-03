import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_run_index(path: str, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _run_stage(stage_id: str, command: list[str], cwd: str) -> dict[str, Any]:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    output = (process.stdout or "") + (process.stderr or "")
    return {
        "stage_id": stage_id,
        "command": command,
        "exit_code": int(process.returncode),
        "ok": process.returncode == 0,
        "output": output.strip(),
    }


def _seed_optional_inputs(out_dir: str) -> None:
    optional_files = ["predictions.json", "ground_truth.json", "redline_history.json"]
    for name in optional_files:
        dst = os.path.join(out_dir, name)
        if os.path.exists(dst):
            continue
        src = os.path.join(REPO_ROOT, "artifacts", "core2", name)
        if os.path.exists(src):
            shutil.copy2(src, dst)


def _ensure_contract_candidates(out_dir: str) -> None:
    raw_candidates_path = os.path.join(out_dir, "pdf_candidates_raw.json")
    contract_path = os.path.join(out_dir, "pdf_candidates.json")

    if not os.path.exists(raw_candidates_path):
        return

    with open(raw_candidates_path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)

    candidates = raw.get("candidates", []) if isinstance(raw, dict) else []
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        sample_id = str(candidate.get("candidate_id", "")).strip()
        if not sample_id:
            continue
        records.append(
            {
                "sample_id": sample_id,
                "view": "unknown",
                "source_type": "pdf_extractor_db",
                "source_ref": candidate.get("source_ref", {}),
                "ingestion_run_id": "run-core2-pipeline",
                "label_timestamp": "2026-03-06T12:00:00Z",
                "qa_status": "pending",
                "routing_tier": "candidate",
            }
        )

    contract_payload = {
        "schema_version": "v2",
        "mode": "candidate_only",
        "records": records,
    }
    with open(contract_path, "w", encoding="utf-8") as handle:
        json.dump(contract_payload, handle, ensure_ascii=False, indent=2)


def _inject_failing_redline(out_dir: str) -> None:
    path = os.path.join(out_dir, "per_view_report.json")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload.pop("target_view_reports", None)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end Core-2 governance pipeline.")
    parser.add_argument("--project", required=True, help="Input project JSON path.")
    parser.add_argument("--db", required=True, help="PDF extraction SQLite DB path.")
    parser.add_argument("--policy", required=True, help="Policy JSON path.")
    parser.add_argument("--out", required=True, help="Output artifact directory.")
    parser.add_argument(
        "--inject-failing-redline",
        action="store_true",
        help="Corrupt redline report before acceptance suite for failure-path testing.",
    )
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out)
    _ensure_dir(out_dir)
    _seed_optional_inputs(out_dir)

    run_index_path = os.path.join(out_dir, "run_index.json")
    stages: list[dict[str, Any]] = []

    migrated_project = os.path.join(out_dir, "project_v2.json")
    migration_report = os.path.join(out_dir, "migration_report.json")
    split_run1 = os.path.join(out_dir, "split_manifest_run1.json")
    split_run2 = os.path.join(out_dir, "split_manifest_run2.json")
    train_manifest = os.path.join(out_dir, "train_manifest.json")
    per_view_metrics = os.path.join(out_dir, "per_view_metrics.json")
    per_view_report = os.path.join(out_dir, "per_view_report.json")
    head_monitor = os.path.join(out_dir, "head_view_monitor.json")
    pdf_candidates_raw = os.path.join(out_dir, "pdf_candidates_raw.json")
    review_sampling_report = os.path.join(out_dir, "review_sampling_report.json")
    routing_decisions = os.path.join(out_dir, "routing_decisions.json")
    locator_trigger = os.path.join(out_dir, "locator_upgrade_trigger.json")
    acceptance_summary = os.path.join(out_dir, "acceptance_summary.json")

    predictions_path = os.path.join(out_dir, "predictions.json")
    ground_truth_path = os.path.join(out_dir, "ground_truth.json")
    redline_history_path = os.path.join(out_dir, "redline_history.json")

    stage_commands = [
        (
            "stage_migrate_project",
            [
                sys.executable,
                os.path.join("tools", "governance", "migrate_project_views.py"),
                "--input",
                os.path.abspath(args.project),
                "--output",
                migrated_project,
                "--report",
                migration_report,
                "--overwrite",
            ],
        ),
        (
            "stage_build_train_manifest",
            [
                sys.executable,
                os.path.join("tools", "governance", "build_train_manifest.py"),
                "--project",
                migrated_project,
                "--policy",
                os.path.abspath(args.policy),
                "--out",
                train_manifest,
            ],
        ),
        (
            "stage_build_split_run1",
            [
                sys.executable,
                os.path.join("tools", "governance", "build_split_manifest.py"),
                "--project",
                migrated_project,
                "--seed",
                "20260306",
                "--out",
                split_run1,
            ],
        ),
        (
            "stage_build_split_run2",
            [
                sys.executable,
                os.path.join("tools", "governance", "build_split_manifest.py"),
                "--project",
                migrated_project,
                "--seed",
                "20260306",
                "--out",
                split_run2,
            ],
        ),
        (
            "stage_check_split_determinism",
            [
                sys.executable,
                os.path.join("tools", "governance", "check_split_determinism.py"),
                "--run-a",
                split_run1,
                "--run-b",
                split_run2,
            ],
        ),
        (
            "stage_check_leakage",
            [
                sys.executable,
                os.path.join("tools", "governance", "check_leakage_groups.py"),
                "--manifest",
                split_run1,
            ],
        ),
        (
            "stage_calc_metrics",
            [
                sys.executable,
                os.path.join("tools", "governance", "calc_per_view_metrics.py"),
                "--pred",
                predictions_path,
                "--gt",
                ground_truth_path,
                "--out",
                per_view_metrics,
            ],
        ),
        (
            "stage_build_redline_report",
            [
                sys.executable,
                os.path.join("tools", "governance", "build_redline_report.py"),
                "--metrics",
                per_view_metrics,
                "--policy",
                os.path.abspath(args.policy),
                "--out",
                per_view_report,
            ],
        ),
        (
            "stage_sample_sufficiency",
            [
                sys.executable,
                os.path.join("tools", "governance", "check_sample_sufficiency.py"),
                "--report",
                per_view_report,
                "--policy",
                os.path.abspath(args.policy),
            ],
        ),
        (
            "stage_build_head_monitor",
            [
                sys.executable,
                os.path.join("tools", "governance", "build_headview_monitor.py"),
                "--metrics",
                per_view_metrics,
                "--out",
                head_monitor,
            ],
        ),
        (
            "stage_export_candidates",
            [
                sys.executable,
                os.path.join("tools", "governance", "export_pdf_candidates.py"),
                "--db",
                os.path.abspath(args.db),
                "--out",
                pdf_candidates_raw,
                "--mode",
                "candidate_only",
            ],
        ),
        (
            "stage_build_sampling",
            [
                sys.executable,
                os.path.join("tools", "governance", "build_sampling_plan.py"),
                "--candidates",
                pdf_candidates_raw,
                "--policy",
                os.path.abspath(args.policy),
                "--out",
                review_sampling_report,
            ],
        ),
        (
            "stage_route_candidates",
            [
                sys.executable,
                os.path.join("tools", "governance", "route_candidates.py"),
                "--candidates",
                pdf_candidates_raw,
                "--policy",
                os.path.abspath(args.policy),
                "--out",
                routing_decisions,
            ],
        ),
        (
            "stage_check_candidate_dedup",
            [
                sys.executable,
                os.path.join("tools", "governance", "check_candidate_dedup.py"),
                "--input",
                routing_decisions,
            ],
        ),
        (
            "stage_eval_locator_trigger",
            [
                sys.executable,
                os.path.join("tools", "governance", "eval_locator_trigger.py"),
                "--history",
                redline_history_path,
                "--out",
                locator_trigger,
            ],
        ),
    ]

    failed_stage = ""
    for stage_id, command in stage_commands:
        result = _run_stage(stage_id, command, REPO_ROOT)
        stages.append(result)
        if not bool(result.get("ok", False)):
            failed_stage = stage_id
            break

    if not failed_stage:
        _ensure_contract_candidates(out_dir)

        if args.inject_failing_redline:
            _inject_failing_redline(out_dir)

        acceptance_stage = _run_stage(
            "stage_acceptance_suite",
            [
                sys.executable,
                os.path.join("tools", "governance", "run_acceptance_suite.py"),
                "--artifacts",
                out_dir,
                "--policy",
                os.path.abspath(args.policy),
                "--out",
                acceptance_summary,
            ],
            REPO_ROOT,
        )
        stages.append(acceptance_stage)
        if not bool(acceptance_stage.get("ok", False)):
            failed_stage = "stage_acceptance_suite"

    run_index = {
        "schema_version": "core2-run-index-v1",
        "status": "failed" if failed_stage else "passed",
        "failed_stage": failed_stage or None,
        "project_input": os.path.abspath(args.project),
        "db_input": os.path.abspath(args.db),
        "policy_path": os.path.abspath(args.policy),
        "out_dir": out_dir,
        "stages": stages,
        "artifacts": {
            "migration_report": migration_report,
            "migrated_project": migrated_project,
            "split_manifest_run1": split_run1,
            "split_manifest_run2": split_run2,
            "train_manifest": train_manifest,
            "per_view_metrics": per_view_metrics,
            "per_view_report": per_view_report,
            "head_view_monitor": head_monitor,
            "pdf_candidates_raw": pdf_candidates_raw,
            "pdf_candidates_contract": os.path.join(out_dir, "pdf_candidates.json"),
            "review_sampling_report": review_sampling_report,
            "routing_decisions": routing_decisions,
            "locator_upgrade_trigger": locator_trigger,
            "acceptance_summary": acceptance_summary,
        },
    }
    _write_run_index(run_index_path, run_index)

    print(f"status={run_index['status']}")
    print(f"failed_stage={run_index['failed_stage']}")
    print(f"run_index={run_index_path}")
    return 0 if not failed_stage else 1


if __name__ == "__main__":
    raise SystemExit(main())
