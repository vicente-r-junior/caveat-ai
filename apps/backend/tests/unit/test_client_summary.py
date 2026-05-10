"""Unit tests for the client-summary stage.

The summary stage is where the constitutional disclaimer (Constitution IV)
is attached. These tests pin that the disclaimer survives every code path —
happy, partial, and malformed-JSON — because exports downstream rely on it.

Sprint 1 fixup-2: ``build_client_summary`` now returns
``(ClientSummary, tuple[str, ...])`` so the malformed-JSON and per-field
fallback paths surface a Constitution VI warning instead of producing
silent placeholder prose. The existing happy-path tests are updated to
unpack the tuple, and two new tests pin the warning paths.
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

    summary, warnings = build_client_summary([], "MSA", "source text")

    assert isinstance(summary, ClientSummary)
    assert summary.what_this_contract_is == payload["what_this_contract_is"]
    assert summary.what_youre_committing_to == payload["what_youre_committing_to"]
    assert summary.biggest_risks == tuple(payload["biggest_risks"])
    assert summary.recommendation == payload["recommendation"]
    # Constitution IV: disclaimer is the canonical, non-empty constant.
    assert summary.disclaimer == DISCLAIMER_TEXT
    assert summary.disclaimer.strip() != ""
    assert "AI" in summary.disclaimer or "attorney review" in summary.disclaimer
    # Happy path emits no warnings.
    assert warnings == ()


def test_client_summary_missing_fields_filled_with_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the model omits fields, each missing field gets a fallback string.

    Sprint 1 fixup-2: each fallback is now also surfaced as a warning so
    the lawyer sees *which* fields the model omitted instead of just
    seeing the placeholder text.
    """
    _patch(monkeypatch, {"recommendation": "Negotiate the cap."})

    summary, warnings = build_client_summary([], "MSA", "source text")

    assert summary.recommendation == "Negotiate the cap."
    # The other three fields must each carry a non-empty placeholder so
    # exports do not render blank sections.
    assert summary.what_this_contract_is.strip() != ""
    assert summary.what_youre_committing_to.strip() != ""
    # biggest_risks is a tuple — it can be empty when no risks were returned.
    assert isinstance(summary.biggest_risks, tuple)
    # Disclaimer is still attached.
    assert summary.disclaimer == DISCLAIMER_TEXT
    # Constitution VI: the missing fields are named in a warning.
    assert len(warnings) == 1
    assert "what_this_contract_is" in warnings[0]
    assert "what_youre_committing_to" in warnings[0]
    # `recommendation` was provided, so it must NOT appear in the warning.
    assert "recommendation" not in warnings[0]


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

    summary, warnings = build_client_summary([], "MSA", "src")

    assert len(summary.biggest_risks) == 3
    assert summary.biggest_risks == ("Risk A", "Risk B", "Risk C")
    assert warnings == ()


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

    summary, warnings = build_client_summary([], "MSA", "src")

    assert summary.biggest_risks == ("Real risk",)
    assert warnings == ()


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
    summary, warnings = build_client_summary(findings, "MSA", "source text")

    # All four narrative fields fall back to a non-empty placeholder.
    assert summary.what_this_contract_is.strip() != ""
    assert summary.what_youre_committing_to.strip() != ""
    assert summary.recommendation.strip() != ""
    assert isinstance(summary.biggest_risks, tuple)

    # The disclaimer field is the canonical constant.
    assert summary.disclaimer == DISCLAIMER_TEXT

    # Sprint 1 fixup-2: malformed JSON now surfaces a warning instead of
    # silently producing the four placeholder fields.
    assert len(warnings) == 1
    assert "malformed" in warnings[0].lower() or "json" in warnings[0].lower()


# ---------------------------------------------------------------------------
# Sprint 1 fixup-2 — additional coverage of the warnings channel.
# ---------------------------------------------------------------------------


def test_client_summary_no_warnings_when_only_risks_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty `biggest_risks` is a legitimate signal, not a fallback.

    The ClientSummary docstring says "an empty tuple is acceptable: it
    means the model could not identify any material risks". Pin that the
    warnings channel respects this — empty risks alone must NOT produce a
    warning, only the three narrative fields can.
    """
    payload = {
        "what_this_contract_is": "ok",
        "what_youre_committing_to": "ok",
        "biggest_risks": [],
        "recommendation": "ok",
    }
    _patch(monkeypatch, payload)

    summary, warnings = build_client_summary([], "MSA", "src")

    assert summary.biggest_risks == ()
    assert warnings == ()


def test_client_summary_warning_lists_only_offending_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warning enumerates exactly the fields that fell back, no more."""
    payload = {
        "what_this_contract_is": "real prose",
        # what_youre_committing_to omitted → fallback
        # recommendation omitted → fallback
        "biggest_risks": ["one"],
    }
    _patch(monkeypatch, payload)

    _, warnings = build_client_summary([], "MSA", "src")

    assert len(warnings) == 1
    msg = warnings[0]
    assert "what_youre_committing_to" in msg
    assert "recommendation" in msg
    assert "what_this_contract_is" not in msg


