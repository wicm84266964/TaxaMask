import argparse
import hashlib
import json


def _membership_hash(payload: dict[str, object]) -> str:
    train = payload.get("train", [])
    val = payload.get("val", [])

    parts: list[str] = []
    if isinstance(train, list):
        for item in train:
            if isinstance(item, dict):
                sample_id = item.get("sample_id")
                if isinstance(sample_id, str):
                    parts.append(f"train|{sample_id}")
    if isinstance(val, list):
        for item in val:
            if isinstance(item, dict):
                sample_id = item.get("sample_id")
                if isinstance(sample_id, str):
                    parts.append(f"val|{sample_id}")

    return hashlib.sha256("\n".join(sorted(parts)).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check deterministic split membership across two manifests.")
    parser.add_argument("--run-a", required=True, help="First split manifest JSON path.")
    parser.add_argument("--run-b", required=True, help="Second split manifest JSON path.")
    args = parser.parse_args()

    with open(args.run_a, "r", encoding="utf-8") as handle:
        run_a = json.load(handle)
    with open(args.run_b, "r", encoding="utf-8") as handle:
        run_b = json.load(handle)

    hash_a = str(run_a.get("membership_fingerprint", "")) or _membership_hash(run_a)
    hash_b = str(run_b.get("membership_fingerprint", "")) or _membership_hash(run_b)

    print(f"hash_a={hash_a}")
    print(f"hash_b={hash_b}")
    print(f"hash_equal={str(hash_a == hash_b).lower()}")

    if hash_a != hash_b:
        print("split_hash_mismatch")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
