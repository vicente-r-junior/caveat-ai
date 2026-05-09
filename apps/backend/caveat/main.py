"""Caveat AI backend entrypoint.

Sprint 1 scope: the full document upload + analyse vertical slice. The
FastAPI app exposes ``/api/health``, ``/api/documents/*``, and
``/api/analyze/*``. Per Constitution I, the application performs no
outbound HTTP except via :mod:`caveat.llm.ollama_client` (locked to
``http://localhost:11434``).

CORS is narrowed to exactly the surface the Sprint 1/2 frontend uses:
methods are limited to ``GET``, ``POST``, ``DELETE``; headers to
``Content-Type``; and the only allowed origin is the Vite dev server at
``http://localhost:5173``. The wildcard surface from Sprint 0 is gone.

The SQLite schema is initialised on startup via
:func:`caveat.storage.db.init_db` so the first request after boot does
not race against a missing table.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from caveat.config import get_settings
from caveat.routers import analyze, documents, health
from caveat.storage.db import get_db_path, init_db

logger = logging.getLogger("caveat")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Initialise the SQLite schema BEFORE handing control to the app — any
    # request that arrives the moment the server is ready must find the
    # tables already present. ``init_db`` is idempotent, so calling it on
    # every startup is safe.
    init_db()
    settings = get_settings()
    logger.info(
        "caveat backend ready, model=%s, db=%s",
        settings.model_name,
        get_db_path(),
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Caveat AI", version="0.1.0", lifespan=lifespan)

    # Narrowed CORS surface for Sprint 1/2 (carry-forward from
    # sprint-0-validation.md). The Vite dev server at :5173 is the only
    # origin we expect, and the API only needs GET/POST/DELETE plus the
    # Content-Type header for multipart and JSON requests.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(analyze.router)
    return app


app = create_app()
