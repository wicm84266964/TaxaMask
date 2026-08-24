"""Versioned SAM decoder checkpoint contract."""

from __future__ import annotations


SAM_DECODER_CHECKPOINT_SCHEMA_VERSION = "taxamask_sam_decoder_checkpoint_v2"
SAM_DECODER_ARCHITECTURE_ID = "sam_mask_decoder_v1"
FINGERPRINT_FIELDS = (
    "entry_kind",
    "size_bytes",
    "hash_algorithm",
    "digest",
)


def normalize_base_sam_fingerprint(value, *, error_prefix="sam_decoder"):
    payload = value if isinstance(value, dict) else {}
    size_bytes = payload.get("size_bytes")
    digest = str(payload.get("digest") or "").lower()
    fingerprint = {
        "entry_kind": payload.get("entry_kind"),
        "size_bytes": size_bytes,
        "hash_algorithm": str(payload.get("hash_algorithm") or "").lower(),
        "digest": digest,
    }
    if (
        fingerprint["entry_kind"] != "file"
        or not isinstance(size_bytes, int)
        or isinstance(size_bytes, bool)
        or size_bytes <= 0
        or fingerprint["hash_algorithm"] != "sha256"
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{error_prefix}_base_sam_fingerprint_invalid")
    return fingerprint


def build_sam_decoder_checkpoint(state_dict, base_sam_fingerprint):
    return {
        "schema_version": SAM_DECODER_CHECKPOINT_SCHEMA_VERSION,
        "state_dict": state_dict,
        "meta": {
            "architecture_id": SAM_DECODER_ARCHITECTURE_ID,
            "base_sam": normalize_base_sam_fingerprint(
                base_sam_fingerprint,
                error_prefix="sam_decoder_checkpoint",
            ),
        },
    }


def parse_sam_decoder_checkpoint(saved_payload, *, require_bound_base=False):
    if (
        isinstance(saved_payload, dict)
        and saved_payload.get("schema_version")
        == SAM_DECODER_CHECKPOINT_SCHEMA_VERSION
    ):
        meta = saved_payload.get("meta")
        if (
            not isinstance(meta, dict)
            or meta.get("architecture_id") != SAM_DECODER_ARCHITECTURE_ID
        ):
            raise ValueError("sam_decoder_checkpoint_meta_invalid")
        state_dict = saved_payload.get("state_dict")
        base_sam = normalize_base_sam_fingerprint(
            meta.get("base_sam"),
            error_prefix="sam_decoder_checkpoint",
        )
        return {
            "schema_version": SAM_DECODER_CHECKPOINT_SCHEMA_VERSION,
            "state_dict": state_dict,
            "base_sam": base_sam,
        }

    if require_bound_base:
        raise ValueError("sam_decoder_checkpoint_base_binding_missing")
    state_dict = (
        saved_payload.get("state_dict")
        if isinstance(saved_payload, dict) and "state_dict" in saved_payload
        else saved_payload
    )
    return {
        "schema_version": "",
        "state_dict": state_dict,
        "base_sam": None,
    }


def require_matching_base_sam(*fingerprints):
    normalized = [
        normalize_base_sam_fingerprint(
            item,
            error_prefix="sam_decoder_runtime",
        )
        for item in fingerprints
        if item is not None
    ]
    if not normalized:
        raise ValueError("sam_decoder_runtime_base_sam_fingerprint_missing")
    first = normalized[0]
    if any(item != first for item in normalized[1:]):
        raise ValueError("sam_decoder_runtime_base_sam_mismatch")
    return first
