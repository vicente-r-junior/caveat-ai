"""Citation validator — the unmovable seam, Constitution II.

Every factual claim Caveat AI makes about a contract MUST be backed by a
verbatim quotation from the source document. This module is the gate that
enforces it. Any finding whose ``quote`` is not a literal substring of the
source text (after a *whitespace-only* normalisation) is dropped before it
reaches the user.

The function in this module is **pure**: no I/O, no Ollama dependency, no
globals, no logging. That is the entire point — the validator can be
wrapped, tested, and reasoned about in isolation, and any future call
site (analysis pipeline, chat pipeline, export pipeline) can run findings
through it without dragging the world along. T024 will write exhaustive
tests; the contract here is intentionally narrow so those tests are
unambiguous.

What the validator normalises
-----------------------------
Only runs of whitespace are collapsed to a single space, on both sides of
the comparison. Nothing else.

What the validator does NOT normalise (and why)
-----------------------------------------------
* **Unicode characters are left untouched.** Smart quotes (``“``,
  ``”``, ``‘``, ``’``) MUST NOT match straight quotes
  (``"``, ``'``). When Gemma emits a smart quote that the source does not
  contain, that is a strong signal the model is paraphrasing or
  fabricating — exactly the failure mode this seam exists to catch. Silent
  unicode normalisation here would be an open door for hallucinated
  citations.
* **Punctuation is left untouched.** A missing comma or a turned period is
  also a fabrication signal; preserving it keeps the validator honest.
* **Case is preserved.** Case-sensitive substring match.

Failure modes returned to the caller
------------------------------------
:class:`ValidationResult` carries the kept findings, the dropped findings
(each with a ``reason`` string), and a derived ``failure_rate`` so callers
(specifically :mod:`caveat.pipeline.analyze`) can decide whether to retry
the model with a stricter prompt.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(slots=True, frozen=True)
class Finding:
    """A risk finding produced by the analysis pipeline.

    ``quote`` MUST be a verbatim substring of the contract source text;
    that is exactly the invariant this module enforces.
    """

    severity: str
    title: str
    quote: str
    explanation: str
    redline: str = ""


@dataclass(slots=True, frozen=True)
class DroppedFinding:
    """A finding rejected by the validator, with the reason it was dropped.

    The reason is human-readable and surface-able: callers may forward it
    to logs, warnings, or even the UI so the lawyer can see *which*
    citations failed and why (Constitution VI).
    """

    finding: Finding
    reason: str


@dataclass(slots=True, frozen=True)
class ValidationResult:
    """Outcome of running :func:`validate_citations`.

    ``failure_rate`` is the fraction of findings that were dropped. It is
    used by :mod:`caveat.pipeline.analyze` to decide whether to retry the
    model with a stricter prompt; the threshold lives in *that* module,
    not here, so the validator stays a pure data transformation.
    """

    kept: tuple[Finding, ...]
    dropped: tuple[DroppedFinding, ...]

    @property
    def failure_rate(self) -> float:
        """Dropped / total. Returns 0.0 when there were no findings at all."""
        total = len(self.kept) + len(self.dropped)
        if total == 0:
            return 0.0
        return len(self.dropped) / total


def _normalize_whitespace(text: str) -> str:
    """Collapse any run of whitespace to a single space and strip the ends.

    This is the *only* normalisation the validator applies. See the module
    docstring for why.
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


def validate_citations(
    findings: Iterable[Finding],
    source_text: str,
) -> ValidationResult:
    """Drop findings whose quotes are not verbatim substrings of *source_text*.

    Rules (in order):

    1. Both sides have whitespace runs collapsed to a single space and
       trimmed at the edges.
    2. If the source text is empty after normalisation, every finding is
       dropped with reason ``"Source text is empty"``.
    3. If a finding's quote is empty after normalisation, it is dropped
       with reason ``"Empty quote"``.
    4. If a finding's normalised quote is longer than the normalised
       source, it is dropped with reason ``"Quote longer than source"``
       (a quick rejection that avoids a substring search that cannot
       possibly succeed).
    5. Otherwise, the validator does a case-sensitive substring search.
       Hits go into ``kept``; misses are dropped with reason
       ``"Quote not found verbatim in source (after whitespace normalization)"``.
    """
    findings_list = list(findings)
    normalized_source = _normalize_whitespace(source_text)
    source_is_empty = normalized_source == ""

    kept: list[Finding] = []
    dropped: list[DroppedFinding] = []

    for finding in findings_list:
        normalized_quote = _normalize_whitespace(finding.quote)
        if source_is_empty:
            dropped.append(DroppedFinding(finding=finding, reason="Source text is empty"))
            continue
        if normalized_quote == "":
            dropped.append(DroppedFinding(finding=finding, reason="Empty quote"))
            continue
        if len(normalized_quote) > len(normalized_source):
            dropped.append(
                DroppedFinding(finding=finding, reason="Quote longer than source")
            )
            continue
        if normalized_quote in normalized_source:
            kept.append(finding)
        else:
            dropped.append(
                DroppedFinding(
                    finding=finding,
                    reason="Quote not found verbatim in source (after whitespace normalization)",
                )
            )

    return ValidationResult(kept=tuple(kept), dropped=tuple(dropped))
