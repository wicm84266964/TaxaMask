from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app.paper_distill.backends import (
    _decode_candidate_items,
    build_backend,
    build_backend_identity,
)
from app.paper_distill.cache import CacheMetadataStore, build_cache_key


class PaperDistillBackendTests(unittest.TestCase):
    def test_mock_backend_reuses_prepared_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_store = CacheMetadataStore(Path(temporary_directory) / "cache")
            backend = build_backend(
                backend_kind="mock",
                cache_store=cache_store,
                model_name="mock-model",
            )

            first = backend.prepare_prefix(
                cache_key="cache-key",
                backend_identity="kind=mock|model=mock-model",
                prefix_hash="prefix-hash",
                paper_id="paper-1",
                source_hash="sha256:abc",
                prompt_version="v1",
            )
            second = backend.prepare_prefix(
                cache_key="cache-key",
                backend_identity="kind=mock|model=mock-model",
                prefix_hash="prefix-hash",
                paper_id="paper-1",
                source_hash="sha256:abc",
                prompt_version="v1",
            )
            generated = backend.generate_batch(
                prefix_text="[[SOURCE_MARKDOWN]]\n# Paper\n\n## Method\n\nA focused method section.\n",
                suffix_text="{}",
                prepared_prefix=second,
                next_ordinal=1,
                batch_size=2,
            )

            self.assertEqual(first.cache_status.value, "created")
            self.assertEqual(second.cache_status.value, "reused")
            self.assertEqual(len(generated), 2)
            self.assertIn("core point #1", generated[0].question)

    def test_openai_compatible_backend_rejects_insecure_non_localhost_http(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_store = CacheMetadataStore(Path(temporary_directory) / "cache")
            with self.assertRaisesRegex(ValueError, "must use https unless it targets localhost"):
                _ = build_backend(
                    backend_kind="openai-compatible",
                    cache_store=cache_store,
                    model_name="mock-model",
                    base_url="http://example.com/v1",
                    api_key="test-key",
                )

            localhost_backend = build_backend(
                backend_kind="openai-compatible",
                cache_store=cache_store,
                model_name="mock-model",
                base_url="http://127.0.0.1:8000/v1",
                api_key="test-key",
            )
            self.assertEqual(localhost_backend.kind, "openai-compatible")

    def test_openai_compatible_backend_identity_changes_cache_key(self) -> None:
        backend_identity_a = build_backend_identity(
            backend_kind="openai-compatible",
            model_name="model-a",
            base_url="https://provider-a.example/v1",
            temperature=0.2,
        )
        backend_identity_b = build_backend_identity(
            backend_kind="openai-compatible",
            model_name="model-a",
            base_url="https://provider-b.example/v1",
            temperature=0.2,
        )

        cache_key_a = build_cache_key(
            source_hash="sha256:abc",
            prompt_version="v1",
            backend_identity=backend_identity_a,
        )
        cache_key_b = build_cache_key(
            source_hash="sha256:abc",
            prompt_version="v1",
            backend_identity=backend_identity_b,
        )

        self.assertNotEqual(backend_identity_a, backend_identity_b)
        self.assertNotEqual(cache_key_a, cache_key_b)

    def test_decode_candidate_items_accepts_bare_array_payload(self) -> None:
        candidates = _decode_candidate_items(
            '[{"question":"q","answer":"a","evidence_text":"e","evidence_locator":"l"}]'
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].question, "q")
        self.assertEqual(candidates[0].answer, "a")

    def test_openai_compatible_backend_retries_gateway_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_store = CacheMetadataStore(Path(temporary_directory) / "cache")
            backend = build_backend(
                backend_kind="openai-compatible",
                cache_store=cache_store,
                model_name="mock-model",
                base_url="https://provider.example/v1",
                api_key="test-key",
            )

            request = httpx.Request("POST", "https://provider.example/v1/chat/completions")
            responses = [
                httpx.Response(504, request=request, json={"error": {"message": "timeout"}}),
                httpx.Response(
                    200,
                    request=request,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "study_goal": "Goal",
                                            "study_object": "Object",
                                            "experimental_design": "Design",
                                            "content_profile": "body_available",
                                            "primary_language": "en",
                                            "sections_present": ["Method"],
                                            "treatments_or_conditions": ["Condition"],
                                            "core_metrics": ["Metric"],
                                            "key_findings": ["Finding"],
                                            "limitations": [],
                                            "recommendations": [],
                                        }
                                    )
                                }
                            }
                        ]
                    },
                ),
            ]

            class _FakeClient:
                def __init__(self, *args: object, **kwargs: object) -> None:
                    _ = args
                    _ = kwargs

                def __enter__(self) -> "_FakeClient":
                    return self

                def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
                    _ = exc_type
                    _ = exc
                    _ = tb
                    return False

                def post(self, *args: object, **kwargs: object) -> httpx.Response:
                    _ = args
                    _ = kwargs
                    return responses.pop(0)

            with patch("app.paper_distill.backends.httpx.Client", _FakeClient), patch(
                "app.paper_distill.backends.time.sleep", return_value=None
            ):
                payload = backend.generate_json_object(
                    prefix_text="Title: Paper\n[[SOURCE_MARKDOWN]]\nBody",
                    suffix_text="{}",
                    prepared_prefix=backend.prepare_prefix(
                        cache_key="cache-key",
                        backend_identity="kind=openai-compatible|model=mock-model|base_url=https://provider.example/v1|temperature=0.200000",
                        prefix_hash="prefix-hash",
                        paper_id="paper-1",
                        source_hash="sha256:abc",
                        prompt_version="v1",
                    ),
                )

            self.assertEqual(payload["study_goal"], "Goal")
            self.assertEqual(len(responses), 0)

    def test_openai_compatible_backend_retries_invalid_model_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_store = CacheMetadataStore(Path(temporary_directory) / "cache")
            backend = build_backend(
                backend_kind="openai-compatible",
                cache_store=cache_store,
                model_name="mock-model",
                base_url="https://provider.example/v1",
                api_key="test-key",
            )

            request = httpx.Request("POST", "https://provider.example/v1/chat/completions")
            responses = [
                httpx.Response(
                    200,
                    request=request,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": '{"study_goal" "broken"}'
                                }
                            }
                        ]
                    },
                ),
                httpx.Response(
                    200,
                    request=request,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "study_goal": "Goal",
                                            "study_object": "Object",
                                            "experimental_design": "Design",
                                            "content_profile": "body_available",
                                            "primary_language": "en",
                                            "sections_present": ["Method"],
                                            "treatments_or_conditions": ["Condition"],
                                            "core_metrics": ["Metric"],
                                            "key_findings": ["Finding"],
                                            "limitations": [],
                                            "recommendations": [],
                                        }
                                    )
                                }
                            }
                        ]
                    },
                ),
            ]

            class _FakeClient:
                def __init__(self, *args: object, **kwargs: object) -> None:
                    _ = args
                    _ = kwargs

                def __enter__(self) -> "_FakeClient":
                    return self

                def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
                    _ = exc_type
                    _ = exc
                    _ = tb
                    return False

                def post(self, *args: object, **kwargs: object) -> httpx.Response:
                    _ = args
                    _ = kwargs
                    return responses.pop(0)

            with patch("app.paper_distill.backends.httpx.Client", _FakeClient), patch(
                "app.paper_distill.backends.time.sleep", return_value=None
            ):
                payload = backend.generate_json_object(
                    prefix_text="Title: Paper\n[[SOURCE_MARKDOWN]]\nBody",
                    suffix_text="{}",
                    prepared_prefix=backend.prepare_prefix(
                        cache_key="cache-key",
                        backend_identity="kind=openai-compatible|model=mock-model|base_url=https://provider.example/v1|temperature=0.200000",
                        prefix_hash="prefix-hash",
                        paper_id="paper-1",
                        source_hash="sha256:abc",
                        prompt_version="v1",
                    ),
                )

            self.assertEqual(payload["study_goal"], "Goal")
            self.assertEqual(len(responses), 0)

    def test_openai_compatible_backend_repairs_fenced_json_with_trailing_commas(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_store = CacheMetadataStore(Path(temporary_directory) / "cache")
            backend = build_backend(
                backend_kind="openai-compatible",
                cache_store=cache_store,
                model_name="mock-model",
                base_url="https://provider.example/v1",
                api_key="test-key",
            )

            request = httpx.Request("POST", "https://provider.example/v1/chat/completions")
            responses = [
                httpx.Response(
                    200,
                    request=request,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        "```json\n"
                                        "{\n"
                                        '  "study_goal": "Goal",\n'
                                        '  "study_object": "Object",\n'
                                        '  "experimental_design": "Design",\n'
                                        '  "content_profile": "body_available",\n'
                                        '  "primary_language": "en",\n'
                                        '  "sections_present": ["Method"],\n'
                                        '  "treatments_or_conditions": ["Condition"],\n'
                                        '  "core_metrics": ["Metric"],\n'
                                        '  "key_findings": ["Finding"],\n'
                                        '  "limitations": [],\n'
                                        '  "recommendations": [],\n'
                                        "}\n"
                                        "```"
                                    )
                                }
                            }
                        ]
                    },
                ),
            ]

            class _FakeClient:
                def __init__(self, *args: object, **kwargs: object) -> None:
                    _ = args
                    _ = kwargs

                def __enter__(self) -> "_FakeClient":
                    return self

                def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
                    _ = exc_type
                    _ = exc
                    _ = tb
                    return False

                def post(self, *args: object, **kwargs: object) -> httpx.Response:
                    _ = args
                    _ = kwargs
                    return responses.pop(0)

            with patch("app.paper_distill.backends.httpx.Client", _FakeClient):
                payload = backend.generate_json_object(
                    prefix_text="Title: Paper\n[[SOURCE_MARKDOWN]]\nBody",
                    suffix_text="{}",
                    prepared_prefix=backend.prepare_prefix(
                        cache_key="cache-key",
                        backend_identity="kind=openai-compatible|model=mock-model|base_url=https://provider.example/v1|temperature=0.200000",
                        prefix_hash="prefix-hash",
                        paper_id="paper-1",
                        source_hash="sha256:abc",
                        prompt_version="v1",
                    ),
                )

            self.assertEqual(payload["study_goal"], "Goal")


if __name__ == "__main__":
    _ = unittest.main()
