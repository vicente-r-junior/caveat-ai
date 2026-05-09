"""Caveat AI backend entrypoint.

Sprint 0 scope: a FastAPI app exposing ``/api/health`` only. No Ollama
client, no pipeline, no storage. Per Constitution I, no outbound HTTP
of any kind is performed here.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from caveat.config import get_settings
from caveat.routers import health

logger = logging.getLogger("caveat")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("caveat backend ready, model=%s", settings.model_name)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Caveat AI", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    return app


app = create_app()
