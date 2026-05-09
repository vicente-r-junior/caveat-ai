"""Unit tests for the /api/health endpoint.

Constitution I: these tests must not touch the network. We use
FastAPI's TestClient, which calls the ASGI app in-process.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from caveat.config import get_settings
from caveat.main import create_app


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def test_health_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAVEAT_MODEL", raising=False)
    get_settings.cache_clear()

    client = TestClient(create_app())
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model": "gemma4:e4b"}


def test_health_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAVEAT_MODEL", "gemma4:31b-instruct-q4_K_M")
    get_settings.cache_clear()

    client = TestClient(create_app())
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model"] == "gemma4:31b-instruct-q4_K_M"
