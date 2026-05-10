"""Documents router — upload, list, fetch metadata, delete.

Implements the upload-side surface of User Story 1: a lawyer drops a PDF on
the app, the backend parses it locally, persists it, and hands back an id
the analyse endpoint can act on.

Spec references
---------------
* **FR-002** — Accept PDF uploads up to 10 MB; reject non-PDFs.
* **FR-003** — Persist documents locally so they survive across requests.
* **FR-015** — Enforce the 10 MB size cap with a clear user-facing error
  before doing any work.

Constitution
------------
* **I — Local-only by construction**: this router does NO outbound HTTP. It
  reads bytes from the request, hands them to :func:`caveat.pipeline.parse.parse_pdf`
  (pure local I/O), and persists through :mod:`caveat.storage.db` (SQLite).
  All future LLM work happens in the analyse pipeline, never here.
* **IV — Disclaimers are part of the product**: this router does not
  generate any analysis output, so no disclaimer is attached at this layer.
  The analyse endpoint owns that.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from pypdf.errors import PdfReadError

from caveat.pipeline.parse import ScannedPDFError, parse_pdf
from caveat.storage import db

router = APIRouter(prefix="/api/documents", tags=["documents"])

# FR-015: hard cap on PDF upload size. 10 MB is enough for almost every
# transactional contract; anything larger is almost certainly a scanned
# document or a packet of supporting exhibits we cannot analyse anyway.
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class DocumentResponse(BaseModel):
    """Returned by ``POST /api/documents`` after a successful upload."""

    document_id: str
    filename: str
    page_count: int
    contract_type: str | None = None


class DocumentSummary(BaseModel):
    """Metadata-only view of a stored document.

    Deliberately omits ``text`` — list views never leak the full contract
    body. Callers that need the text request the analyse endpoint, which
    pulls it from storage server-side without exposing it on a list.
    """

    id: str
    filename: str
    contract_type: str | None
    page_count: int
    created_at: str


def _is_pdf_upload(upload: UploadFile) -> bool:
    """Return True if *upload* declares itself a PDF.

    Accepts either ``application/pdf`` content-type or a ``.pdf`` extension
    (case-insensitive). The extension fallback covers the common case of
    browsers / curl users not setting a content type.
    """
    if upload.content_type == "application/pdf":
        return True
    filename = upload.filename or ""
    return filename.lower().endswith(".pdf")


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_200_OK)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
) -> DocumentResponse:
    """Accept a single PDF upload, parse it, persist it, return its id.

    Validation order matters: content-type/extension check first (cheapest),
    then size cap, then parse. We avoid touching the parser until we know
    the file is at least nominally a PDF and within the size budget.
    """
    if not _is_pdf_upload(file):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are accepted (.pdf)",
        )

    # Read the full body. ``UploadFile`` is backed by a SpooledTemporaryFile,
    # so this does not blow up memory for the 10 MB ceiling we enforce next.
    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="PDF exceeds 10 MB limit",
        )

    # Persist the bytes to a temp file because pypdf wants a path. We use
    # ``delete=False`` so we control the lifetime explicitly: parse_pdf
    # opens the path itself, and the ``finally`` block below removes the
    # file deterministically across platforms (Windows file-locking
    # disagrees with the auto-delete-on-close model).
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    try:
        try:
            parsed = parse_pdf(Path(tmp_path))
        except ScannedPDFError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        except (PdfReadError, ValueError, OSError) as exc:
            # Encrypted PDFs, malformed structures, and stream errors all
            # surface here. We give a clear "could not parse" message so the
            # lawyer knows it is a file problem rather than a tool bug.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Could not parse PDF: {exc}",
            ) from exc

        document_id = db.insert_document(
            filename=file.filename or "uploaded.pdf",
            page_count=parsed.page_count,
            text=parsed.text,
            contract_type=None,
        )
        return DocumentResponse(
            document_id=document_id,
            filename=file.filename or "uploaded.pdf",
            page_count=parsed.page_count,
            contract_type=None,
        )
    finally:
        # Best-effort cleanup; missing-file is fine because some failure
        # paths above may have already removed it.
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)


@router.get("/", response_model=list[DocumentSummary])
def list_documents() -> list[DocumentSummary]:
    """Return metadata for every stored document.

    Delegates to :func:`caveat.storage.db.list_documents`, which already
    excludes the ``text`` column by design.
    """
    rows = db.list_documents()
    return [DocumentSummary(**row) for row in rows]


@router.get("/{document_id}", response_model=DocumentSummary)
def get_document(document_id: str) -> DocumentSummary:
    """Return metadata for a single document, or 404 if it does not exist."""
    row = db.get_document(document_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return DocumentSummary(
        id=row["id"],
        filename=row["filename"],
        contract_type=row["contract_type"],
        page_count=row["page_count"],
        created_at=row["created_at"],
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str) -> Response:
    """Delete a document (cascade deletes its findings). 204 on success, 404 if missing."""
    removed = db.delete_document(document_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
