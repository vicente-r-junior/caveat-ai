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
    joined :attr:`ParsedDocument.text`. ``char_end`` is the offset of the
    next section's heading (or ``len(text)`` for the last section), so the
    half-open interval ``[start_offset, char_end)`` covers everything that
    belongs to this section, heading line included. ``body`` is the section
    content with the heading line stripped: it starts at the character
    immediately after the heading line's trailing newline (or equals
    ``""`` when the heading is the last line of the document) and runs to
    ``char_end``. ``page`` is 1-indexed.

    Sprint 3 (T002) added ``body`` and ``char_end`` so the source viewer
    can render section-by-section without re-deriving slices in the router
    (Constitution VI: surface what we already know rather than recompute).
    A synthetic ``Section(number="0", title="Preamble", ...)`` is emitted
    when text precedes the first detected heading, so ``source_sections``
    is always a complete cover of the document text — silently dropping
    pre-heading prose would violate Constitution VI.
    """

    number: str
    title: str
    start_offset: int
    page: int
    body: str
    char_end: int


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


@dataclass(slots=True, frozen=True)
class _SectionMarker:
    """Internal: a heading hit before body/char_end have been computed.

    Two-pass detection — first walk pages and emit one marker per heading
    line (cheap, line-by-line), then a second pass fills ``body`` and
    ``char_end`` by indexing into the already-joined document text.
    """

    number: str
    title: str
    start_offset: int
    page: int
    heading_line_end: int
    """Offset of the character immediately after the heading line's
    trailing ``\\n`` inside ``text``, or ``len(text)`` if the heading is
    the final line of the document. Used as the ``body`` start when the
    second pass fills in section bodies."""


def _detect_sections(pages: tuple[str, ...], text: str) -> tuple[Section, ...]:
    """Walk every line of every page and emit a Section per matching heading.

    The function is two-pass:

    1. Walk pages line-by-line and emit a :class:`_SectionMarker` per hit.
       The marker stashes the offset of the character immediately after
       the heading line's trailing newline so the second pass can carve
       the body without re-scanning the joined text.
    2. Post-process the marker list: each section's ``char_end`` is the
       next marker's ``start_offset`` (or ``len(text)`` for the last);
       its ``body`` is ``text[heading_line_end:char_end]``.

    Constitution VI corrections layered in here:

    * If any text precedes the first detected heading, prepend a synthetic
      preamble section so the document text is fully covered by
      ``source_sections``. Skipping the preamble would silently lose any
      recitals or front-matter the model legitimately quoted.
    * If zero headings were detected at all *and* the document still has
      text, emit a single whole-document fallback section so
      ``source_sections`` is never empty when the document has body text.
      This keeps the Source tab populated for outline-numbered contracts
      ("I.", "A.", "1.") that the regex was not tuned for.

    Pages are 1-indexed in the output.
    """
    markers: list[_SectionMarker] = []
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
                start_offset = cursor + line_offset
                # End of the heading line inside ``text``. ``line`` does
                # not include the trailing ``\n``; account for it by
                # adding 1, but cap at len(text) for the file's final line
                # which has no trailing newline.
                heading_line_end = min(start_offset + len(line) + 1, len(text))
                markers.append(
                    _SectionMarker(
                        number=number,
                        title=full_title,
                        start_offset=start_offset,
                        page=page_number,
                        heading_line_end=heading_line_end,
                    )
                )
            # +1 for the "\n" we split on.
            line_offset += len(line) + 1
        # Advance cursor past this page's text plus the separator that
        # join() will insert between this page and the next.
        cursor += len(page_text)
        if page_index < len(pages) - 1:
            cursor += len(page_separator)

    # ---- Second pass: fill body + char_end -------------------------------
    sections: list[Section] = []

    if markers:
        # Constitution VI: if any text precedes the first detected
        # heading, surface it as a synthetic preamble section so
        # source_sections covers the whole document. Recitals,
        # signature-block letterhead, and "WHEREAS" front-matter all
        # legitimately end up here on real contracts.
        first_offset = markers[0].start_offset
        if first_offset > 0:
            sections.append(
                Section(
                    number="0",
                    title="Preamble",
                    start_offset=0,
                    page=1,
                    body=text[0:first_offset],
                    char_end=first_offset,
                )
            )

        for index, marker in enumerate(markers):
            char_end = (
                markers[index + 1].start_offset
                if index + 1 < len(markers)
                else len(text)
            )
            # ``body`` excludes the heading line itself (everything from
            # the character after the heading's trailing ``\n`` up to the
            # next section's start). When the heading is the last line of
            # the document, ``heading_line_end == len(text)`` so the body
            # is an empty string — accurate, not a defect.
            body_start = min(marker.heading_line_end, char_end)
            sections.append(
                Section(
                    number=marker.number,
                    title=marker.title,
                    start_offset=marker.start_offset,
                    page=marker.page,
                    body=text[body_start:char_end],
                    char_end=char_end,
                )
            )
        return tuple(sections)

    # Zero headings detected. Emit a single whole-document fallback if
    # there is any text to cover so source_sections is never empty for a
    # readable document — Constitution VI: degraded-but-honest beats
    # silently-empty.
    if text:
        sections.append(
            Section(
                number="0",
                title="Document",
                start_offset=0,
                page=1,
                body=text,
                char_end=len(text),
            )
        )
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

    sections = _detect_sections(pages_tuple, text)
    return ParsedDocument(
        text=text,
        pages=pages_tuple,
        sections=sections,
        page_count=page_count,
    )
