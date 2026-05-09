"""Unit tests for the contract-type classifier.

The classifier wraps a single Ollama call and maps the model's response into
one of five literal contract types. These tests mock at the
``ollama_client.generate_json`` boundary (Constitution I — every test runs
under the autouse no-network guard, but mocking the seam keeps the test
deterministic and fast).

Constitution VI: malformed model output collapses to ``"Other"``, but the
"daemon is down" failure must propagate so the caller can return a clean 503.
"""

from __future__ import annotations

from typing import Any

import pytest

from caveat.llm import ollama_client
from caveat.pipeline.classify import classify


def _patch_response(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> None:
    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return payload

    monkeypatch.setattr(ollama_client, "generate_json", _fake)


def test_classify_returns_msa_when_model_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_response(monkeypatch, {"contract_type": "MSA"})
    assert classify("any text") == "MSA"


@pytest.mark.parametrize(
    "contract_type",
    ["MSA", "NDA", "SaaS", "Employment", "Other"],
)
def test_classify_each_known_type(
    monkeypatch: pytest.MonkeyPatch, contract_type: str
) -> None:
    _patch_response(monkeypatch, {"contract_type": contract_type})
    assert classify("contract text") == contract_type


def test_classify_unknown_returns_other(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_response(monkeypatch, {"contract_type": "Pizza"})
    assert classify("contract text") == "Other"


def test_classify_missing_field_returns_other(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_response(monkeypatch, {"foo": "bar"})
    assert classify("contract text") == "Other"


def test_classify_invalid_json_returns_other(monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed JSON from the model is a soft failure for classification."""

    def _raise(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise ollama_client.OllamaInvalidJSONError("garbage from the model")

    monkeypatch.setattr(ollama_client, "generate_json", _raise)

    assert classify("contract text") == "Other"


def test_classify_unreachable_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Daemon-down must NOT be silently swallowed (Constitution VI).

    The caller (analyze router) returns 503 — this module must not paper
    over the failure with a default value.
    """

    def _raise(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise ollama_client.OllamaUnreachableError(
            "Ollama not reachable at http://localhost:11434"
        )

    monkeypatch.setattr(ollama_client, "generate_json", _raise)

    with pytest.raises(ollama_client.OllamaUnreachableError):
        classify("contract text")
