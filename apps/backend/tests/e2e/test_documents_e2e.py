"""End-to-end tests for the /api/documents router.

Drives the real FastAPI app through ``TestClient`` (in-process ASGI — the
autouse no-network guard explicitly allows the in-process transport). Each
test gets an isolated SQLite DB inside ``tmp_path`` via ``CAVEAT_DATA_DIR``.

LLM is not exercised by this router — these tests cover upload, list, get,
delete, and the validation/size/scanned-PDF rejection paths.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from caveat.config import get_settings
from caveat.main import create_app
from caveat.storage import db
from caveat.storage.db import init_db

_FIXTURES = Path(__file__).parents[3].parent / "fixtures" / "contracts"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Yield a TestClient with an isolated DB pointed at ``tmp_path``."""
    monkeypatch.setenv("CAVEAT_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    init_db(tmp_path / "data.db")

    with TestClient(create_app()) as test_client:
        yield test_client

    get_settings.cache_clear()


def _upload_msa(client: TestClient) -> dict[str, object]:
    pdf_bytes = (_FIXTURES / "msa-acme.pdf").read_bytes()
    response = client.post(
        "/api/documents/",
        files={"file": ("msa-acme.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def test_upload_msa_acme_returns_document_id(client: TestClient) -> None:
    body = _upload_msa(client)

    assert isinstance(body["document_id"], str)
    assert len(body["document_id"]) > 0
    assert body["filename"] == "msa-acme.pdf"
    assert body["page_count"] == 8
    # Contract type is set on /analyze, not on upload.
    assert body["contract_type"] is None


def test_upload_persists_sections_for_msa_acme(
    client: TestClient, tmp_path: Path
) -> None:
    """Sprint 3 (T004): upload writes the parsed sections into SQLite.

    The Source tab depends on this — without a non-empty
    ``list_sections_for_document`` the analyse handler emits a
    Constitution VI warning and the Source tab renders empty.
    """
    body = _upload_msa(client)
    doc_id = body["document_id"]
    assert isinstance(doc_id, str)

    db_path = tmp_path / "data.db"
    sections = db.list_sections_for_document(doc_id, path=db_path)

    assert len(sections) > 0
    # Sections come back in idx order.
    assert [s["idx"] for s in sections] == sorted(s["idx"] for s in sections)
    # Every section row carries the required Sprint 3 columns.
    for section in sections:
        for key in ("idx", "number", "title", "body", "char_start", "char_end", "page"):
            assert key in section
    # And the first section's body is non-empty (real content, not a placeholder).
    assert sections[0]["body"] != ""


def test_list_documents_after_upload(client: TestClient) -> None:
    body = _upload_msa(client)
    doc_id = body["document_id"]

    response = client.get("/api/documents/")
    assert response.status_code == 200
    listing = response.json()
    assert isinstance(listing, list)
    assert any(item["id"] == doc_id for item in listing)
    # Privacy: list views never carry the full text.
    for item in listing:
        assert "text" not in item


def test_get_single_document_metadata(client: TestClient) -> None:
    body = _upload_msa(client)
    doc_id = body["document_id"]

    ok = client.get(f"/api/documents/{doc_id}")
    assert ok.status_code == 200
    meta = ok.json()
    assert meta["id"] == doc_id
    assert meta["filename"] == "msa-acme.pdf"

    missing = client.get("/api/documents/nope-not-real")
    assert missing.status_code == 404


def test_delete_document(client: TestClient) -> None:
    body = _upload_msa(client)
    doc_id = body["document_id"]

    first = client.delete(f"/api/documents/{doc_id}")
    assert first.status_code == 204

    second = client.delete(f"/api/documents/{doc_id}")
    assert second.status_code == 404


def test_upload_rejects_non_pdf_extension(client: TestClient) -> None:
    response = client.post(
        "/api/documents/",
        files={"file": ("hello.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 415


def test_upload_rejects_oversized_file(client: TestClient) -> None:
    big = b"x" * (11 * 1024 * 1024)
    response = client.post(
        "/api/documents/",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert response.status_code == 413


def test_upload_rejects_image_only_pdf(client: TestClient, tmp_path: Path) -> None:
    """A blank/image-only PDF must produce a 422 with the scanned-PDF message."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    blank_path = tmp_path / "blank.pdf"
    with blank_path.open("wb") as fh:
        writer.write(fh)

    response = client.post(
        "/api/documents/",
        files={"file": ("blank.pdf", blank_path.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 422
    detail = response.json()["detail"].lower()
    assert "scanned" in detail or "image-only" in detail
