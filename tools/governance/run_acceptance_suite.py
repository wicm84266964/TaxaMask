import argparse
import json
import os
import subprocess
import sys
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _run_check(check_id: str, command: list[str]) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    output = (process.stdout or "") + (process.stderr or "")
    return {
        "check_id": check_id,
        "passed": process.returncode == 0,
        "exit_code": int(process.returncode),
        "command": command,
        "output": output.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Core-2 governance acceptance suite.")
    parser.add_argument("--artifacts", required=True, help="Artifacts directory path.")
    parser.add_argument("--policy", required=True, help="Policy JSON path.")
    parser.add_argument("--out", required=True, help="Output acceptance summary JSON path.")
    args = parser.parse_args()

    artifacts_dir = os.path.abspath(args.artifacts)
    policy_path = os.path.abspath(args.policy)

    checks: list[tuple[str, list[str]]] = [
        (
            "CHK_CONTRACT_V2",
            [
                sys.executable,
                os.path.join("tools", "governance", "validate_contract.py"),
                "--input",
                os.path.join(artifacts_dir, "pdf_candidates.json"),
            ],
        ),
        (
            "CHK_SPLIT_DETERMINISM",
            [
                sys.executable,
                os.path.join("tools", "governance", "check_split_determinism.py"),
                "--run-a",
                os.path.join(artifacts_dir, "split_manifest_run1.json"),
                "--run-b",
                os.path.join(artifacts_dir, "split_manifest_run2.json"),
            ],
        ),
        (
            "CHK_HEADVIEW_BLOCK",
            [
                sys.executable,
                os.path.join("tools", "governance", "check_headview_block.py"),
                "--manifest",
                os.path.join(artifacts_dir, "train_manifest.json"),
            ],
        ),
        (
            "CHK_REDLINE_TARGET_VIEW",
            [
                sys.executable,
                os.path.join("tools", "governance", "check_redline_report.py"),
                "--report",
                os.path.join(artifacts_dir, "per_view_report.json"),
            ],
        ),
        (
            "CHK_BRIDGE_MODE",
            [
                sys.executable,
                os.path.join("tools", "governance", "check_bridge_mode.py"),
                "--candidates",
                os.path.join(artifacts_dir, "pdf_candidates.json"),
                "--expect-mode",
                "candidate_only",
            ],
        ),
        (
            "CHK_SAMPLING_RATES",
            [
                sys.executable,
                os.path.join("tools", "governance", "check_sampling_rates.py"),
                "--report",
                os.path.join(artifacts_dir, "review_sampling_report.json"),
                "--policy",
                policy_path,
            ],
        ),
        (
            "CHK_IDEMPOTENCY_DEDUP",
            [
                sys.executable,
                os.path.join("tools", "governance", "check_candidate_dedup.py"),
                "--input",
                os.path.join(artifacts_dir, "routing_decisions.json"),
            ],
        ),
    ]

    results = [_run_check(check_id, command) for check_id, command in checks]
    all_pass = all(bool(item.get("passed")) for item in results)
    failing_ids = [str(item.get("check_id")) for item in results if not bool(item.get("passed"))]

    summary = {
        "schema_version": "core2-acceptance-v1",
        "artifacts_dir": artifacts_dir,
        "policy_path": policy_path,
        "all_pass": all_pass,
        "failing_check_ids": failing_ids,
        "checks": results,
    }

    _ensure_parent(args.out)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    print(f"all_pass={str(all_pass).lower()}")
    print(f"check_count={len(results)}")
    if failing_ids:
        print("failing_checks=" + ",".join(failing_ids))

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
