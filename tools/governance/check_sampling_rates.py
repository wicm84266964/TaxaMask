import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate sampling report rates against policy.")
    parser.add_argument("--report", required=True, help="Sampling report JSON path.")
    parser.add_argument("--policy", required=True, help="Policy JSON path.")
    args = parser.parse_args()

    with open(args.report, "r", encoding="utf-8") as handle:
        report = json.load(handle)
    with open(args.policy, "r", encoding="utf-8") as handle:
        policy = json.load(handle)

    sampling_rates = report.get("sampling_rates", {})
    policy_rates = policy.get("review_sampling", {})
    if not isinstance(sampling_rates, dict) or not isinstance(policy_rates, dict):
        print("sampling_structure_invalid")
        return 1

    for tier in ("high", "medium", "low"):
        report_rate = float(sampling_rates.get(tier, -1))
        policy_rate = float(policy_rates.get(tier, -2))
        print(f"{tier}_rate_report={report_rate}")
        print(f"{tier}_rate_policy={policy_rate}")
        if abs(report_rate - policy_rate) > 1e-9:
            print(f"sampling_rate_mismatch:{tier}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