# ---------------------------------------------------------------------------
# Sprint 2 fixup-3 — Constitution VI: Ollama timeouts during the summary
# stage must surface as structured warnings + fallback memo + disclaimer,
# not as HTTP 500 from the router.
# ---------------------------------------------------------------------------


def test_client_summary_handles_timeout_with_disclaimer_and_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timeout during summary → fallback memo + disclaimer + verbatim warning.

    The summary stage is the longest in the pipeline (~150-200s on E4B
    on long-context fixtures). Pre-fixup-3 a timeout escaped the
    pipeline as HTTP 500 with stack trace; now it surfaces as a
    Constitution-IV-compliant fallback memo with the canonical
    disclaimer attached AND a warning that names the elapsed seconds.
    Findings produced upstream remain valid — the warning copy says so.
    """
    _patch_raises(
        monkeypatch,
        ollama_client.OllamaTimeoutError(elapsed_seconds=205.7, timeout_kind="read"),
    )

    findings = [
        Finding(
            severity="high",
            title="cap",
            quote="Provider's cap is small",
            explanation="why",
        )
    ]
    summary, warnings = build_client_summary(findings, "MSA", "source text")

    # All four narrative fields fall back to a non-empty placeholder.
    assert summary.what_this_contract_is.strip() != ""
    assert summary.what_youre_committing_to.strip() != ""
    assert summary.recommendation.strip() != ""
    assert isinstance(summary.biggest_risks, tuple)

    # Constitution IV invariant survives the timeout path.
    assert summary.disclaimer == DISCLAIMER_TEXT

    # Constitution VI: the warning is verbatim and names the wait.
    assert len(warnings) == 1
    msg = warnings[0]
    assert "timed out" in msg.lower()
    assert "205.7" in msg
    # The "Findings (if any) are still valid." copy is the honest signal
    # that upstream analyze work was not wasted.
    assert "findings" in msg.lower()
    assert "valid" in msg.lower()


# ---------------------------------------------------------------------------
# Sprint 2 fixup-4 — Constitution VI: upstream Ollama HTTP errors during
# the summary stage (e.g. HTTP 500 when the llama runner crashes
# mid-inference) must surface as a structured warning + fallback memo
# with the canonical disclaimer attached, not as HTTP 500 from the router.
# ---------------------------------------------------------------------------


def test_client_summary_handles_server_error_with_disclaimer_and_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 500 during summary → fallback memo + disclaimer + verbatim warning.

    The summary stage is the longest in the pipeline; a llama runner
    crash here is a real failure mode on E4B / M4 Air. Pre-fixup-4 this
    bubbled to the router as HTTP 500 with stack trace; now it surfaces
    as a Constitution-IV-compliant fallback memo with the canonical
    disclaimer attached AND a warning that names the upstream status
    and elapsed seconds. Findings produced upstream remain valid — the
    warning copy says so verbatim.
    """
    _patch_raises(
        monkeypatch,
        ollama_client.OllamaServerError(
            status_code=500,
            body_snippet="runner terminated: exit status 2",
            elapsed_seconds=58.3,
        ),
    )

    findings = [
        Finding(
            severity="high",
            title="cap",
            quote="Provider's cap is small",
            explanation="why",
        )
    ]
    summary, warnings = build_client_summary(findings, "MSA", "source text")

    # All four narrative fields fall back to a non-empty placeholder.
    assert summary.what_this_contract_is.strip() != ""
    assert summary.what_youre_committing_to.strip() != ""
    assert summary.recommendation.strip() != ""
    assert isinstance(summary.biggest_risks, tuple)

    # Constitution IV invariant survives the upstream-error path.
    assert summary.disclaimer == DISCLAIMER_TEXT

    # Constitution VI: the warning is verbatim and names the upstream
    # status code, the elapsed seconds, and the "findings still valid"
    # signal.
    assert len(warnings) == 1
    msg = warnings[0]
    assert "HTTP 500" in msg
    assert "58.3" in msg
    assert "findings" in msg.lower()
    assert "valid" in msg.lower()
