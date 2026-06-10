import argparse
import json
import re


def _extract_policy_sync_block(doc_text: str) -> dict[str, str]:
    match = re.search(r"<!--\s*POLICY_SYNC\n(.*?)-->", doc_text, flags=re.DOTALL)
    if not match:
        return {}

    block = match.group(1)
    values: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Check runbook policy snapshot against policy JSON.")
    parser.add_argument("--doc", required=True, help="Runbook markdown path.")
    parser.add_argument("--policy", required=True, help="Policy JSON path.")
    args = parser.parse_args()

    with open(args.doc, "r", encoding="utf-8") as handle:
        doc_text = handle.read()
    with open(args.policy, "r", encoding="utf-8") as handle:
        policy = json.load(handle)

    sync_values = _extract_policy_sync_block(doc_text)
    if not sync_values:
        print("policy_sync_block_missing")
        return 1

    quality = policy.get("quality_gate", {})
    review_sampling = policy.get("review_sampling", {})

    expected = {
        "pass_rate_min": str(float(quality.get("pass_rate_min", -1))),
        "boundary_overlap_min": str(float(quality.get("boundary_overlap_min", -1))),
        "localization_error_px_max": str(float(quality.get("localization_error_px_max", -1))),
        "review_sampling_high": str(float(review_sampling.get("high", -1))),
        "review_sampling_medium": str(float(review_sampling.get("medium", -1))),
        "review_sampling_low": str(float(review_sampling.get("low", -1))),
        "head_view_mode": "non_training_non_blocking",
    }

    mismatches: list[str] = []
    for key, expected_value in expected.items():
        actual_value = sync_values.get(key)
        if actual_value != expected_value:
            mismatches.append(f"{key}:expected={expected_value}:actual={actual_value}")

    if "head_frontal" not in doc_text or "non-training" not in doc_text or "non-blocking" not in doc_text:
        mismatches.append("head_view_statement_missing")

    if mismatches:
        print("docs_policy_mismatch")
        for mismatch in mismatches:
            print(mismatch)
        return 1

    print("docs_policy_sync_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
