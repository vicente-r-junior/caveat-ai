"""End-to-end tests for the /api/analyze router.

Drives the full pipeline through the FastAPI app: upload → classify →
analyze → client_summary → response. The Ollama daemon is mocked at the
``caveat.llm.ollama_client.generate_json`` boundary because all three
pipeline modules call it via attribute access on the module.

The mocked findings use REAL verbatim quotes from msa-acme.pdf so the
citation validator's substring check actually exercises the realistic
contract text — not a synthetic stub.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from caveat.config import get_settings
from caveat.llm import ollama_client
from caveat.main import create_app
from caveat.storage import db
from caveat.storage.db import init_db

_FIXTURES = Path(__file__).parents[3].parent / "fixtures" / "contracts"

# Real verbatim substrings present in msa-acme.pdf. See test_analyze.py for
# the source-of-truth verification fixture.
_QUOTE_LIABILITY_CAP = (
    "THREE (3) MONTHS IMMEDIATELY PRECEDING THE EVENT GIVING RISE TO THE CLAIM"
)
_QUOTE_INDEMNITY = "Customer shall indemnify, defend, and hold harmless Provider"
_QUOTE_NO_REFUND = "no refund of prepaid fees shall be due to Customer"
_QUOTE_BAD = "This text does not appear in the contract anywhere"


def _finding(quote: str, *, severity: str = "high", title: str = "F") -> dict[str, Any]:
    return {
        "severity": severity,
        "title": title,
        "quote": quote,
        "explanation": "explanation text",
        "redline": "",
    }


def _summary_payload() -> dict[str, Any]:
    return {
        "what_this_contract_is": "An MSA between Acme and a customer.",
        "what_youre_committing_to": "Pay fees on time and follow the AUP.",
        "biggest_risks": ["Low cap", "One-way indemnity", "No DPA"],
        "recommendation": "Negotiate the cap and add a DPA before signing.",
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """TestClient with isolated DB pointed at ``tmp_path``."""
    monkeypatch.setenv("CAVEAT_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    init_db(tmp_path / "data.db")

    with TestClient(create_app()) as test_client:
        yield test_client

    get_settings.cache_clear()


def _upload_msa(client: TestClient) -> str:
    pdf_bytes = (_FIXTURES / "msa-acme.pdf").read_bytes()
    response = client.post(
        "/api/documents/",
        files={"file": ("msa-acme.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    doc_id = response.json()["document_id"]
    assert isinstance(doc_id, str)
    return doc_id


def _patch_pipeline_responses(
    monkeypatch: pytest.MonkeyPatch, responses: list[dict[str, Any]]
) -> None:
    """Plug a sequential list of canned JSON payloads into the LLM seam."""
    iterator = iter(responses)

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return next(iterator)

    monkeypatch.setattr(ollama_client, "generate_json", _fake)


def test_analyze_happy_path_returns_full_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc_id = _upload_msa(client)

    _patch_pipeline_responses(
        monkeypatch,
        [
            {"contract_type": "MSA"},
            {
                "findings": [
                    _finding(_QUOTE_LIABILITY_CAP, title="3-month cap"),
                    _finding(_QUOTE_INDEMNITY, title="One-way indemnity"),
                    _finding(_QUOTE_NO_REFUND, severity="medium", title="No refund"),
                ]
            },
            _summary_payload(),
        ],
    )

    response = client.post(f"/api/analyze/{doc_id}")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["document_id"] == doc_id
    assert body["contract_type"] == "MSA"
    assert len(body["findings"]) == 3
    titles = {f["title"] for f in body["findings"]}
    assert titles == {"3-month cap", "One-way indemnity", "No refund"}

    summary = body["client_summary"]
    assert summary["disclaimer"].strip() != ""
    assert "attorney review" in summary["disclaimer"]
    assert summary["biggest_risks"] == ["Low cap", "One-way indemnity", "No DPA"]

    assert body["warnings"] == []
    assert body["elapsed_seconds"] > 0


def test_analyze_returns_404_for_unknown_doc(client: TestClient) -> None:
    response = client.post("/api/analyze/this-id-does-not-exist")
    assert response.status_code == 404


def test_analyze_persists_findings_to_db(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc_id = _upload_msa(client)

    _patch_pipeline_responses(
        monkeypatch,
        [
            {"contract_type": "MSA"},
            {
                "findings": [
                    _finding(_QUOTE_LIABILITY_CAP, title="cap"),
                    _finding(_QUOTE_INDEMNITY, title="indem"),
                ]
            },
            _summary_payload(),
        ],
    )

    response = client.post(f"/api/analyze/{doc_id}")
    assert response.status_code == 200

    db_path = tmp_path / "data.db"
    persisted = db.list_findings_for_document(doc_id, path=db_path)
    assert len(persisted) == 2
    assert {f["title"] for f in persisted} == {"cap", "indem"}


def test_analyze_503_when_ollama_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc_id = _upload_msa(client)

    def _raise(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise ollama_client.OllamaUnreachableError(
            "Ollama not reachable at http://localhost:11434 — is `ollama serve` running?"
        )

    monkeypatch.setattr(ollama_client, "generate_json", _raise)

    response = client.post(f"/api/analyze/{doc_id}")
    assert response.status_code == 503
    detail = response.json()["detail"].lower()
    assert "ollama" in detail


def test_analyze_includes_warnings_field_when_pipeline_warns(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All-bad first call → retry → 2 valid → warnings list non-empty."""
    doc_id = _upload_msa(client)

    _patch_pipeline_responses(
        monkeypatch,
        [
            {"contract_type": "MSA"},
            # First analyze pass: all-bad quotes
            {"findings": [_finding(_QUOTE_BAD, title=f"bad-{i}") for i in range(4)]},
            # Retry: 2 valid quotes
            {
                "findings": [
                    _finding(_QUOTE_LIABILITY_CAP, title="rec-1"),
                    _finding(_QUOTE_INDEMNITY, title="rec-2"),
                ]
            },
            _summary_payload(),
        ],
    )

    response = client.post(f"/api/analyze/{doc_id}")
    assert response.status_code == 200

    body = response.json()
    assert len(body["findings"]) == 2
    assert isinstance(body["warnings"], list)
    assert len(body["warnings"]) >= 1
    # The retry warning string is the canonical Constitution VI signal.
    joined = " ".join(body["warnings"]).lower()
    assert "retried" in joined or "stricter" in joined
