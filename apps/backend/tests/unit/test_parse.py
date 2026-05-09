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
