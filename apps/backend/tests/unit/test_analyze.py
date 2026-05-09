"""Unit tests for the analyze pipeline stage.

The analyze stage builds the prompt, calls Ollama once (or twice on retry),
parses the JSON, and runs the citation validator. We mock at the
``ollama_client.generate_json`` boundary and use REAL verbatim quotes from
the parsed msa-acme.pdf — that way the validator receives realistic input
rather than synthetic strings that obscure whether the validator is doing
its job inside ``analyze``.

Constitution VI: warnings surface honestly. Constitution II: only validated
findings are returned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from caveat.llm import ollama_client
from caveat.pipeline.analyze import analyze
from caveat.pipeline.load_playbook import load_playbook
from caveat.pipeline.parse import parse_pdf

_FIXTURES = Path(__file__).parents[3].parent / "fixtures" / "contracts"

# Real verbatim substrings present in msa-acme.pdf (verified by parsing the
# fixture and feeding these into validate_citations — see the test setup
# fixture at the bottom of this module).
_QUOTE_LIABILITY_CAP = (
    "THREE (3) MONTHS IMMEDIATELY PRECEDING THE EVENT GIVING RISE TO THE CLAIM"
)
_QUOTE_INDEMNITY = "Customer shall indemnify, defend, and hold harmless Provider"
_QUOTE_NO_REFUND = "no refund of prepaid fees shall be due to Customer"
_QUOTE_DELAWARE = "State of Delaware"
_QUOTE_BAD = "This text does not appear in the contract anywhere at all"


@pytest.fixture(scope="session")
def msa_text() -> str:
    """Parse msa-acme.pdf once per session (heaviest fixture in the suite)."""
    return parse_pdf(_FIXTURES / "msa-acme.pdf").text


@pytest.fixture(scope="session")
def msa_playbook() -> dict[str, Any]:
    return load_playbook("MSA")


def _verify_quotes_real(msa_text: str) -> None:
    """Sanity check: the verbatim quotes used in this module really are in the source.

    If the fixture is regenerated and these strings drift, every test below
    becomes meaningless. Failing fast here points the diagnostic at the
    fixture rather than at the analyze pipeline.
    """
    from caveat.pipeline.validate_citations import Finding, validate_citations

    findings = [
        Finding(severity="high", title="t", quote=q, explanation="e")
        for q in (
            _QUOTE_LIABILITY_CAP,
            _QUOTE_INDEMNITY,
            _QUOTE_NO_REFUND,
            _QUOTE_DELAWARE,
        )
    ]
    result = validate_citations(findings, msa_text)
    assert len(result.kept) == 4, (
        "Test verbatim quotes have drifted from msa-acme.pdf — regenerate the "
        "fixture or update the constants in this module."
    )


def _make_finding_dict(quote: str, *, severity: str = "high", title: str = "F") -> dict[str, Any]:
    return {
        "severity": severity,
        "title": title,
        "quote": quote,
        "explanation": "explanation text",
        "redline": "",
    }


def test_analyze_happy_path_with_three_valid_findings(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    _verify_quotes_real(msa_text)

    payload = {
        "findings": [
            _make_finding_dict(_QUOTE_LIABILITY_CAP, severity="high", title="3-month cap"),
            _make_finding_dict(_QUOTE_INDEMNITY, severity="high", title="One-way indemnity"),
            _make_finding_dict(_QUOTE_NO_REFUND, severity="medium", title="No refund"),
            _make_finding_dict(_QUOTE_BAD, severity="low", title="Fabricated"),
        ]
    }

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return payload

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    # Three valid (verbatim) + one fabricated → three kept. Failure rate is
    # 1/4 = 0.25, below the 0.30 retry threshold, so no warnings.
    assert len(result.findings) == 3
    titles = {f.title for f in result.findings}
    assert titles == {"3-month cap", "One-way indemnity", "No refund"}
    assert result.warnings == ()


def test_analyze_triggers_retry_on_high_failure_rate(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """All-bad first response → retry → second response valid."""
    first_payload = {
        "findings": [
            _make_finding_dict(_QUOTE_BAD, title=f"bad-{i}") for i in range(4)
        ]
    }
    second_payload = {
        "findings": [
            _make_finding_dict(_QUOTE_LIABILITY_CAP, title="recovered-1"),
            _make_finding_dict(_QUOTE_INDEMNITY, title="recovered-2"),
        ]
    }
    calls = iter([first_payload, second_payload])

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return next(calls)

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert len(result.findings) == 2
    assert {f.title for f in result.findings} == {"recovered-1", "recovered-2"}
    # Constitution VI: the retry is surfaced even when it succeeded.
    assert any("retried" in w.lower() or "stricter" in w.lower() for w in result.warnings)


def test_analyze_warns_when_post_retry_still_has_drops(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """After retry, surviving drops must produce a failure-rate warning."""
    first_payload = {
        "findings": [_make_finding_dict(_QUOTE_BAD, title=f"bad-{i}") for i in range(4)]
    }
    second_payload = {
        "findings": [
            _make_finding_dict(_QUOTE_LIABILITY_CAP, title="ok-1"),
            _make_finding_dict(_QUOTE_BAD + " again", title="bad-r1"),
            _make_finding_dict(_QUOTE_BAD + " more", title="bad-r2"),
        ]
    }
    calls = iter([first_payload, second_payload])

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return next(calls)

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert len(result.findings) == 1
    assert result.findings[0].title == "ok-1"
    # Two warnings expected: the retry-was-triggered note and the
    # "still dropped after retry" failure-rate note.
    assert len(result.warnings) >= 2
    joined = " ".join(result.warnings).lower()
    assert "failure rate" in joined or "dropped" in joined


def test_analyze_handles_invalid_json_gracefully(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    def _raise(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise ollama_client.OllamaInvalidJSONError("not json")

    monkeypatch.setattr(ollama_client, "generate_json", _raise)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert result.findings == ()
    assert len(result.warnings) == 1
    assert "malformed json" in result.warnings[0].lower()


def test_analyze_propagates_unreachable_error(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """Daemon-down propagates so the router can return 503."""

    def _raise(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise ollama_client.OllamaUnreachableError("Ollama not reachable")

    monkeypatch.setattr(ollama_client, "generate_json", _raise)

    with pytest.raises(ollama_client.OllamaUnreachableError):
        analyze(msa_text, "MSA", msa_playbook)


def test_analyze_skips_malformed_finding_dicts(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """Entries missing required fields are dropped silently before validation."""
    payload = {
        "findings": [
            _make_finding_dict(_QUOTE_LIABILITY_CAP, title="ok-1"),
            {"severity": "high", "quote": _QUOTE_INDEMNITY, "explanation": "e"},  # no title
            {"title": "no severity", "quote": _QUOTE_DELAWARE, "explanation": "e"},
            _make_finding_dict(_QUOTE_INDEMNITY, title="ok-2"),
        ]
    }

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return payload

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert len(result.findings) == 2
    assert {f.title for f in result.findings} == {"ok-1", "ok-2"}
