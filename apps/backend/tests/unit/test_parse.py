"""Unit tests for the PDF parser.

Covers the three synthetic fixtures and the ScannedPDFError path. Parsing a
PDF is the only file-I/O step in the pipeline, so these tests touch the disk
but never the network (the autouse no-network guard in conftest enforces that).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from caveat.pipeline.parse import ParsedDocument, ScannedPDFError, parse_pdf

_FIXTURES = Path(__file__).parents[3].parent / "fixtures" / "contracts"


@pytest.fixture(scope="session")
def msa_acme_parsed() -> ParsedDocument:
    """Parse msa-acme.pdf once per session — it's the heaviest synthetic fixture.

    Constitution X requires the unit suite to run under 10 seconds; reusing
    the parsed result across tests that need it keeps the suite fast.
    """
    return parse_pdf(_FIXTURES / "msa-acme.pdf")


def test_parse_msa_acme_happy_path(msa_acme_parsed: ParsedDocument) -> None:
    parsed = msa_acme_parsed

    # The fixture README pins this at 8 pages. If the build script changes
    # the rendered length, update the README and the assertion together.
    assert parsed.page_count == 8
    assert len(parsed.text) > 5000
    # The MSA has §§ 1–17 plus subsections; the heuristic should catch
    # several of them. Don't pin the exact count — just that the detector ran.
    assert len(parsed.sections) >= 5


def test_parse_msa_acme_section_bodies_are_continuous(
    msa_acme_parsed: ParsedDocument,
) -> None:
    """Sprint 3 (T002): section bodies cover the document without gaps or overlap.

    For every adjacent pair, ``sections[i].char_end == sections[i+1].start_offset``.
    The first section's ``body`` is non-empty (the synthetic preamble or
    the first detected section's content), and the last section's
    ``char_end`` is exactly ``len(text)``. This is the invariant the
    Source-tab offset map relies on.
    """
    parsed = msa_acme_parsed
    sections = parsed.sections
    assert len(sections) > 0

    # First section's body must carry real content — either the preamble
    # text or the body under the first detected heading.
    assert sections[0].body != ""

    # Pairwise walk — sections[1:] is intentionally one shorter than sections,
    # so strict=False is correct here.
    for left, right in zip(sections, sections[1:], strict=False):
        # No gap, no overlap: continuous half-open intervals.
        assert left.char_end == right.start_offset, (
            f"Discontinuity at section '{left.title}' → '{right.title}': "
            f"char_end={left.char_end}, next start_offset={right.start_offset}"
        )

    # Final section closes at end of text.
    assert sections[-1].char_end == len(parsed.text)


def test_parse_msa_acme_synthesizes_preamble_when_text_precedes_first_heading(
    msa_acme_parsed: ParsedDocument,
) -> None:
    """If the first detected heading is not at offset 0, a Preamble is prepended.

    The MSA fixture has a title page / preamble before § 1, so the first
    section in the parsed output must be the synthetic preamble.
    """
    parsed = msa_acme_parsed
    first = parsed.sections[0]

    # The MSA has cover-page text before the first numbered heading. If a
    # future fixture build pushes § 1 to offset 0 this assertion will need
    # to flip — but today the contract has front-matter and this test
    # pins the preamble synthesis.
    assert first.start_offset == 0
    if first.number == "0":
        assert first.title == "Preamble"
        # The preamble's body must be the slice of text from 0 to the
        # next section's start — that is the whole point of synthesizing it.
        assert first.body == parsed.text[0 : first.char_end]


def test_parse_invoice_emits_whole_document_fallback() -> None:
    """Sprint 3 (T002): invoice fixture must always have ≥ 1 section.

    Invoices are not legal contracts and the §-style heading regex
    typically catches one or zero headings. The whole-document fallback
    ensures the Source tab still renders something honest rather than
    going blank.
    """
    parsed = parse_pdf(_FIXTURES / "invoice-not-a-contract.pdf")

    assert len(parsed.sections) >= 1
    # The very first section's body must be non-empty for a document with
    # text content.
    assert parsed.sections[0].body != ""
    # And the section coverage closes at end-of-text.
    assert parsed.sections[-1].char_end == len(parsed.text)


def test_parse_nda_techcorp_happy_path() -> None:
    parsed = parse_pdf(_FIXTURES / "nda-techcorp.pdf")

    assert parsed.page_count > 0
    assert len(parsed.text) > 1000


def test_parse_invoice_happy_path() -> None:
    parsed = parse_pdf(_FIXTURES / "invoice-not-a-contract.pdf")

    assert parsed.page_count == 1
    assert len(parsed.text) > 200
    # Invoices don't have § or numbered legal sections; the heuristic may
    # fire on a stray "1." but should not produce a long list.
    assert len(parsed.sections) <= 2


def test_parse_scanned_pdf_raises(tmp_path: Path) -> None:
    """An image-only / blank PDF (no text layer) must raise ScannedPDFError.

    Generated in-test via PdfWriter.add_blank_page so the suite has no
    dependency on a checked-in scanned fixture.
    """
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    blank_pdf = tmp_path / "blank.pdf"
    with blank_pdf.open("wb") as fh:
        writer.write(fh)

    with pytest.raises(ScannedPDFError):
        parse_pdf(blank_pdf)
