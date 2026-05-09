"""Unit tests for the SQLite storage layer.

Each test gets a fresh DB file inside ``tmp_path`` — the storage helpers all
accept an explicit ``path=`` argument, so we never touch the developer's
real ``~/.caveat/data.db``.

Privacy-critical assertions: ``list_documents`` must NOT return the document
text (it is committed evidence in the SQLite schema but list views are
metadata-only).
"""

from __future__ import annotations

from pathlib import Path

from caveat.storage import db


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / "data.db"


def test_init_db_idempotent(tmp_path: Path) -> None:
    path = _db_path(tmp_path)
    db.init_db(path)
    # Second call must not raise; schema is created with IF NOT EXISTS.
    db.init_db(path)
    # And the schema is real: we can insert a document.
    doc_id = db.insert_document(
        filename="x.pdf", page_count=1, text="hello", path=path
    )
    assert isinstance(doc_id, str) and len(doc_id) > 0


def test_insert_and_get_document_round_trip(tmp_path: Path) -> None:
    path = _db_path(tmp_path)
    db.init_db(path)

    doc_id = db.insert_document(
        filename="contract.pdf",
        page_count=10,
        text="full contract text body here",
        contract_type="MSA",
        path=path,
    )

    fetched = db.get_document(doc_id, path=path)
    assert fetched is not None
    assert fetched["id"] == doc_id
    assert fetched["filename"] == "contract.pdf"
    assert fetched["page_count"] == 10
    assert fetched["text"] == "full contract text body here"
    assert fetched["contract_type"] == "MSA"
    assert "created_at" in fetched


def test_list_documents_excludes_text_field(tmp_path: Path) -> None:
    """Privacy: list views must not leak the full contract body."""
    path = _db_path(tmp_path)
    db.init_db(path)

    long_text = "Highly confidential client work product " * 200
    db.insert_document(
        filename="secret.pdf", page_count=20, text=long_text, path=path
    )

    rows = db.list_documents(path=path)
    assert len(rows) == 1
    assert "text" not in rows[0]
    # And the metadata fields are present.
    for key in ("id", "filename", "contract_type", "page_count", "created_at"):
        assert key in rows[0]


def test_delete_document_returns_true_then_false(tmp_path: Path) -> None:
    path = _db_path(tmp_path)
    db.init_db(path)

    doc_id = db.insert_document(filename="x.pdf", page_count=1, text="t", path=path)

    assert db.delete_document(doc_id, path=path) is True
    assert db.delete_document(doc_id, path=path) is False
    assert db.get_document(doc_id, path=path) is None


def test_update_document_type(tmp_path: Path) -> None:
    path = _db_path(tmp_path)
    db.init_db(path)

    doc_id = db.insert_document(
        filename="x.pdf", page_count=1, text="t", contract_type=None, path=path
    )
    fetched_before = db.get_document(doc_id, path=path)
    assert fetched_before is not None
    assert fetched_before["contract_type"] is None

    db.update_document_type(doc_id, "NDA", path=path)

    fetched_after = db.get_document(doc_id, path=path)
    assert fetched_after is not None
    assert fetched_after["contract_type"] == "NDA"


def test_insert_findings_round_trip(tmp_path: Path) -> None:
    path = _db_path(tmp_path)
    db.init_db(path)

    doc_id = db.insert_document(filename="x.pdf", page_count=1, text="t", path=path)
    findings = [
        {
            "severity": "high",
            "title": "Liability cap",
            "quote": "Q1",
            "explanation": "E1",
            "redline": "R1",
        },
        {
            "severity": "medium",
            "title": "Indemnity",
            "quote": "Q2",
            "explanation": "E2",
            "redline": "",
        },
        {
            "severity": "low",
            "title": "Governing law",
            "quote": "Q3",
            "explanation": "E3",
        },
    ]

    ids = db.insert_findings(doc_id, findings, path=path)
    assert len(ids) == 3

    rows = db.list_findings_for_document(doc_id, path=path)
    assert len(rows) == 3
    severities = {r["severity"] for r in rows}
    assert severities == {"high", "medium", "low"}
    titles = {r["title"] for r in rows}
    assert titles == {"Liability cap", "Indemnity", "Governing law"}


def test_insert_findings_empty_list_is_noop(tmp_path: Path) -> None:
    path = _db_path(tmp_path)
    db.init_db(path)

    doc_id = db.insert_document(filename="x.pdf", page_count=1, text="t", path=path)
    ids = db.insert_findings(doc_id, [], path=path)

    assert ids == []
    assert db.list_findings_for_document(doc_id, path=path) == []


def test_findings_cascade_on_document_delete(tmp_path: Path) -> None:
    """Deleting a document removes its findings via FK cascade."""
    path = _db_path(tmp_path)
    db.init_db(path)

    doc_id = db.insert_document(filename="x.pdf", page_count=1, text="t", path=path)
    db.insert_findings(
        doc_id,
        [
            {
                "severity": "high",
                "title": "A",
                "quote": "qa",
                "explanation": "ea",
            }
        ],
        path=path,
    )
    assert len(db.list_findings_for_document(doc_id, path=path)) == 1

    assert db.delete_document(doc_id, path=path) is True
    assert db.list_findings_for_document(doc_id, path=path) == []
