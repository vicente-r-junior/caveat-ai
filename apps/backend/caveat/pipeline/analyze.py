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
6. **Constitution VI fixup-2**: when the model returns valid JSON but the
   ``findings`` payload is unusable (field missing, not a list, all
   entries malformed, or the list is empty), surface a warning rather
   than returning silently empty. The original implementation conflated
   these failure modes with "model successfully reported zero risks"; the
   four cases now have distinct messages so the lawyer sees what
   actually happened.

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


@dataclass(slots=True, frozen=True)
class _CoerceResult:
    """Outcome of converting one Ollama JSON payload into ``Finding`` objects.

    The previous shape (``list[Finding]``) collapsed three distinct failure
    modes — missing ``findings`` key, wrong type, all entries malformed —
    into the same "empty list" return, which is precisely how the silent-
    empty Constitution VI bug got through Sprint 1. Carrying ``raw_count``
    and ``findings_field_present`` here lets :func:`analyze` detect each
    case explicitly and emit a distinct warning.
    """

    findings: tuple[Finding, ...]
    raw_count: int
    """Number of entries the model put under ``findings`` (whatever their
    shape). Zero when the field was missing or not a list."""
    findings_field_present: bool
    """True iff ``payload["findings"]`` was present AND a list. False when
    the model omitted the field or returned a non-list value (string,
    dict, scalar, etc.)."""


def _coerce_findings(payload: dict[str, Any]) -> _CoerceResult:
    """Best-effort conversion of an Ollama JSON response into Finding objects.

    Skips entries that miss any required field. Optional ``redline``
    defaults to an empty string. The :class:`_CoerceResult` carries enough
    metadata for the caller to distinguish *which* failure mode produced
    an empty findings list; see the dataclass docstring for the rationale.
    """
    raw = payload.get("findings")
    if not isinstance(raw, list):
        return _CoerceResult(findings=(), raw_count=0, findings_field_present=False)
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
    return _CoerceResult(
        findings=tuple(out),
        raw_count=len(raw),
        findings_field_present=True,
    )


def _structural_warning(coerce: _CoerceResult, *, on_retry: bool = False) -> str | None:
    """Return a Constitution VI warning describing why *coerce* is unusable.

    Returns ``None`` when the coerce result has at least one usable finding
    — in that case the citation validator decides what happens next.

    The three "structurally empty" cases are surfaced separately because
    they tell the lawyer different things:

    * **Missing/wrong-type ``findings`` field** — the model misunderstood
      the prompt entirely. Likely a too-small model or a prompt tweak
      that confused it.
    * **Empty ``findings`` list** — the model parsed the contract but
      reported nothing concerning. Could be legitimate ("clean contract")
      or a sign the model is undersized for this contract. The lawyer
      should know to verify.
    * **All entries malformed** — the model tried to produce findings but
      did not follow the schema. Usually a sign the JSON-mode response
      has truncated mid-object or the model dropped required fields.
    """
    pass_label = "on retry" if on_retry else "on first pass"
    if not coerce.findings_field_present:
        return (
            f"Analyze stage {pass_label}: model output had no usable "
            "`findings` field (either missing or not a list). No findings "
            "produced. The model may be undersized for this contract or "
            "the response may have been truncated."
        )
    if coerce.raw_count == 0:
        return (
            f"Analyze stage {pass_label}: model returned zero findings. "
            "This may mean no risks were identified, or the model is "
            "undersized for this contract — verify against the source "
            "before relying on the empty result."
        )
    if not coerce.findings:
        return (
            f"Analyze stage {pass_label}: model returned {coerce.raw_count} "
            "finding(s) but every entry was malformed (missing required "
            "fields). No findings produced."
        )
    return None


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
    except ollama_client.OllamaTimeoutError as exc:
        # Sprint 2 fixup-3: a httpx ReadTimeout used to bubble out as an
        # opaque HTTP 500 with stack trace from the router (Constitution VI
        # violation — the same failure mode Sprint 1 fixup-2 closed for
        # OllamaInvalidJSONError but missed for timeouts). Capture it
        # here, return empty findings + a warning that names the actual
        # elapsed seconds, and let the rest of the pipeline (including
        # the summary stage) continue.
        return AnalysisResult(
            findings=(),
            warnings=(
                f"Analyze stage: Ollama timed out after "
                f"{exc.elapsed_seconds:.1f}s. Model may be overwhelmed by "
                "long context. Try gemma4:31b-instruct-q4_K_M on capable "
                "hardware, or shorten the contract.",
            ),
        )

    first_coerce = _coerce_findings(first_payload)

    # Constitution VI fixup-2: catch the silent-empty paths the previous
    # implementation collapsed into "perfect run". We do NOT retry here:
    # a structural failure (missing `findings`, malformed entries, or an
    # empty list) is unlikely to flip on a second identical call against
    # the same model, and on the E4B fallback model on a laptop a second
    # pass costs minutes. Surface and exit; let the lawyer decide whether
    # to re-run with the larger model or different hardware.
    structural = _structural_warning(first_coerce)
    if structural is not None:
        return AnalysisResult(findings=(), warnings=(structural,))

    first_result = validate_citations(first_coerce.findings, text)

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
    except ollama_client.OllamaTimeoutError as exc:
        # Same shape as the first-pass timeout, but mention "on retry" so
        # the lawyer sees that the slow call was the second one. The
        # initial findings (validated, but below the retry threshold) are
        # already lost at this point.
        warnings.append(
            f"Analyze stage: Ollama timed out after {exc.elapsed_seconds:.1f}s "
            "on retry. Model may be overwhelmed by long context. Try "
            "gemma4:31b-instruct-q4_K_M on capable hardware, or shorten the "
            "contract."
        )
        return AnalysisResult(findings=(), warnings=tuple(warnings))

    second_coerce = _coerce_findings(second_payload)
    structural_retry = _structural_warning(second_coerce, on_retry=True)
    if structural_retry is not None:
        warnings.append(structural_retry)
        return AnalysisResult(findings=(), warnings=tuple(warnings))

    second_result = validate_citations(second_coerce.findings, text)

    if second_result.dropped:
        warnings.append(_format_failure_warning(second_result))

    return AnalysisResult(findings=second_result.kept, warnings=tuple(warnings))
