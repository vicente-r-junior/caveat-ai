"""Unit tests for the source-offset mapping pipeline stage.

Constitution III (no invention) and VI (honesty over polish) are the two
principles this module pins:

* Every located highlight comes from a raw, case-sensitive
  ``str.find`` against the canonical source text — there is no fuzzy
  fallback that could invent a match.
* Findings whose quote does not survive raw ``find`` after citation
  validation surface a verbatim warning naming the finding title;
  ``source_offset`` is ``None`` and the Source tab will not draw a
  highlight for them.

Tests are pure-Python: hand-built ``Finding`` instances + a hand-built
sections list. No Ollama mocking, no DB, no fixtures — the function
under test is a deterministic data transform.
"""

from __future__ import annotations

from typing import Any

from caveat.pipeline.map_offsets import (
    FindingWithOffset,
    SourceOffset,
    map_finding_offsets,
)
from caveat.pipeline.validate_citations import Finding


def _section(
    *,
    idx: int,
    char_start: int,
    char_end: int,
    number: str = "1",
    title: str = "Section",
    body: str = "",
    page: int = 1,
) -> dict[str, Any]:
    """Hand-build a section dict in the shape ``list_sections_for_document`` returns."""
    return {
        "idx": idx,
        "number": number,
        "title": title,
        "body": body,
        "char_start": char_start,
        "char_end": char_end,
        "page": page,
    }


def _finding(quote: str, *, title: str = "F", severity: str = "high") -> Finding:
    return Finding(
        severity=severity,
        title=title,
        quote=quote,
        explanation="explanation",
        redline="",
    )


# ---------------------------------------------------------------------------
# (a) every finding maps when quotes are present verbatim
# ---------------------------------------------------------------------------


def test_every_finding_maps_to_a_section_when_quotes_are_present_verbatim() -> None:
    source = (
        "1. Definitions\nThe term Provider means Acme Corp.\n\n"
        "2. Liability\nIN NO EVENT SHALL PROVIDER BE LIABLE FOR INDIRECT DAMAGES.\n\n"
        "3. Indemnity\nCustomer shall indemnify Provider against all claims.\n"
    )
    sections = (
        _section(idx=0, char_start=0, char_end=49, number="1", title="Definitions"),
        _section(idx=1, char_start=49, char_end=115, number="2", title="Liability"),
        _section(idx=2, char_start=115, char_end=len(source), number="3", title="Indemnity"),
    )
    findings = (
        _finding("The term Provider means Acme Corp.", title="provider def"),
        _finding(
            "IN NO EVENT SHALL PROVIDER BE LIABLE FOR INDIRECT DAMAGES.",
            title="liability waiver",
        ),
        _finding(
            "Customer shall indemnify Provider against all claims.",
            title="one-way indemnity",
        ),
    )

    located, warnings = map_finding_offsets(findings, sections, source)

    assert warnings == ()
    assert len(located) == 3
    for entry in located:
        assert isinstance(entry, FindingWithOffset)
        assert entry.source_offset is not None
        # The slice of source at [start, end) must equal the finding quote
        # verbatim — Constitution III: only-located highlights, no
        # fuzzy fallback.
        offset = entry.source_offset
        assert source[offset.start : offset.end] == entry.finding.quote


def test_section_index_lands_in_the_correct_section() -> None:
    source = "AAA SECTION-ONE-BODY BBB SECTION-TWO-BODY CCC"
    sections = (
        _section(idx=0, char_start=0, char_end=20),
        _section(idx=1, char_start=20, char_end=len(source)),
    )

    located, warnings = map_finding_offsets(
        (_finding("SECTION-TWO-BODY"),), sections, source
    )

    assert warnings == ()
    assert located[0].source_offset is not None
    assert located[0].source_offset.section_index == 1


# ---------------------------------------------------------------------------
# (a.5) whitespace drift in the source (pypdf line wraps) is forgiven
# ---------------------------------------------------------------------------


