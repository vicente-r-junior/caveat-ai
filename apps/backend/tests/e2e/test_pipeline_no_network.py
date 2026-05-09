"""Named scenario: full pipeline runs under the no-network guard.

Constitution I, NFR-001. The same setup as the happy path in
``test_analyze_e2e.py``, but this file exists as a single, named test that
the validation report points at to prove the airplane-mode guarantee.

The autouse fixture in ``apps/backend/tests/conftest.py`` is active for
every test; the test itself ALSO explicitly attempts an external HTTP call
at the end so the guard's presence is visible in this file's assertions.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from caveat.config import get_settings
from caveat.llm import ollama_client
from caveat.main import create_app
from caveat.storage.db import init_db

_FIXTURES = Path(__file__).parents[3].parent / "fixtures" / "contracts"

_QUOTE_LIABILITY_CAP = (
    "THREE (3) MONTHS IMMEDIATELY PRECEDING THE EVENT GIVING RISE TO THE CLAIM"
)
_QUOTE_INDEMNITY = "Customer shall indemnify, defend, and hold harmless Provider"


def _finding(quote: str, *, title: str = "F") -> dict[str, Any]:
    return {
        "severity": "high",
        "title": title,
        "quote": quote,
        "explanation": "explanation",
        "redline": "",
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("CAVEAT_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    init_db(tmp_path / "data.db")

    with TestClient(create_app()) as test_client:
        yield test_client

    get_settings.cache_clear()


def test_full_analyze_pipeline_runs_under_no_network_guard(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pipeline must complete WITHOUT making any external HTTP request.

    The autouse no-network fixture is active; the pipeline still works
    because every Ollama call is mocked at the ``ollama_client.generate_json``
    boundary. The test passing AT ALL is the proof — but we also include
    an explicit ``Constitution I`` assertion at the end to make the guard's
    presence visible from this file.
    """
    pdf_bytes = (_FIXTURES / "msa-acme.pdf").read_bytes()
    upload = client.post(
        "/api/documents/",
        files={"file": ("msa-acme.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 200
    doc_id = upload.json()["document_id"]

    payloads: list[dict[str, Any]] = [
        {"contract_type": "MSA"},
        {
            "findings": [
                _finding(_QUOTE_LIABILITY_CAP, title="cap"),
                _finding(_QUOTE_INDEMNITY, title="indem"),
            ]
        },
        {
            "what_this_contract_is": "An MSA.",
            "what_youre_committing_to": "Pay fees.",
            "biggest_risks": ["Low cap", "One-way indemnity", "No DPA"],
            "recommendation": "Negotiate.",
        },
    ]
    responses = iter(payloads)

    def _fake(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return next(responses)

    monkeypatch.setattr(ollama_client, "generate_json", _fake)

    response = client.post(f"/api/analyze/{doc_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contract_type"] == "MSA"
    assert len(body["findings"]) == 2

    # Belt-and-suspenders: explicitly try to reach an external host. The
    # guard MUST raise — otherwise the airplane-mode guarantee is broken.
    with pytest.raises(RuntimeError, match="Constitution I"):
        httpx.get("https://example.com")
