"""Health check endpoint.

Returns the active model name so the frontend can confirm the backend
came up with the expected configuration. Does NOT call Ollama — per
Constitution I, this endpoint must work with the network disabled.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from caveat.config import get_settings

router = APIRouter(prefix="/api")


class HealthResponse(BaseModel):
    status: str
    model: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", model=settings.model_name)