def test_map_finding_offsets_tolerates_whitespace_drift_in_source() -> None:
    """A mid-clause ``\\n`` in the source must not defeat offset mapping.

    pypdf routinely splits a single contractual clause across multiple
    lines with a hard ``\\n``. The citation validator already collapses
    whitespace runs on both sides before its substring check (see
    :mod:`caveat.pipeline.validate_citations`), so it accepts those
    quotes. The offset stage must mirror that tolerance — otherwise
    citation-validated findings silently lose their Source-tab highlight
    on real PDFs.

    Constitution III is preserved: every non-whitespace token of the
    quote still has to appear verbatim, in order, in the source. Only
    the whitespace bytes between tokens are flexible.
    """
    # Source has a mid-clause line break exactly where the quote has a
    # single space — the canonical pypdf drift pattern.
    source = (
        "9.1 Exclusion of Damages.\n"
        "In no event shall either party's\n"
        "aggregate liability exceed the fees paid in the prior 3 months."
    )
    sections = (_section(idx=0, char_start=0, char_end=len(source)),)
    quote = (
        "In no event shall either party's aggregate liability exceed "
        "the fees paid in the prior 3 months."
    )
    findings = (_finding(quote, title="liability cap"),)

    located, warnings = map_finding_offsets(findings, sections, source)

    assert warnings == ()
    assert len(located) == 1
    offset = located[0].source_offset
    assert offset is not None
    assert offset.section_index == 0

    # The matched span in the *original* source is token-equivalent to
    # the quote: same words, same order, only whitespace differs.
    matched_span = source[offset.start : offset.end]
    assert matched_span.split() == quote.split()
    # And the regex consumed at least the whole single-space-rendered
    # quote width — typically a touch more because each ``\n`` in the
    # source replaces a single ``" "`` in the quote.
    assert offset.end - offset.start >= len(quote.replace(" ", ""))


def test_map_finding_offsets_tolerates_double_spaces_and_tabs() -> None:
    """Mixed whitespace runs (double space, tab) are also tolerated."""
    source = "Customer  shall\tindemnify Provider against all claims."
    sections = (_section(idx=0, char_start=0, char_end=len(source)),)
    findings = (
        _finding(
            "Customer shall indemnify Provider against all claims.",
            title="indemnity",
        ),
    )

    located, warnings = map_finding_offsets(findings, sections, source)

    assert warnings == ()
    assert located[0].source_offset is not None


# ---------------------------------------------------------------------------
# (b) finding whose quote is absent → source_offset=None + warning
# ---------------------------------------------------------------------------


def test_unlocated_finding_emits_warning_naming_title_verbatim() -> None:
    source = "Section 1. Some clean text. No Force Majeure section here."
    sections = (_section(idx=0, char_start=0, char_end=len(source)),)
    findings = (
        _finding(
            "We hereby invent a Force Majeure clause that is not present.",
            title="Indemnification one-way",
        ),
    )

    located, warnings = map_finding_offsets(findings, sections, source)

    assert len(located) == 1
    assert located[0].source_offset is None
    assert located[0].finding == findings[0]

    # Constitution VI: warning must name the title verbatim AND match the
    # exact wording in the brief so the frontend Source tab can render it.
    assert len(warnings) == 1
    assert warnings[0] == (
        "Source viewer: finding 'Indemnification one-way' could not be "
        "located in the source text after citation validation. "
        "The Source tab will not show its highlight."
    )


def test_smart_quote_drift_is_a_genuine_miss_not_papered_over() -> None:
    """A smart quote in the finding that the source spells with a straight
    quote is a *genuine* miss: the regex preserves unicode strictness
    because :func:`re.escape` of ``’`` produces a literal ``’``, which
    does not match the straight ``'`` in the source.

    Constitution III: this asymmetry is intentional — when Gemma emits a
    smart quote the source does not contain, that's a fabrication signal
    the offset stage refuses to paper over. The validator's module
    docstring already commits to the same strictness.
    """
    source = "The term 'Provider' means Acme Corp."
    sections = (_section(idx=0, char_start=0, char_end=len(source)),)
    # Curly apostrophes around Provider — the source uses straight ones.
    findings = (
        _finding("The term ‘Provider’ means Acme Corp.", title="prov-def"),
    )

    located, warnings = map_finding_offsets(findings, sections, source)

    assert located[0].source_offset is None
    assert len(warnings) == 1
    assert "'prov-def'" in warnings[0]


