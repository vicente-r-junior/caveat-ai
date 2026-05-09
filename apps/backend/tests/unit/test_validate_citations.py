"""Exhaustive unit tests for the citation validator (Constitution II).

The citation validator is the unmovable seam between Gemma's output and what
reaches the user. Every factual claim Caveat AI makes about a contract must
be backed by a verbatim quotation; this test file pins down the exact
boundary of "verbatim" and the failure-rate arithmetic the analysis
pipeline depends on.

These tests are intentionally fine-grained — one assertion idea per test —
because the validator is the constitutional gate and any regression here
silently lets fabricated citations through.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

import pytest

from caveat.pipeline.validate_citations import (
    DroppedFinding,
    Finding,
    validate_citations,
)


def _f(quote: str, *, severity: str = "high", title: str = "T", expl: str = "E") -> Finding:
    """Tiny helper to keep test bodies focused on the quote field."""
    return Finding(severity=severity, title=title, quote=quote, explanation=expl)


def test_valid_quote_found_verbatim() -> None:
    source = "The Provider shall maintain the Services with reasonable care."
    finding = _f("Provider shall maintain the Services")

    result = validate_citations([finding], source)

    assert result.kept == (finding,)
    assert result.dropped == ()
    assert result.failure_rate == 0.0


def test_quote_missing_entirely() -> None:
    source = "The Provider shall maintain the Services."
    finding = _f("Customer shall pay all sums on demand")

    result = validate_citations([finding], source)

    assert result.kept == ()
    assert len(result.dropped) == 1
    dropped = result.dropped[0]
    assert isinstance(dropped, DroppedFinding)
    assert dropped.finding is finding
    assert "not found" in dropped.reason.lower()


def test_quote_partial_word_match() -> None:
    """Model-extended quote must NOT match.

    The source contains the prefix; the quote adds words the model invented.
    This is a real fabrication mode the validator must catch.
    """
    source = "Customer shall indemnify Provider against claims."
    finding = _f("Customer shall indemnify Provider for everything")

    result = validate_citations([finding], source)

    assert result.kept == ()
    assert len(result.dropped) == 1
    assert "not found" in result.dropped[0].reason.lower()


def test_whitespace_normalized_match_succeeds() -> None:
    """Multiple spaces, tabs, and newlines on either side must collapse."""
    source = "The Provider\n\nshall   maintain\tthe Services."
    finding = _f("Provider shall maintain the Services")

    result = validate_citations([finding], source)

    assert result.kept == (finding,)
    assert result.dropped == ()


def test_smart_quotes_do_not_match_straight_quotes() -> None:
    """Anti-fabrication: smart vs straight quotes must NOT be normalized.

    See validate_citations module docstring — silent unicode normalization
    here would let the model fabricate citations by paraphrasing punctuation.
    """
    source = "Provider’s liability shall be limited."  # smart quote U+2019
    finding = _f("Provider's liability shall be limited")  # ASCII apostrophe

    result = validate_citations([finding], source)

    assert result.kept == ()
    assert len(result.dropped) == 1
    assert "not found" in result.dropped[0].reason.lower()


def test_punctuation_preserved_exactly() -> None:
    """Trailing punctuation difference must NOT match — punctuation is preserved."""
    source = "See Section 7 for details."
    finding = _f("Section 7.")  # quote has trailing period; source does not

    result = validate_citations([finding], source)

    assert result.kept == ()
    assert len(result.dropped) == 1
    assert "not found" in result.dropped[0].reason.lower()


def test_empty_quote_dropped() -> None:
    source = "Some real contract text here that is non-trivial."
    finding = _f("")

    result = validate_citations([finding], source)

    assert result.kept == ()
    assert len(result.dropped) == 1
    assert result.dropped[0].reason == "Empty quote"


def test_empty_source_drops_everything() -> None:
    findings = [_f("anything"), _f("something else"), _f("Customer shall indemnify")]

    result = validate_citations(findings, "")

    assert result.kept == ()
    assert len(result.dropped) == 3
    for dropped in result.dropped:
        assert dropped.reason == "Source text is empty"


def test_quote_longer_than_source_dropped() -> None:
    source = "short"
    long_quote = "this quote is much longer than the source text it claims to be drawn from"
    finding = _f(long_quote)

    result = validate_citations([finding], source)

    assert result.kept == ()
    assert len(result.dropped) == 1
    assert result.dropped[0].reason == "Quote longer than source"


def test_mixed_valid_and_invalid_split_correctly() -> None:
    source = (
        "The Provider shall maintain the Services. "
        "Customer shall pay all fees within thirty days. "
        "This Agreement is governed by the laws of the State of Delaware."
    )
    valid_findings = [
        _f("Provider shall maintain the Services"),
        _f("Customer shall pay all fees"),
        _f("State of Delaware"),
    ]
    invalid_findings = [
        _f("Customer must arbitrate in Switzerland"),
        _f("Provider warrants no bugs whatsoever"),
    ]
    all_findings = [*valid_findings, *invalid_findings]

    result = validate_citations(all_findings, source)

    assert len(result.kept) == 3
    assert set(result.kept) == set(valid_findings)
    assert len(result.dropped) == 2
    dropped_findings = {d.finding for d in result.dropped}
    assert dropped_findings == set(invalid_findings)
    for dropped in result.dropped:
        assert "not found" in dropped.reason.lower()


def test_failure_rate_arithmetic() -> None:
    source = "alpha bravo charlie delta echo foxtrot"
    findings = [
        _f("alpha bravo"),
        _f("charlie delta"),
        _f("echo foxtrot"),
        _f("hotel india"),  # invalid
    ]

    result = validate_citations(findings, source)

    assert len(result.kept) == 3
    assert len(result.dropped) == 1
    assert result.failure_rate == pytest.approx(0.25)

    # Empty input must return failure_rate 0.0, not divide-by-zero.
    empty_result = validate_citations([], source)
    assert empty_result.failure_rate == 0.0
    assert empty_result.kept == ()
    assert empty_result.dropped == ()


def test_findings_iterable_can_be_generator() -> None:
    """The signature is ``Iterable[Finding]``, so a generator must work.

    A common bug is calling ``len()`` on the input; this test catches that.
    """
    source = "The quick brown fox jumps over the lazy dog."

    def _gen() -> Iterator[Finding]:
        yield _f("quick brown fox")
        yield _f("nonexistent phrase")
        yield _f("lazy dog")

    result = validate_citations(_gen(), source)

    assert len(result.kept) == 2
    assert len(result.dropped) == 1


def test_result_is_immutable() -> None:
    """ValidationResult is a frozen dataclass with tuple fields."""
    source = "The Provider shall maintain the Services."
    result = validate_citations([_f("Provider shall maintain")], source)

    # Fields must be tuples, not lists, so callers cannot mutate them.
    assert isinstance(result.kept, tuple)
    assert isinstance(result.dropped, tuple)

    # Frozen dataclass: any attempt to rebind a field raises FrozenInstanceError.
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.kept = ()  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.dropped = ()  # type: ignore[misc]
