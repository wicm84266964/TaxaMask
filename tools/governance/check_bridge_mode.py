import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate candidate bridge mode.")
    parser.add_argument("--candidates", required=True, help="Candidate artifact JSON path.")
    parser.add_argument("--expect-mode", required=True, help="Expected bridge mode.")
    args = parser.parse_args()

    with open(args.candidates, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    mode = str(payload.get("mode", ""))
    print(f"mode={mode}")
    print(f"expected_mode={args.expect_mode}")

    if mode != args.expect_mode:
        print("bridge_mode_invalid")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
