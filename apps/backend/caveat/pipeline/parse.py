"""PDF parsing for Caveat AI — text extraction + section detection.

This module turns a PDF on disk into a :class:`ParsedDocument`: the joined
text, the per-page text, a list of detected sections, and the page count.
It deliberately does NO OCR — scanned/image-only PDFs are rejected with a
:class:`ScannedPDFError` so the upload router can surface a clear 422 to
the user. Constitution VI: we would rather refuse than guess.

Per Constitution I (Local-only by construction), this module performs no
network I/O — it only reads the file the caller hands it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

# A scanned PDF will typically have effectively zero extracted text. We use
# 100 chars across the *whole* document as the floor below which we declare
# the document unreadable rather than try to bluff our way through it.
_MIN_TEXT_LEN = 100

# Section heading heuristic. Matches lines like:
#   "1. Definitions"
#   "2.1 Confidentiality"
#   "§ 4.2 Limitation of Liability"
#   "§4.2 Limitation of Liability"
# The leading optional "§" is allowed; numbering must be followed by at
# least one space and then a Capital-letter word so that we do not fire
# on inline references like "see 2.1 below".
_SECTION_RE = re.compile(r"^\s*(?:§\s*)?\d+(?:\.\d+)*\s+[A-Z][A-Za-z]")


class ScannedPDFError(Exception):
    """Raised when a PDF appears to be scanned/image-only (no text layer).

    The MVP does not perform OCR; the upload router catches this exception
    and returns HTTP 422 with the user-facing message attached here.
    """


@dataclass(slots=True, frozen=True)
class Section:
    """A detected section heading inside the contract.

    ``start_offset`` is the character offset of the heading inside the
    joined :attr:`ParsedDocument.text`. ``page`` is 1-indexed.
    """

    number: str
    title: str
    start_offset: int
    page: int


@dataclass(slots=True, frozen=True)
class ParsedDocument:
    """The output of :func:`parse_pdf` — a frozen, immutable record.

    ``text`` is ``"\\n\\n".join(pages)``: this is the canonical string the
    citation validator (Constitution II) checks quotes against.
    """

    text: str
    pages: tuple[str, ...]
    sections: tuple[Section, ...]
    page_count: int


def _detect_sections(pages: tuple[str, ...]) -> tuple[Section, ...]:
    """Walk every line of every page and emit a Section per matching heading.

    Uses a running offset that tracks where each page starts inside the
    joined ``"\\n\\n".join(pages)`` text. Pages are 1-indexed in the output.
    """
    sections: list[Section] = []
    cursor = 0
    page_separator = "\n\n"
    for page_index, page_text in enumerate(pages):
        page_number = page_index + 1
        # Walk each line and compute its offset inside the page, then
        # translate that to an offset inside the joined document text.
        line_offset = 0
        for line in page_text.split("\n"):
            stripped = line.strip()
            match = _SECTION_RE.match(line)
            if match and stripped:
                # Split heading into "number" and the remainder ("title").
                # The regex guarantees at least one space after the number.
                head = match.group(0)
                # Strip leading "§" + whitespace from the head, then split
                # on the first whitespace to separate number from title.
                head_clean = head.lstrip("§").strip()
                parts = head_clean.split(None, 1)
                number = parts[0]
                # The title in the matched prefix only contains the first
                # word; recover the rest of the line as the full title.
                full_title = stripped[len(head_clean) :].strip()
                if not full_title:
                    # Fall back to whatever the regex captured (a single
                    # capitalized word) so the title is never empty.
                    full_title = parts[1] if len(parts) > 1 else ""
                sections.append(
                    Section(
                        number=number,
                        title=full_title,
                        start_offset=cursor + line_offset,
                        page=page_number,
                    )
                )
            # +1 for the "\n" we split on.
            line_offset += len(line) + 1
        # Advance cursor past this page's text plus the separator that
        # join() will insert between this page and the next.
        cursor += len(page_text)
        if page_index < len(pages) - 1:
            cursor += len(page_separator)
    return tuple(sections)


def parse_pdf(path: Path) -> ParsedDocument:
    """Parse *path* into a :class:`ParsedDocument`.

    Raises
    ------
    ScannedPDFError
        If the total extracted text length is below :data:`_MIN_TEXT_LEN`,
        which the MVP treats as evidence the PDF is image-only.
    FileNotFoundError
        If *path* does not exist (propagated from :class:`PdfReader`).
    """
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        # ``extract_text`` returns ``None`` for pages with no text layer in
        # some pypdf versions; coerce to empty string so downstream code
        # never has to deal with ``None``.
        page_text = page.extract_text() or ""
        pages.append(page_text)

    pages_tuple = tuple(pages)
    text = "\n\n".join(pages_tuple)
    page_count = len(pages_tuple)

    if len(text.strip()) < _MIN_TEXT_LEN:
        raise ScannedPDFError(
            "This appears to be a scanned/image-only PDF. OCR is not "
            "supported in the MVP. Please upload a text-based PDF."
        )

    sections = _detect_sections(pages_tuple)
    return ParsedDocument(
        text=text,
        pages=pages_tuple,
        sections=sections,
        page_count=page_count,
    )
