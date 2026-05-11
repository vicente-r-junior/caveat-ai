"""Verify the source-offset round-trip against a real analyse run in SQLite.

Sprint 3 audit point 1 — pinned by 199 automated tests but blocked on a
visual run against real Gemma output because E4B produced 0 findings on
`msa-acme.pdf` (26KB prompt). This script reads the persisted document
text, sections, and findings for a given ``document_id`` out of SQLite,
re-runs :func:`caveat.pipeline.map_offsets.map_finding_offsets`, and
prints per-finding round-trip results so the byte-exact (whitespace-
tolerant) property can be confirmed against a real-world response.

Property being checked, per finding
-----------------------------------
    source_text[offset.start:offset.end].split() == finding.quote.split()

That is the same whitespace-tolerant comparison the citation validator and
the offset stage already agree on — exact tokens, in order, with any
whitespace combo between them.

Usage
-----
    # From the repo root (`uv` picks up apps/backend/pyproject.toml).
    cd apps/backend
    uv run python -m scripts.verify_offset_roundtrip <document_id>

    # Or with an explicit DB path:
    CAVEAT_DATA_DIR=/tmp/run-1 uv run python -m scripts.verify_offset_roundtrip <document_id>

Exit codes
----------
0   every finding round-trips (or no findings exist).
1   at least one finding fails to round-trip — see stdout for the offending
    finding title and the diff.
2   bad CLI arguments / document not found.
"""

from __future__ import annotations

import sys

from caveat.pipeline.map_offsets import map_finding_offsets
from caveat.pipeline.validate_citations import Finding
from caveat.storage import db


def _load(document_id: str) -> tuple[str, tuple[dict, ...], tuple[Finding, ...]]:
    doc = db.get_document(document_id)
    if doc is None:
        print(f"document not found: {document_id}", file=sys.stderr)
        sys.exit(2)
    text = str(doc["text"])
    sections = tuple(db.list_sections_for_document(document_id))
    rows = db.list_findings_for_document(document_id)
    findings = tuple(
        Finding(
            severity=str(row["severity"]),
            title=str(row["title"]),
            quote=str(row["quote"]),
            explanation=str(row["explanation"]),
            redline=str(row.get("redline") or ""),
        )
        for row in rows
    )
    return text, sections, findings


def _check(
    text: str,
    sections: tuple[dict, ...],
    findings: tuple[Finding, ...],
) -> int:
    """Return the number of round-trip failures."""
    if not findings:
        print("no findings persisted for this document — nothing to verify.")
        return 0
    if not sections:
        print(
            "no sections persisted for this document — Source tab would render empty.\n"
            "Re-upload the document to populate sections.",
            file=sys.stderr,
        )
        return len(findings)

    located, warnings = map_finding_offsets(findings, sections, text)
    failures = 0
    for fwo in located:
        title = fwo.finding.title
        offset = fwo.source_offset
        if offset is None:
            print(f"MISS  {title!r}  (no offset — see Source viewer warning)")
            failures += 1
            continue
        slice_ = text[offset.start : offset.end]
        quote_tokens = fwo.finding.quote.split()
        slice_tokens = slice_.split()
        if slice_tokens != quote_tokens:
            print(
                f"FAIL  {title!r}\n"
                f"  offset = (section={offset.section_index}, "
                f"start={offset.start}, end={offset.end})\n"
                f"  slice tokens = {slice_tokens}\n"
                f"  quote tokens = {quote_tokens}"
            )
            failures += 1
        else:
            print(
                f"OK    {title!r}  "
                f"(section={offset.section_index}, span={offset.end - offset.start} chars)"
            )
    if warnings:
        print("\nConstitution VI warnings from map_finding_offsets:")
        for w in warnings:
            print(f"  - {w}")
    return failures


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: verify_offset_roundtrip.py <document_id>",
            file=sys.stderr,
        )
        return 2
    document_id = sys.argv[1]
    text, sections, findings = _load(document_id)
    print(
        f"document_id   = {document_id}\n"
        f"text          = {len(text)} chars\n"
        f"sections      = {len(sections)}\n"
        f"findings      = {len(findings)}\n"
    )
    failures = _check(text, sections, findings)
    print()
    if failures:
        print(f"FAILED: {failures} of {len(findings)} findings did not round-trip.")
        return 1
    print(f"PASS: all {len(findings)} findings round-trip byte-exact (whitespace-tolerant).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
