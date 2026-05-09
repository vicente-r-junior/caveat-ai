"""Explicit positive test of the autouse no-network guard.

This is the named scenario referenced by ``sprint-1-validation.md``: any
attempt to reach a host that is not localhost MUST raise ``RuntimeError``
with the message ``"Constitution I violation: blocked outbound request to ..."``.

The guard itself lives in ``apps/backend/tests/conftest.py`` and is
``autouse=True, scope="session"``. These tests both prove that the guard is
on and that it does not over-block — calls to ``localhost`` itself must be
allowed through (the guard rejects only NON-local hosts).

Constitution I — *Local-only by construction*. NFR-001.
"""

from __future__ import annotations

import asyncio
import urllib.error
import urllib.request

import httpx
import pytest


def test_httpx_get_to_external_host_blocked() -> None:
    with pytest.raises(RuntimeError, match="Constitution I"):
        httpx.get("https://example.com")


def test_httpx_async_to_external_host_blocked() -> None:
    async def _call() -> None:
        async with httpx.AsyncClient() as client:
            await client.get("https://example.com")

    with pytest.raises(RuntimeError, match="Constitution I"):
        asyncio.run(_call())


def test_httpx_to_localhost_allowed_to_attempt() -> None:
    """Localhost is allowed through — the guard rejects only non-local hosts.

    The request to localhost may succeed (if Ollama is running on this dev
    machine) or fail (if it isn't). EITHER outcome proves the guard let the
    call through; the only thing that would be wrong is the guard raising a
    Constitution I error for a localhost destination.
    """
    raised: BaseException | None = None
    try:
        # Use a tiny timeout so this never blocks the suite on a hung port.
        # We don't care about the response — just that the guard doesn't
        # block the request as a constitutional violation.
        httpx.get("http://localhost:11434/api/version", timeout=0.5)
    except BaseException as exc:  # noqa: BLE001 — broad on purpose
        raised = exc

    if raised is not None:
        # Acceptable: connect-refused, timeout, HTTP error, etc. The ONLY
        # unacceptable outcome is the Constitution I message.
        assert "Constitution I" not in str(raised), (
            "Localhost calls must pass through the no-network guard. The guard "
            f"incorrectly blocked a localhost request: {raised!r}"
        )


def test_urllib_to_external_host_blocked() -> None:
    """urllib is the stdlib HTTP path; it must also be guarded."""
    with pytest.raises((RuntimeError, urllib.error.URLError)) as excinfo:
        urllib.request.urlopen("https://example.com")  # noqa: S310

    # If urllib raised URLError instead of RuntimeError, the guard failed.
    assert "Constitution I" in str(excinfo.value)
