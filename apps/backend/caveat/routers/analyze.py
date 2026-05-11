"""Analyse router — runs the full pipeline on a stored document.

A single endpoint, ``POST /api/analyze/{document_id}``, walks the document
through the six pipeline stages: classify → load_playbook → analyze
(citation-validated) → build_client_summary → persist findings → respond.

Constitution
------------
* **VII — Performance budgets are real**: the 60-second budget for a
  30-page contract is *surfaced*, not enforced. We measure elapsed time
  via :func:`time.perf_counter` and return it on the response so the
  lawyer (and the validation suite) can see when the budget is being
  blown. We deliberately do NOT enforce a hard timeout: the M4 Air dev
  hardware can legitimately exceed 60s on the larger fallback model, and
  killing a near-complete analysis silently is a worse user experience
  than reporting an honest elapsed time.
* **VI — Honesty over polish**: the ``warnings`` field on the response
  is the channel for "this happened, you should know" signals from the
  pipeline (citation retries, malformed model JSON, etc.). The router
  forwards them verbatim — it does NOT prettify, drop, or de-dup them.
* **IV — Disclaimers are part of the product**: the disclaimer is a
  separate field on ``client_summary``, not concatenated into prose. The
  frontend renders it independently and exports preserve it as-is.
* **I — Local-only by construction**: the router itself does no network
  I/O. Every Ollama call funnels through the pipeline modules, which in
  turn use :mod:`caveat.llm.ollama_client` (locked to localhost:11434).
"""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from caveat.llm.ollama_client import (
    OllamaError,
    OllamaServerError,
    OllamaTimeoutError,
    OllamaUnreachableError,
)
from caveat.pipeline.analyze import analyze
from caveat.pipeline.classify import classify
from caveat.pipeline.client_summary import build_client_summary
from caveat.pipeline.load_playbook import load_playbook
from caveat.pipeline.map_offsets import FindingWithOffset, map_finding_offsets
from caveat.storage import db

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


class SourceOffset(BaseModel):
    """The character offsets of a finding's quote inside the source text.

    Sprint 3 (T006): the Source tab uses this to draw a highlight on the
    matching section. ``section_index`` matches the ``idx`` field of the
    :class:`SourceSection` the offset lives in. The interval is
    half-open: the highlight covers ``source_text[start:end]``.
    """

    section_index: int
    start: int
    end: int


class SourceSection(BaseModel):
    """A single parsed section of the contract, persisted at upload time.

    Surfaced on ``AnalyzeResponse`` so the Source tab can render the
    contract section-by-section without re-parsing on the client. The
    fields mirror the ``sections`` SQLite table 1:1 (T003).
    """

    idx: int
    number: str
    title: str
    body: str
    char_start: int
    char_end: int
    page: int


class FindingOut(BaseModel):
    """A single risk finding as returned to the client.

    ``redline`` is allowed to be empty when the model declined to draft
    one — the pipeline does not invent redlines, per Constitution III.

    ``source_offset`` is ``None`` when the offset stage could not locate
    the finding's quote inside the source text (rare — see
    :mod:`caveat.pipeline.map_offsets`). The corresponding warning is
    surfaced verbatim in :attr:`AnalyzeResponse.warnings` so the Source
    tab can render an honest "highlight missing" signal alongside.
    """

    severity: str
    title: str
    quote: str
    explanation: str
    redline: str = ""
    source_offset: SourceOffset | None = None


class ClientSummaryOut(BaseModel):
    """The four-section client memo plus the constitutional disclaimer.

    The disclaimer is a *separate field* (Constitution IV). It is not
    inlined into any of the prose fields so that exports can render it as
    a distinct, non-removable block.
    """

    what_this_contract_is: str
    what_youre_committing_to: str
    biggest_risks: list[str]
    recommendation: str
    disclaimer: str


class AnalyzeResponse(BaseModel):
    """Top-level response from ``POST /api/analyze/{document_id}``.

    ``warnings`` carries any honest-over-polish signals from the pipeline
    (citation retries, malformed JSON, un-located source offsets, etc.).
    Order is preserved: analyse-stage warnings, then summary-stage
    warnings, then offset-stage warnings — the same order they were
    produced. ``elapsed_seconds`` surfaces the 60-second performance
    budget without enforcing it (Constitution VII).

    Sprint 3 (T006): added ``source_sections`` so the Source tab can
    render the document section-by-section.
    """

    document_id: str
    contract_type: str
    findings: list[FindingOut]
    client_summary: ClientSummaryOut
    warnings: list[str]
    source_sections: list[SourceSection]
    elapsed_seconds: float


def _finding_to_out(located: FindingWithOffset) -> FindingOut:
    """Convert a :class:`FindingWithOffset` into the response model.

    The offset projection is the only Sprint 3 difference from the
    Sprint 2 surface; existing fields stay byte-identical.
    """
    finding = located.finding
    offset = located.source_offset
    return FindingOut(
        severity=finding.severity,
        title=finding.title,
        quote=finding.quote,
        explanation=finding.explanation,
        redline=finding.redline,
        source_offset=(
            SourceOffset(
                section_index=offset.section_index,
                start=offset.start,
                end=offset.end,
            )
            if offset is not None
            else None
        ),
    )


