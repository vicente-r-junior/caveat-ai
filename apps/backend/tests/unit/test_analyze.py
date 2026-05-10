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


# ---------------------------------------------------------------------------
# Sprint 1 fixup-2 — Constitution VI: silent-empty paths must surface as
# warnings, not as ``warnings=()`` with empty findings. The original
# implementation collapsed three structural failure modes into the same
# "perfect run" branch; these tests pin that they now produce distinct,
# diagnosable warnings.
# ---------------------------------------------------------------------------


def test_analyze_warns_when_model_returns_empty_findings_list(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """Model returns valid JSON with `findings: []` → warn, do not retry.

    A legitimate "no concerns" response is indistinguishable from a model
    that gave up. Constitution VI: surface the ambiguity so the lawyer can
    verify rather than silently accept zero findings.
    """

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {"findings": []}

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert result.findings == ()
    assert len(result.warnings) == 1
    warning = result.warnings[0].lower()
    assert "zero findings" in warning or "no findings" in warning
    assert "verify" in warning


def test_analyze_warns_when_findings_field_missing(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """Model returns valid JSON without a `findings` field at all → warn.

    This is the worst silent failure: the model produced something the
    JSON parser accepted but that has no usable structure. Pre-fixup-2
    this returned ``AnalysisResult(findings=(), warnings=())``.
    """

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {"summary": "I am confused about this contract."}

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert result.findings == ()
    assert len(result.warnings) == 1
    assert "findings" in result.warnings[0].lower()
    assert "missing" in result.warnings[0].lower() or "no usable" in result.warnings[0].lower()


def test_analyze_warns_when_findings_field_wrong_type(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """Model returns `findings: "some string"` (not a list) → warn."""

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {"findings": "I could not produce findings"}

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert result.findings == ()
    assert len(result.warnings) == 1
    assert "findings" in result.warnings[0].lower()


def test_analyze_warns_when_all_entries_malformed(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """Model returns N findings but every one fails the required-fields filter.

    The pre-fixup-2 silent path: ``raw_count == 3`` but ``coerce.findings ==
    ()`` because every entry was malformed. The validator then saw zero
    inputs, returned ``failure_rate == 0.0``, and the analyse stage
    returned silently. This must now warn with the raw count so the
    lawyer can see the model attempted the task and failed.
    """
    payload = {
        "findings": [
            {"severity": "high", "quote": "x"},  # missing title + explanation
            {"title": "no sev", "quote": "y"},  # missing severity + explanation
            "not even a dict",  # wrong type entirely
        ]
    }

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return payload

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert result.findings == ()
    assert len(result.warnings) == 1
    warning = result.warnings[0].lower()
    assert "malformed" in warning
    assert "3" in result.warnings[0]  # the raw count is surfaced


def test_analyze_does_not_retry_on_structural_empty(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """Structural failures must NOT trigger a second Ollama call.

    On the E4B fallback model on a laptop, every retry costs minutes. A
    structural failure is unlikely to flip on a second identical call
    against the same model + same prompt; surfacing the warning is
    cheaper and more honest than silently burning compute.
    """
    call_count = 0

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return {"findings": []}

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    analyze(msa_text, "MSA", msa_playbook)

    assert call_count == 1, "Structural-empty paths must not retry"


def test_analyze_warns_when_retry_returns_structural_empty(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """First pass triggers retry (high failure rate); retry hands back empty."""
    first_payload = {
        "findings": [_make_finding_dict(_QUOTE_BAD, title=f"bad-{i}") for i in range(4)]
    }
    second_payload: dict[str, Any] = {"findings": []}
    calls = iter([first_payload, second_payload])

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return next(calls)

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert result.findings == ()
    # Two warnings expected: the retry-was-triggered note and the
    # structural-empty-on-retry note. The latter must say "on retry" so
    # the human knows the second pass is what failed.
    assert len(result.warnings) == 2
    joined = " ".join(result.warnings).lower()
    assert "retried" in joined or "stricter" in joined
    assert "on retry" in joined


# ---------------------------------------------------------------------------
# Sprint 2 fixup-3 — Constitution VI: Ollama timeouts must surface as
# structured warnings, not as opaque HTTP 500 with stack trace. The fixup-2
# work covered OllamaInvalidJSONError but not OllamaTimeoutError; the manual
# repro on msa-acme.pdf with E4B caught the gap.
# ---------------------------------------------------------------------------


def test_analyze_handles_timeout_first_pass(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """A timeout during the first analyze call → empty findings + warning.

    The warning must name the actual elapsed seconds so the lawyer sees
    the real wait, not a generic "timed out" message.
    """

    def _raise(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise ollama_client.OllamaTimeoutError(
            elapsed_seconds=312.4, timeout_kind="read"
        )

    monkeypatch.setattr(ollama_client, "generate_json", _raise)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert result.findings == ()
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    # The verbatim user-facing copy: name the elapsed seconds, suggest
    # the production-class fallback model, and mention shortening the
    # contract.
    assert "timed out" in warning.lower()
    assert "312.4" in warning
    assert "gemma4:31b-instruct-q4_K_M" in warning
    assert "shorten" in warning.lower() or "long context" in warning.lower()


def test_analyze_handles_timeout_on_retry(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """First pass triggers retry; retry times out → empty findings + warning."""
    first_payload = {
        "findings": [_make_finding_dict(_QUOTE_BAD, title=f"bad-{i}") for i in range(4)]
    }

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        if "CRITICAL" in _prompt:
            raise ollama_client.OllamaTimeoutError(
                elapsed_seconds=210.0, timeout_kind="read"
            )
        return first_payload

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert result.findings == ()
    # Two warnings: the retry-was-triggered note + the timeout-on-retry note.
    assert len(result.warnings) == 2
    joined = " ".join(result.warnings).lower()
    assert "retried" in joined or "stricter" in joined
    assert "on retry" in joined
    assert "210.0" in " ".join(result.warnings)


# ---------------------------------------------------------------------------
# Sprint 2 fixup-4 — Constitution VI: an upstream Ollama HTTP error (e.g.
# HTTP 500 when the llama runner subprocess crashes mid-inference) must
# surface as a structured warning, not as opaque HTTP 500 with stack
# trace. fixup-3 closed the parallel timeout gap; this closes the
# OllamaServerError gap.
# ---------------------------------------------------------------------------


def test_analyze_handles_server_error_first_pass(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """Upstream HTTP 500 on first analyze call → empty findings + warning.

    The warning must name the actual upstream status code (so the lawyer
    sees what really failed) and the elapsed seconds (so the wait the
    user endured is honest, not summarized away).
    """

    def _raise(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise ollama_client.OllamaServerError(
            status_code=500,
            body_snippet='{"error":"llama runner terminated: exit status 2"}',
            elapsed_seconds=212.4,
        )

    monkeypatch.setattr(ollama_client, "generate_json", _raise)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert result.findings == ()
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    # The verbatim user-facing copy: name the status code, the elapsed
    # seconds, and suggest the production-class fallback model.
    assert "HTTP 500" in warning
    assert "212.4" in warning
    assert "gemma4:31b-instruct-q4_K_M" in warning
    # The diagnostic context — "model runner may have crashed
    # mid-inference" — is what tells the lawyer this isn't a bug in
    # Caveat AI but in the underlying inference daemon.
    assert "crashed" in warning.lower() or "runner" in warning.lower()


def test_analyze_handles_server_error_on_retry(
    monkeypatch: pytest.MonkeyPatch,
    msa_text: str,
    msa_playbook: dict[str, Any],
) -> None:
    """First pass triggers retry; retry crashes upstream → 2 warnings."""
    first_payload = {
        "findings": [_make_finding_dict(_QUOTE_BAD, title=f"bad-{i}") for i in range(4)]
    }

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        if "CRITICAL" in _prompt:
            raise ollama_client.OllamaServerError(
                status_code=500,
                body_snippet="runner crash",
                elapsed_seconds=68.2,
            )
        return first_payload

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    result = analyze(msa_text, "MSA", msa_playbook)

    assert result.findings == ()
    # Two warnings: the retry-was-triggered note + the server-error-on-
    # retry note.
    assert len(result.warnings) == 2
    joined = " ".join(result.warnings).lower()
    assert "retried" in joined or "stricter" in joined
    assert "on retry" in joined
    assert "http 500" in joined
    assert "68.2" in " ".join(result.warnings)
