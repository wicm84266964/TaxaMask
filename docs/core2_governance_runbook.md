# Core-2 Governance Runbook

This runbook defines the executable governance flow for Core-2 (`lateral` + `dorsal`) and the acceptance checks required before use.

## Scope and Taxonomy

- **Core-2 target views**: `lateral`, `dorsal`
- **Head view role**: `head_frontal` is **non-training** and **non-blocking**; it is monitor-only.
- **Ambiguous routing**: unknown/conflicting signals are routed to `Ambiguous`, never Core-2.

## Policy Snapshot (Authoritative)

Redline thresholds:

- `pass_rate >= 0.95`
- `boundary_overlap >= 0.75`
- `localization_error_px <= 15.0`

Sampling rates:

- `high: 1.0`
- `medium: 0.3`
- `low: 0.1`

Trigger policy:

- consecutive target-view fail runs: `2`
- single-run pass-rate gap trigger: `0.05`

<!-- POLICY_SYNC
pass_rate_min:0.95
boundary_overlap_min:0.75
localization_error_px_max:15.0
review_sampling_high:1.0
review_sampling_medium:0.3
review_sampling_low:0.1
head_view_mode:non_training_non_blocking
-->

## Command Chain (Dry Run)

Run from repository root:

```bash
python tools/governance/build_train_manifest.py --project artifacts/core2/test-head-v2.json --policy AntSleap/config/view_policy_core2.json --out artifacts/core2/train_manifest.json
python tools/governance/build_split_manifest.py --project artifacts/core2/test-head-v2.json --seed 20260306 --out artifacts/core2/split_manifest_run1.json
python tools/governance/check_leakage_groups.py --manifest artifacts/core2/split_manifest_run1.json
python tools/governance/calc_per_view_metrics.py --pred artifacts/core2/predictions.json --gt artifacts/core2/ground_truth.json --out artifacts/core2/per_view_metrics.json
python tools/governance/build_redline_report.py --metrics artifacts/core2/per_view_metrics.json --policy AntSleap/config/view_policy_core2.json --out artifacts/core2/per_view_report.json
python tools/governance/check_sample_sufficiency.py --report artifacts/core2/per_view_report.json --policy AntSleap/config/view_policy_core2.json
python tools/governance/build_headview_monitor.py --metrics artifacts/core2/per_view_metrics.json --out artifacts/core2/head_view_monitor.json
python tools/governance/export_pdf_candidates.py --db ant_literature.db --out artifacts/core2/pdf_candidates_raw.json --mode candidate_only
python tools/governance/build_sampling_plan.py --candidates artifacts/core2/pdf_candidates_raw.json --policy AntSleap/config/view_policy_core2.json --out artifacts/core2/review_sampling_report.json
python tools/governance/route_candidates.py --candidates artifacts/core2/pdf_candidates_raw.json --policy AntSleap/config/view_policy_core2.json --out artifacts/core2/routing_decisions.json
python tools/governance/check_candidate_dedup.py --input artifacts/core2/routing_decisions.json
python tools/governance/eval_locator_trigger.py --history artifacts/core2/redline_history.json --out artifacts/core2/locator_upgrade_trigger.json
python tools/governance/run_acceptance_suite.py --artifacts artifacts/core2 --policy AntSleap/config/view_policy_core2.json --out artifacts/core2/acceptance_summary.json
```

## Acceptance Check → Artifact Map

- `CHK_CONTRACT_V2` → `artifacts/core2/pdf_candidates.json`
- `CHK_SPLIT_DETERMINISM` → `artifacts/core2/split_manifest_run1.json`, `artifacts/core2/split_manifest_run2.json`
- `CHK_HEADVIEW_BLOCK` → `artifacts/core2/train_manifest.json`
- `CHK_REDLINE_TARGET_VIEW` → `artifacts/core2/per_view_report.json`
- `CHK_BRIDGE_MODE` → `artifacts/core2/pdf_candidates_raw.json`
- `CHK_SAMPLING_RATES` → `artifacts/core2/review_sampling_report.json`
- `CHK_IDEMPOTENCY_DEDUP` → `artifacts/core2/routing_decisions.json`

## Interpretation Guide

- `global_pass=true` and `insufficient_evidence=false` means target-view gates are satisfied with enough samples.
- `insufficient_evidence=true` forces `global_pass=false` even if metric thresholds pass.
- `head_view_monitor.status=no_headview_samples` is valid and non-blocking.
- `locator_upgrade_trigger.triggered=true` means upgrade recommendation is issued; it does not auto-switch architecture.
