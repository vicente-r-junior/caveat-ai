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

from caveat.llm.ollama_client import OllamaError, OllamaUnreachableError
from caveat.pipeline.analyze import analyze
from caveat.pipeline.classify import classify
from caveat.pipeline.client_summary import build_client_summary
from caveat.pipeline.load_playbook import load_playbook
from caveat.storage import db

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


class FindingOut(BaseModel):
    """A single risk finding as returned to the client.

    ``redline`` is allowed to be empty when the model declined to draft
    one — the pipeline does not invent redlines, per Constitution III.
    """

    severity: str
    title: str
    quote: str
    explanation: str
    redline: str = ""


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
    (citation retries, malformed JSON, etc.). ``elapsed_seconds`` surfaces
    the 60-second performance budget without enforcing it (Constitution VII).
    """

    document_id: str
    contract_type: str
    findings: list[FindingOut]
    client_summary: ClientSummaryOut
    warnings: list[str]
    elapsed_seconds: float


def _finding_to_out(finding: Any) -> FindingOut:
    """Convert a pipeline ``Finding`` dataclass into the response model."""
    return FindingOut(
        severity=finding.severity,
        title=finding.title,
        quote=finding.quote,
        explanation=finding.explanation,
        redline=finding.redline,
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

    elapsed = time.perf_counter() - start

    return AnalyzeResponse(
        document_id=document_id,
        contract_type=contract_type,
        findings=[_finding_to_out(f) for f in analysis_result.findings],
        client_summary=ClientSummaryOut(
            what_this_contract_is=summary.what_this_contract_is,
            what_youre_committing_to=summary.what_youre_committing_to,
            biggest_risks=list(summary.biggest_risks),
            recommendation=summary.recommendation,
            disclaimer=summary.disclaimer,
        ),
        # Merge analyze + client_summary warnings into a single channel.
        # Both stages emit Constitution VI signals (silent-empty findings,
        # malformed JSON, per-field fallback) and the lawyer needs both.
        warnings=list(analysis_result.warnings) + list(summary_warnings),
        elapsed_seconds=elapsed,
    )
