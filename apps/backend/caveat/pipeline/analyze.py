"""Risk-analysis pipeline stage — calls Ollama once (or twice) and validates citations.

This is the orchestration layer that sits between the Ollama client and
the citation validator. It does the following:

1. Build the analyse prompt with the contract text + playbook.
2. Call Ollama, parse the JSON response into :class:`Finding` objects.
3. Run the citation validator (Constitution II, the unmovable seam).
4. If more than 30 percent of findings were dropped because their quotes
   were not verbatim in the source, retry ONCE with a stricter prompt
   variant that explicitly tells the model its previous output failed
   verbatim-quoting and must do better. Constitution VI: surface, don't
   paper over — when a retry happens, the result carries a warning saying
   so, even if the retry succeeded.
5. On malformed JSON from the model (either pass), return an empty
   :class:`AnalysisResult` with a warning. Do not crash the pipeline.

This module never speaks to the network directly — every external call
funnels through :mod:`caveat.llm.ollama_client` (Constitution I).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from caveat.llm import ollama_client
from caveat.llm.prompts import build_analyze_prompt
from caveat.pipeline.validate_citations import (
    Finding,
    ValidationResult,
    validate_citations,
)

_RETRY_THRESHOLD = 0.30
"""Above this fraction of dropped findings, the analyser retries ONCE with a
stricter prompt. Tuned conservatively: a single bad citation in three
findings should not trigger a retry, but half of them being bad should."""

_STRICTER_PREFIX = (
    "\nCRITICAL: Your previous output had quotes that did not appear "
    "verbatim in the source. You MUST quote the source EXACTLY, "
    "character-for-character, including punctuation and capitalization. "
    "Findings without verbatim quotes will be discarded.\n\n"
)
"""Prepended to the original analyse prompt on retry. The wording is
deliberately blunt — gentle reminders did not help on the first pass."""

_REQUIRED_FIELDS = ("severity", "title", "quote", "explanation")


@dataclass(slots=True, frozen=True)
class AnalysisResult:
    """The output of :func:`analyze` — kept findings plus any warnings.

    Warnings are surfaced (not hidden) per Constitution VI. They flow
    through the API response so the lawyer sees when a retry happened or
    when citations failed in bulk.
    """

    findings: tuple[Finding, ...]
    warnings: tuple[str, ...]


def _coerce_findings(payload: dict[str, Any]) -> list[Finding]:
    """Best-effort conversion of an Ollama JSON response into Finding objects.

    Skips entries that miss any required field. Optional ``redline`` defaults
    to an empty string.
    """
    raw = payload.get("findings", [])
    if not isinstance(raw, list):
        return []
    out: list[Finding] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if any(field not in entry for field in _REQUIRED_FIELDS):
            continue
        try:
            finding = Finding(
                severity=str(entry["severity"]),
                title=str(entry["title"]),
                quote=str(entry["quote"]),
                explanation=str(entry["explanation"]),
                redline=str(entry.get("redline", "") or ""),
            )
        except (TypeError, ValueError):
            continue
        out.append(finding)
    return out


def _format_failure_warning(result: ValidationResult) -> str:
    pct = round(result.failure_rate * 100)
    return (
        f"Citation failure rate after retry: {pct}%. "
        f"{len(result.dropped)} findings were dropped because their quotes "
        f"could not be located verbatim in the source."
    )


def analyze(
    text: str,
    contract_type: str,
    playbook: dict[str, Any],
) -> AnalysisResult:
    """Run the analyse stage end-to-end and return validated findings.

    See module docstring for the full algorithm. The function never raises
    on Ollama-level failures (malformed JSON is converted to an empty
    result + warning); network errors and HTTP errors propagate unchanged
    so the caller can return a clear 5xx.
    """
    prompt = build_analyze_prompt(text, contract_type, playbook)
    warnings: list[str] = []

    # ---- First pass --------------------------------------------------------
    try:
        first_payload = ollama_client.generate_json(prompt)
    except ollama_client.OllamaInvalidJSONError:
        return AnalysisResult(
            findings=(),
            warnings=("Model returned malformed JSON; no findings produced.",),
        )

    first_findings = _coerce_findings(first_payload)
    first_result = validate_citations(first_findings, text)

    if first_result.failure_rate <= _RETRY_THRESHOLD:
        return AnalysisResult(findings=first_result.kept, warnings=tuple(warnings))

    # ---- Retry once with a stricter prompt --------------------------------
    # Per Constitution VI, the user sees that we retried even when the
    # retry rescued the result. Hiding the retry would paper over a real
    # signal that the model is struggling with this contract.
    warnings.append(
        "Initial analysis had a high citation failure rate; retried once "
        "with a stricter prompt."
    )
    stricter_prompt = _STRICTER_PREFIX + prompt
    try:
        second_payload = ollama_client.generate_json(stricter_prompt)
    except ollama_client.OllamaInvalidJSONError:
        warnings.append("Model returned malformed JSON on retry; no findings produced.")
        return AnalysisResult(findings=(), warnings=tuple(warnings))

    second_findings = _coerce_findings(second_payload)
    second_result = validate_citations(second_findings, text)

    if second_result.dropped:
        warnings.append(_format_failure_warning(second_result))

    return AnalysisResult(findings=second_result.kept, warnings=tuple(warnings))
