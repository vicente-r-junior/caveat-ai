"""SQLite persistence for Caveat AI documents and findings.

Plain ``sqlite3`` (stdlib) per the locked stack — no SQLAlchemy, no ORM.
All queries are parameterized. The database lives at
``<settings.data_dir>/data.db`` (default ``~/.caveat/data.db``).

Per Constitution I, this module performs no network I/O. Per the privacy
posture in :mod:`caveat`, :func:`list_documents` deliberately does NOT
return the full document text — list views show metadata only.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caveat.config import get_settings

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    contract_type TEXT,
    page_count INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    quote TEXT NOT NULL,
    explanation TEXT NOT NULL,
    redline TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_findings_doc ON findings(document_id);

CREATE TABLE IF NOT EXISTS sections (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    number TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    page INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sections_doc_idx ON sections(document_id, idx);
"""


# ---------------------------------------------------------------------------
# Path / connection helpers
# ---------------------------------------------------------------------------


def get_db_path() -> Path:
    """Return the SQLite file path, creating the parent directory if needed."""
    settings = get_settings()
    data_dir = settings.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "data.db"


def _connect(path: Path | None = None) -> sqlite3.Connection:
    """Open a connection with row-dict access and FK enforcement."""
    db_path = path if path is not None else get_db_path()
    # Ensure parent exists when caller passes an explicit path (e.g., tests
    # using a tmp_path subdirectory).
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None) -> None:
    """Create tables and indexes if absent. Idempotent — safe to call on every startup."""
    with _connect(path) as conn:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """ISO-8601 UTC timestamp with seconds precision."""
    return datetime.now(UTC).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    # ``sqlite3.Row`` exposes its columns through ``.keys()``; iterating
    # the row object itself yields values, not column names, so this is
    # the correct call here despite ruff's general SIM118 hint.
    return dict(zip(row.keys(), row, strict=True))


# ---------------------------------------------------------------------------
# Documents CRUD
# ---------------------------------------------------------------------------


def insert_document(
    *,
    filename: str,
    page_count: int,
    text: str,
    contract_type: str | None = None,
    path: Path | None = None,
) -> str:
    """Insert a parsed document. Returns the generated UUID4 id."""
    document_id = str(uuid.uuid4())
    created_at = _now_iso()
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO documents (id, filename, contract_type, page_count, text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (document_id, filename, contract_type, page_count, text, created_at),
        )
        conn.commit()
    return document_id


def get_document(document_id: str, path: Path | None = None) -> dict[str, Any] | None:
    """Return the full document row (including ``text``) or ``None``."""
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT id, filename, contract_type, page_count, text, created_at "
            "FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    return _row_to_dict(row) if row is not None else None


def list_documents(path: Path | None = None) -> list[dict[str, Any]]:
    """Return metadata for every document. **Excludes ``text``** by design.

    Privacy: list views never leak the full contract text. Callers that
    need the text must fetch a single document via :func:`get_document`.
    """
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT id, filename, contract_type, page_count, created_at "
            "FROM documents ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def delete_document(document_id: str, path: Path | None = None) -> bool:
    """Delete a document (and cascade to its findings). Returns True if a row was removed."""
    with _connect(path) as conn:
        cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()
        return cursor.rowcount > 0


def update_document_type(
    document_id: str,
    contract_type: str,
    path: Path | None = None,
) -> None:
    """Set or update the classified contract type for a document."""
    with _connect(path) as conn:
        conn.execute(
            "UPDATE documents SET contract_type = ? WHERE id = ?",
            (contract_type, document_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Findings CRUD
# ---------------------------------------------------------------------------


def insert_findings(
    document_id: str,
    findings: list[dict[str, Any]],
    path: Path | None = None,
) -> list[str]:
    """Bulk-insert findings for a document. Returns the generated ids in order.

    Each finding dict must contain at minimum: ``severity``, ``title``,
    ``quote``, ``explanation``. Optional: ``redline``, ``status``.
    """
    created_at = _now_iso()
    rows: list[tuple[str, str, str, str, str, str, str | None, str, str]] = []
    ids: list[str] = []
    for finding in findings:
        finding_id = str(uuid.uuid4())
        ids.append(finding_id)
        rows.append(
            (
                finding_id,
                document_id,
                str(finding["severity"]),
                str(finding["title"]),
                str(finding["quote"]),
                str(finding["explanation"]),
                finding.get("redline"),
                str(finding.get("status", "pending")),
                created_at,
            )
        )
    if not rows:
        return []
    with _connect(path) as conn:
        conn.executemany(
            """
            INSERT INTO findings
                (id, document_id, severity, title, quote, explanation, redline, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return ids


def list_findings_for_document(
    document_id: str,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return all findings for a document, oldest first."""
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT id, document_id, severity, title, quote, explanation, redline,
                   status, created_at
            FROM findings
            WHERE document_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (document_id,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Sections CRUD (Sprint 3 — T003)
# ---------------------------------------------------------------------------


def insert_sections(
    document_id: str,
    sections: list[dict[str, Any]],
    path: Path | None = None,
) -> list[str]:
    """Bulk-insert sections for a document. Returns generated ids in order.

    Each section dict must carry: ``idx``, ``number``, ``title``, ``body``,
    ``char_start``, ``char_end``, ``page``. Mirrors the shape of
    :func:`insert_findings`. An empty input returns ``[]`` without opening
    a write transaction — same fast-path as findings.

    Per Constitution VI, the upload router calls this best-effort: if the
    sections insert fails for some reason, the document row has already
    committed and the document remains usable (the analyse handler emits
    a warning when ``list_sections_for_document`` is empty). Better
    partial state than refusing the upload.
    """
    rows: list[tuple[str, str, int, str, str, str, int, int, int]] = []
    ids: list[str] = []
    for section in sections:
        section_id = str(uuid.uuid4())
        ids.append(section_id)
        rows.append(
            (
                section_id,
                document_id,
                int(section["idx"]),
                str(section["number"]),
                str(section["title"]),
                str(section["body"]),
                int(section["char_start"]),
                int(section["char_end"]),
                int(section["page"]),
            )
        )
    if not rows:
        return []
    with _connect(path) as conn:
        conn.executemany(
            """
            INSERT INTO sections
                (id, document_id, idx, number, title, body, char_start, char_end, page)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return ids


def list_sections_for_document(
    document_id: str,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return all sections for a document, sorted by ``idx`` ascending.

    The returned dicts include ``id``, ``document_id``, ``idx``,
    ``number``, ``title``, ``body``, ``char_start``, ``char_end``, ``page``.
    """
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT id, document_id, idx, number, title, body, char_start,
                   char_end, page
            FROM sections
            WHERE document_id = ?
            ORDER BY idx ASC
            """,
            (document_id,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]
