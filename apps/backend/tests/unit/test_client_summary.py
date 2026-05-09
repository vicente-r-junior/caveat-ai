"""Unit tests for the client-summary stage.

The summary stage is where the constitutional disclaimer (Constitution IV)
is attached. These tests pin that the disclaimer survives every code path —
happy, partial, and malformed-JSON — because exports downstream rely on it.
"""

from __future__ import annotations

from typing import Any

import pytest

from caveat.llm import ollama_client
from caveat.pipeline.client_summary import (
    DISCLAIMER_TEXT,
    ClientSummary,
    build_client_summary,
)
from caveat.pipeline.validate_citations import Finding


def _patch(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> None:
    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return payload

    monkeypatch.setattr(ollama_client, "generate_json", _fake)


def _patch_raises(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    def _raise(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise exc

    monkeypatch.setattr(ollama_client, "generate_json", _raise)


def test_client_summary_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "what_this_contract_is": "A standard MSA between Acme and a customer.",
        "what_youre_committing_to": "Pay fees on time and follow the AUP.",
        "biggest_risks": ["Low liability cap", "One-way indemnity", "No DPA"],
        "recommendation": "Negotiate the cap and add a DPA before signing.",
    }
    _patch(monkeypatch, payload)

    summary = build_client_summary([], "MSA", "source text")

    assert isinstance(summary, ClientSummary)
    assert summary.what_this_contract_is == payload["what_this_contract_is"]
    assert summary.what_youre_committing_to == payload["what_youre_committing_to"]
    assert summary.biggest_risks == tuple(payload["biggest_risks"])
    assert summary.recommendation == payload["recommendation"]
    # Constitution IV: disclaimer is the canonical, non-empty constant.
    assert summary.disclaimer == DISCLAIMER_TEXT
    assert summary.disclaimer.strip() != ""
    assert "AI" in summary.disclaimer or "attorney review" in summary.disclaimer


def test_client_summary_missing_fields_filled_with_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the model omits fields, each missing field gets a fallback string."""
    _patch(monkeypatch, {"recommendation": "Negotiate the cap."})

    summary = build_client_summary([], "MSA", "source text")

    assert summary.recommendation == "Negotiate the cap."
    # The other three fields must each carry a non-empty placeholder so
    # exports do not render blank sections.
    assert summary.what_this_contract_is.strip() != ""
    assert summary.what_youre_committing_to.strip() != ""
    # biggest_risks is a tuple — it can be empty when no risks were returned.
    assert isinstance(summary.biggest_risks, tuple)
    # Disclaimer is still attached.
    assert summary.disclaimer == DISCLAIMER_TEXT


def test_client_summary_caps_biggest_risks_at_three(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "what_this_contract_is": "x",
        "what_youre_committing_to": "y",
        "biggest_risks": [
            "Risk A",
            "Risk B",
            "Risk C",
            "Risk D",  # excess — must be trimmed
            "Risk E",  # excess — must be trimmed
        ],
        "recommendation": "z",
    }
    _patch(monkeypatch, payload)

    summary = build_client_summary([], "MSA", "src")

    assert len(summary.biggest_risks) == 3
    assert summary.biggest_risks == ("Risk A", "Risk B", "Risk C")


def test_client_summary_filters_empty_strings_from_risks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "what_this_contract_is": "x",
        "what_youre_committing_to": "y",
        "biggest_risks": ["", "Real risk", "   ", ""],
        "recommendation": "z",
    }
    _patch(monkeypatch, payload)

    summary = build_client_summary([], "MSA", "src")

    assert summary.biggest_risks == ("Real risk",)


def test_client_summary_disclaimer_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Constitution IV: the disclaimer is non-removable, even on errors.

    A malformed JSON response from the model produces fallback prose for
    each narrative field, BUT the disclaimer must still be the canonical
    constant. The disclaimer is the constitutional invariant; everything
    else is replaceable.
    """
    _patch_raises(monkeypatch, ollama_client.OllamaInvalidJSONError("garbage"))

    findings = [
        Finding(
            severity="high",
            title="cap",
            quote="Provider's cap is small",
            explanation="why",
        )
    ]
    summary = build_client_summary(findings, "MSA", "source text")

    # All four narrative fields fall back to a non-empty placeholder.
    assert summary.what_this_contract_is.strip() != ""
    assert summary.what_youre_committing_to.strip() != ""
    assert summary.recommendation.strip() != ""
    assert isinstance(summary.biggest_risks, tuple)

    # The disclaimer field is the canonical constant.
    assert summary.disclaimer == DISCLAIMER_TEXT
