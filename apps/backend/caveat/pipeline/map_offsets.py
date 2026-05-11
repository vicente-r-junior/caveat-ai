"""Source-offset mapping — locate every finding's quote inside the source text.

This stage runs **after** the citation validator (Constitution II,
:mod:`caveat.pipeline.validate_citations`). The validator already proved
that each kept finding's quote is a verbatim substring of the source
*after whitespace normalisation*; this stage tags each finding with the
character offsets the Source tab needs to draw a highlight.

Constitution alignment
----------------------
* **III — The model does not invent.** This module locates a quote only
  when every non-whitespace token of the quote appears verbatim, in
  order, in ``source_text``. The match is **whitespace-tolerant**
  (mid-clause ``\\n`` from pypdf is forgiven, exactly like the validator
  already does) but it is otherwise byte-exact: case-sensitive, no
  unicode normalisation, no smart-quote substitution, no fuzzy edit
  distance. A token that isn't present in the source still produces a
  miss and a warning. The Source tab will not render an "approximate"
  highlight that wasn't in the contract.
* **VI — Honesty over polish.** When a citation-validated finding cannot
  be located even with whitespace tolerance (e.g., Gemma emitted a smart
  quote ``’`` where the source has a straight ``'``, or fabricated
  wording the validator somehow missed), we surface a **named warning**
  rather than dropping the finding silently. The lawyer sees that the
  highlight is missing and why, in the same warnings channel the analyse
  + summary stages already use.

Why whitespace-tolerant search rather than raw ``str.find``
-----------------------------------------------------------
pypdf-extracted contract text routinely splits a single clause across
multiple lines with a hard ``\\n``. The citation validator already
collapses whitespace runs on both sides before its substring check, so
the validator accepts those quotes. A naive raw ``source_text.find``
here would miss them — which means the Source tab silently loses the
highlight for clauses the validator (correctly) kept. That asymmetry
breaks the Tab 03 demo on real PDFs.

The fix mirrors the validator's behaviour in regex form: every
whitespace run inside the finding's quote is rewritten as ``\\s+`` in
the search pattern, so any whitespace combo (single space, ``\\n``,
``\\t``, mixed) matches between tokens. Because we ``re.search`` against
the **original** ``source_text``, the match's ``.start()`` and ``.end()``
report offsets directly into the source the Source tab will render —
no back-mapping from a normalised string is needed.

Algorithm
---------
For each finding:

1. Build a regex pattern from ``finding.quote``: split on whitespace
   runs, regex-escape each token, rejoin with ``\\s+``. Empty quotes
   (which the validator should have already dropped) defensively miss.
2. ``re.search(pattern, source_text)`` — first match wins.
3. On miss: emit a Constitution VI warning naming the finding's title
   verbatim, append ``FindingWithOffset(finding, source_offset=None)``
   and continue.
4. On hit: walk ``sections`` (assumed sorted by ``char_start``) and pick
   the section whose half-open ``[char_start, char_end)`` interval
   contains ``match.start()``. **Boundary rule**: when ``start`` equals
   a section's ``char_start`` (i.e. the quote begins exactly at a
   section boundary), the **later** section wins — the finding belongs
   to the start of the new section, not the tail of the prior one. This
   is the intuitive choice when the quote starts with a heading-adjacent
   token like "Section 4.2 imposes…".
5. Build ``SourceOffset(section_index=section["idx"],
   start=match.start(), end=match.end())``. Note that ``end - start``
   may be larger than ``len(finding.quote)`` when the source had a
   ``\\n`` where the quote had a single space — that's expected; the
   Source tab highlights the region of the contract that backs the
   finding, not a re-hydrated copy of the model's whitespace.

The function performs zero I/O (Constitution I): it is a pure
transformation over its inputs, suitable for unit testing without
mocking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from caveat.pipeline.validate_citations import Finding


@dataclass(slots=True, frozen=True)
class SourceOffset:
    """Half-open ``[start, end)`` byte interval inside the source text.

    ``section_index`` is the ``idx`` of the matching :class:`Section`
    inside :attr:`caveat.pipeline.parse.ParsedDocument.sections` (and the
    ``idx`` column of the ``sections`` SQLite table). The Source tab uses
    it to look up which section to render the highlight inside.
    """

    section_index: int
    start: int
    end: int


@dataclass(slots=True, frozen=True)
class FindingWithOffset:
    """A validated finding paired with its source-text offset (or ``None``).

    ``source_offset`` is ``None`` when the finding survived citation
    validation but could not be located by the whitespace-tolerant regex
    search against the canonical source text — see the module docstring
    for when that happens (typically: smart-quote vs straight-quote
    drift, or Gemma fabricating wording the validator somehow missed).
    The accompanying warning naming the finding title goes into the
    warnings tuple returned alongside.
    """

    finding: Finding
    source_offset: SourceOffset | None


def _build_whitespace_tolerant_pattern(quote: str) -> str:
    """Compile *quote* into a regex pattern that tolerates whitespace drift.

    Mirrors :func:`caveat.pipeline.validate_citations._normalize_whitespace`
    in regex form: every whitespace run inside *quote* is rewritten as
    ``\\s+`` so any whitespace combo in the source (single space,
    ``\\n``, ``\\t``, mixed) matches between tokens. Each non-whitespace
    token is :func:`re.escape`'d so regex metacharacters present in
    contract text (``.``, ``$``, ``(``, etc.) match literally.

    Returns ``""`` when *quote* is empty or whitespace-only — the
    validator should have already dropped those, but the offset stage
    defends against malformed input by returning the empty pattern,
    which the caller treats as a miss (Constitution VI: surface, do not
    paper over).
    """
    stripped = quote.strip()
    if not stripped:
        return ""
    tokens = re.split(r"\s+", stripped)
    return r"\s+".join(re.escape(token) for token in tokens)


def _locate_section_index(
    start: int, sorted_sections: tuple[dict[str, Any], ...]
) -> int | None:
    """Return the ``idx`` of the section whose ``[char_start, char_end)`` covers *start*.

    Walks ``sorted_sections`` (sorted by ``char_start`` ascending) and
    returns the ``idx`` of the section satisfying
    ``char_start <= start < char_end``. Sections produced by
    :mod:`caveat.pipeline.parse` are guaranteed non-overlapping and
    continuous, so at most one section matches.

    The half-open interval is the boundary-resolution rule: when
    ``start == next.char_start``, the prior section's ``char_end`` equals
    that same value, so ``start < prior.char_end`` is **False** (the
    prior section's interval is exclusive of its end), but
    ``start < next.char_end`` is **True**. Result: the *later* section
    wins on a boundary hit, as the brief specifies.

    Returns ``None`` if no covering section is found (defensive — would
    only happen for a malformed sections list with gaps the parser is
    not supposed to produce, e.g., a hand-built fixture in tests).
    """
    for section in sorted_sections:
        char_start = int(section["char_start"])
        char_end = int(section["char_end"])
        if char_start <= start < char_end:
            return int(section["idx"])
    return None


def map_finding_offsets(
    findings: tuple[Finding, ...],
    sections: tuple[dict[str, Any], ...],
    source_text: str,
) -> tuple[tuple[FindingWithOffset, ...], tuple[str, ...]]:
    """Tag each finding with a :class:`SourceOffset` (or ``None``) + collect warnings.

    Parameters
    ----------
    findings:
        Citation-validated findings, in the order the analyse stage
        returned them. Order is preserved in the output.
    sections:
        Section rows as returned by
        :func:`caveat.storage.db.list_sections_for_document` (or any
        equivalent shape with ``idx``, ``char_start``, ``char_end`` keys).
        The function sorts them defensively before walking.
    source_text:
        The canonical document text (same string the citation validator
        ran against — :attr:`caveat.pipeline.parse.ParsedDocument.text`).

    Returns
    -------
    tuple of two tuples:

    * The first tuple is one :class:`FindingWithOffset` per input finding,
      in order. ``source_offset`` is ``None`` when the quote could not be
      located.
    * The second tuple is the Constitution VI warnings string list — one
      verbatim entry per finding that could not be located.
    """
    sorted_sections = tuple(
        sorted(sections, key=lambda s: int(s["char_start"]))
    )
    out: list[FindingWithOffset] = []
    warnings: list[str] = []

    miss_warning = (
        "Source viewer: finding '{title}' could not be located in the "
        "source text after citation validation. The Source tab will not "
        "show its highlight."
    )

    for finding in findings:
        pattern = _build_whitespace_tolerant_pattern(finding.quote)
        match = re.search(pattern, source_text) if pattern else None
        if match is None:
            # Constitution VI: name the finding title verbatim so the
            # lawyer can correlate the warning to the missing highlight
            # in the Source tab. This mirrors the analyse-stage and
            # summary-stage warning style — surface, do not paper over.
            # After Sprint 3's whitespace-tolerant search, this branch
            # only fires for genuine misses: smart-quote drift, model
            # fabrications the validator somehow accepted, or empty
            # quotes that should never have reached us.
            warnings.append(miss_warning.format(title=finding.title))
            out.append(FindingWithOffset(finding=finding, source_offset=None))
            continue

        start = match.start()
        end = match.end()

        section_idx = _locate_section_index(start, sorted_sections)
        if section_idx is None:
            # Defensive — sections should always cover the document. If a
            # malformed sections list with gaps slips through, surface
            # rather than silently mis-render.
            warnings.append(miss_warning.format(title=finding.title))
            out.append(FindingWithOffset(finding=finding, source_offset=None))
            continue

        out.append(
            FindingWithOffset(
                finding=finding,
                source_offset=SourceOffset(
                    section_index=section_idx,
                    start=start,
                    end=end,
                ),
            )
        )

    return tuple(out), tuple(warnings)