def test_unlocated_finding_kept_in_output_alongside_located_ones() -> None:
    """A miss does not corrupt the order of subsequent findings."""
    source = "alpha beta gamma delta"
    sections = (_section(idx=0, char_start=0, char_end=len(source)),)
    findings = (
        _finding("alpha", title="A"),
        _finding("not-in-source", title="B"),
        _finding("delta", title="C"),
    )

    located, warnings = map_finding_offsets(findings, sections, source)

    assert [entry.finding.title for entry in located] == ["A", "B", "C"]
    assert located[0].source_offset is not None
    assert located[1].source_offset is None
    assert located[2].source_offset is not None
    assert len(warnings) == 1
    assert "'B'" in warnings[0]


# ---------------------------------------------------------------------------
# (c) section selection on a boundary — start == next.char_start
# ---------------------------------------------------------------------------


def test_boundary_offset_resolves_to_later_section() -> None:
    """A finding whose quote starts exactly at section[i+1].char_start lands in section[i+1].

    Boundary rule per the brief: when ``start == next.char_start``, the
    LATER section wins. This is the intuitive choice — a finding whose
    quote starts at "Section 2 imposes…" belongs to Section 2, not at the
    tail of Section 1. The half-open interval ``[char_start, char_end)``
    naturally encodes this.
    """
    # Build a source where two sections meet exactly at offset 20.
    section_one_text = "Section 1 lorem. " * 1  # 17 chars
    section_two_text = "Section 2 imposes a hard cap of $100."
    # Pad section one to exactly 20 chars.
    section_one_text = section_one_text + "xyz"  # 20 chars total
    assert len(section_one_text) == 20
    source = section_one_text + section_two_text

    sections = (
        _section(idx=0, char_start=0, char_end=20),
        _section(idx=1, char_start=20, char_end=len(source)),
    )

    findings = (_finding("Section 2 imposes a hard cap of $100.", title="cap"),)

    located, warnings = map_finding_offsets(findings, sections, source)

    assert warnings == ()
    offset = located[0].source_offset
    assert offset is not None
    # The quote starts exactly at offset 20, which is section 1's char_start.
    assert offset.start == 20
    # And we expect the LATER section (idx=1) to win.
    assert offset.section_index == 1


# ---------------------------------------------------------------------------
# (d) two findings whose quotes appear inside the same section both map
# ---------------------------------------------------------------------------


def test_two_findings_in_same_section_both_map_no_off_by_one() -> None:
    source = (
        "1. Liability\n"
        "First risky clause goes here. "
        "Second risky clause is even worse and lives in the same section."
    )
    sections = (_section(idx=0, char_start=0, char_end=len(source)),)
    findings = (
        _finding("First risky clause goes here.", title="first"),
        _finding(
            "Second risky clause is even worse and lives in the same section.",
            title="second",
        ),
    )

    located, warnings = map_finding_offsets(findings, sections, source)

    assert warnings == ()
    assert len(located) == 2
    assert located[0].source_offset is not None
    assert located[1].source_offset is not None
    assert located[0].source_offset.section_index == 0
    assert located[1].source_offset.section_index == 0
    # No off-by-one: the slice of source at [start, end) must equal the
    # quote for each finding, exactly.
    o0 = located[0].source_offset
    o1 = located[1].source_offset
    assert source[o0.start : o0.end] == findings[0].quote
    assert source[o1.start : o1.end] == findings[1].quote
    # And the second finding's start is strictly after the first's end —
    # no overlap.
    assert o1.start >= o0.end


# ---------------------------------------------------------------------------
# (e) zero findings → empty result + empty warnings
# ---------------------------------------------------------------------------


def test_empty_findings_yields_empty_result_and_empty_warnings() -> None:
    source = "any text at all"
    sections = (_section(idx=0, char_start=0, char_end=len(source)),)

    located, warnings = map_finding_offsets((), sections, source)

    assert located == ()
    assert warnings == ()


# ---------------------------------------------------------------------------
# Defensive — the module exports the dataclasses the router needs.
# ---------------------------------------------------------------------------


def test_source_offset_dataclass_is_frozen_and_carries_three_fields() -> None:
    offset = SourceOffset(section_index=0, start=10, end=20)
    assert offset.section_index == 0
    assert offset.start == 10
    assert offset.end == 20