def _section_row_to_out(row: dict[str, Any]) -> SourceSection:
    """Convert a ``list_sections_for_document`` row into the response model."""
    return SourceSection(
        idx=int(row["idx"]),
        number=str(row["number"]),
        title=str(row["title"]),
        body=str(row["body"]),
        char_start=int(row["char_start"]),
        char_end=int(row["char_end"]),
        page=int(row["page"]),
    )


@router.post("/{document_id}", response_model=AnalyzeResponse)
def analyze_document(document_id: str) -> AnalyzeResponse:
    """Run the full analysis pipeline against a previously uploaded document.

    Steps:
      1. Load the document text from storage (404 if absent).
      2. Classify the contract type.
      3. Persist the classification so subsequent list/get views show it.
      4. Load the matching playbook.
      5. Run the analyse stage (Ollama call + citation validation).
      6. Build the client summary (second Ollama call).
      7. Persist the validated findings.
      8. Return the structured response.

    Errors are mapped per Constitution VI: connection failures to Ollama
    surface as 503 so the frontend can show "is Ollama running?", and any
    other Ollama-side failure surfaces as 502.
    """
    start = time.perf_counter()

    document = db.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    text: str = document["text"]

    try:
        contract_type = classify(text)
        db.update_document_type(document_id, contract_type)

        playbook = load_playbook(contract_type)
        analysis_result = analyze(text, contract_type, playbook)
        summary, summary_warnings = build_client_summary(
            analysis_result.findings, contract_type, text
        )
    except OllamaUnreachableError as exc:
        # Surface the daemon-down case explicitly so the frontend can render
        # a "Is Ollama running?" hint instead of a generic 5xx (Constitution VI).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OllamaTimeoutError as exc:
        # Belt-and-suspenders. Sprint 2 fixup-3: pipeline stages
        # (analyze.py, client_summary.py) catch OllamaTimeoutError and
        # convert it to a structured warning, so the router should
        # NEVER see this in normal operation. If it does — e.g. a future
        # pipeline stage forgets to wrap its Ollama call — surface 504
        # Gateway Timeout with a structured detail message rather than
        # letting it escape as HTTP 500 with a stack trace (Constitution
        # VI). 504 is the semantically correct status for "upstream
        # service we depend on did not respond in time".
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except OllamaServerError as exc:
        # Belt-and-suspenders. Sprint 2 fixup-4: pipeline stages absorb
        # OllamaServerError into a structured warning, so the router
        # should NEVER see this in normal operation. If it does — e.g. a
        # future pipeline stage forgets to wrap its Ollama call — surface
        # 502 Bad Gateway, which is the semantically correct status for
        # "upstream service we depend on returned an error response".
        # Never HTTP 500 with stack trace (Constitution VI).
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except OllamaError as exc:
        # Catches OllamaInvalidJSONError and any other Ollama-layer failure
        # the pipeline did not absorb into a warning. 502 is the correct
        # signal: an upstream service we depend on misbehaved.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    # Persist the validated findings BEFORE returning, so a subsequent
    # GET /api/documents/{id}/findings (Sprint 4) sees the same set.
    db.insert_findings(
        document_id,
        [asdict(f) for f in analysis_result.findings],
    )

    # Sprint 3 (T006): load persisted sections and map each finding's
    # quote to a (section_index, start, end) offset triple. This is what
    # the Source tab needs to draw highlights.
    sections_rows = db.list_sections_for_document(document_id)
    offset_warnings: tuple[str, ...] = ()
    if not sections_rows:
        # Constitution VI: documents uploaded BEFORE T004 landed have no
        # sections rows. Surface this rather than silently rendering an
        # empty Source tab. Re-uploading the document populates sections.
        located_findings: tuple[FindingWithOffset, ...] = tuple(
            FindingWithOffset(finding=f, source_offset=None)
            for f in analysis_result.findings
        )
        if analysis_result.findings or text:
            offset_warnings = (
                "Source viewer: this document was uploaded before section "
                "indexing was enabled. Source tab will be empty. Re-upload "
                "to enable highlights.",
            )
    else:
        located_findings, offset_warnings = map_finding_offsets(
            analysis_result.findings,
            tuple(sections_rows),
            text,
        )

    elapsed = time.perf_counter() - start

    return AnalyzeResponse(
        document_id=document_id,
        contract_type=contract_type,
        findings=[_finding_to_out(f) for f in located_findings],
        client_summary=ClientSummaryOut(
            what_this_contract_is=summary.what_this_contract_is,
            what_youre_committing_to=summary.what_youre_committing_to,
            biggest_risks=list(summary.biggest_risks),
            recommendation=summary.recommendation,
            disclaimer=summary.disclaimer,
        ),
        # Merge analyze + client_summary + offset warnings into a single
        # channel. All three stages emit Constitution VI signals
        # (silent-empty findings, malformed JSON, per-field fallback,
        # un-located highlights) and the lawyer needs all of them. The
        # ordering — analyze, then summary, then offsets — preserves the
        # Sprint 2 ordering and appends the new offset warnings at the
        # end so the Findings-tab warnings banner stays grouped.
        warnings=(
            list(analysis_result.warnings)
            + list(summary_warnings)
            + list(offset_warnings)
        ),
        source_sections=[_section_row_to_out(row) for row in sections_rows],
        elapsed_seconds=elapsed,
    )
