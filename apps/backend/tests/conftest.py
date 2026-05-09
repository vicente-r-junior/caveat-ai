"""Constitutional no-network guard for the backend test suite.

This conftest installs an **autouse, session-scoped** fixture that monkey-patches
every HTTP egress path used (or potentially used) by Caveat AI so that any attempt
to reach a non-localhost host raises ``RuntimeError`` immediately. It is the named
enforcement of:

- Constitution I — *Local-only by construction*: the application MUST function
  identically with the network interface disabled. Any code path that would fail
  without network access is a bug.
- Specification NFR-001 — *Privacy*: zero network requests MUST be made by the
  application after model download is complete.

What it patches:

1. ``httpx.Client.send`` — sync httpx requests (used by the Ollama client and any
   future sync HTTP code).
2. ``httpx.AsyncClient.send`` — async httpx requests (defensive: not currently used
   but covers any future async HTTP path).
3. ``requests.adapters.HTTPAdapter.send`` — applied conditionally because
   ``requests`` is not in ``pyproject.toml``. If a future task adds it, the patch
   activates automatically.
4. ``urllib.request.urlopen`` — defensive coverage for any stdlib HTTP usage.

Allowed hosts (the only hosts that may be contacted from inside the test suite):

- ``localhost``
- ``127.0.0.1``
- ``::1``

Anything else raises ``RuntimeError`` with the message
``"Constitution I violation: blocked outbound request to <host>"``.

The fixture is *session-scoped* and *autouse*, so it applies to every test under
``apps/backend/tests/`` (both ``unit/`` and ``e2e/``) without any opt-in. Originals
are restored at session teardown.

What it does NOT block:

- FastAPI's ``TestClient`` — Starlette's ``TestClient`` subclasses
  ``httpx.Client`` and dispatches through ``Client.send``, but the underlying
  transport is an in-process ``ASGITransport`` that never opens a socket.
  We detect that transport explicitly and let those calls pass. As a
  belt-and-suspenders check we also allow the special host ``testserver``,
  which is the well-known constant Starlette uses for the test base URL.

Positive test:

The explicit positive test of this fixture lives in
``tests/unit/test_no_network_guard.py`` (task T032). That test asserts that any
code path that tries ``httpx.get("https://example.com")`` (or similar) raises
``RuntimeError`` under this fixture. Together they form the belt-and-suspenders
guarantee that the lawyer's data never leaves the machine during testing.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
import pytest

# The only hosts allowed to be contacted from the test suite. Anything else is
# a Constitution I violation.
#
# ``testserver`` is the default base host used by Starlette's ``TestClient``
# when it dispatches in-process ASGI calls through httpx; the underlying
# transport is ``ASGITransport`` (no socket), so allowing this host is safe
# and required for the existing FastAPI tests to keep working.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "testserver"})


def _is_in_process_transport(client: Any) -> bool:
    """Return True if *client*'s transport is httpx's in-process ASGI transport.

    ``httpx.ASGITransport`` and Starlette's ``_TestClientTransport`` (a subclass
    of ``ASGITransport``) never open a socket — they call the ASGI app
    directly. Requests dispatched through such a transport are by definition
    local and must be allowed.
    """
    transport = getattr(client, "_transport", None)
    if transport is None:
        return False
    asgi_transport = getattr(httpx, "ASGITransport", None)
    if asgi_transport is not None and isinstance(transport, asgi_transport):
        return True
    # Defensive fall-through: match by class name in case Starlette wraps
    # things differently in some versions.
    return type(transport).__name__ in {"ASGITransport", "_TestClientTransport"}


def _extract_host(url: Any) -> str | None:
    """Return the lowercase host of *url*, or ``None`` if it cannot be determined.

    Handles ``httpx.URL`` objects (which expose ``.host``), plain strings, and
    anything else that ``urlparse`` can chew on. ``None`` is returned only when
    no host is present at all (e.g., a relative path); the caller treats that
    as not-a-network-request and lets it through.
    """
    if url is None:
        return None
    host = getattr(url, "host", None)
    if host:
        return str(host).lower()
    parsed = urlparse(str(url))
    if parsed.hostname:
        return parsed.hostname.lower()
    # ``urlparse`` returns netloc when there's no scheme; fall back to that
    # stripped of any user-info or port.
    netloc = parsed.netloc
    if netloc:
        if "@" in netloc:
            netloc = netloc.split("@", 1)[1]
        if ":" in netloc:
            netloc = netloc.split(":", 1)[0]
        return netloc.lower() or None
    return None


def _assert_local_url(url: Any) -> None:
    """Raise ``RuntimeError`` if *url*'s host is not in the local allowlist.

    A URL with no host (e.g., a relative path or in-process ASGI request) is
    treated as local and allowed through; the network transport itself will
    decide what to do with it.
    """
    host = _extract_host(url)
    if host is None:
        return
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(f"Constitution I violation: blocked outbound request to {host}")


@pytest.fixture(autouse=True, scope="session")
def _no_network_guard() -> Any:
    """Autouse session-scoped fixture that blocks all non-localhost HTTP.

    Patches httpx (sync + async), requests (if installed), and
    ``urllib.request.urlopen``. Yields, then restores the originals at session
    teardown.
    """
    # ----- Save originals --------------------------------------------------
    original_httpx_send = httpx.Client.send
    original_httpx_async_send = httpx.AsyncClient.send

    # ----- httpx.Client.send (sync) ---------------------------------------
    def guarded_httpx_send(
        self: httpx.Client,
        request: httpx.Request,
        *args: Any,
        **kwargs: Any,
    ) -> httpx.Response:
        if not _is_in_process_transport(self):
            _assert_local_url(request.url)
        return original_httpx_send(self, request, *args, **kwargs)

    httpx.Client.send = guarded_httpx_send  # type: ignore[method-assign]

    # ----- httpx.AsyncClient.send (async) ---------------------------------
    async def guarded_httpx_async_send(
        self: httpx.AsyncClient,
        request: httpx.Request,
        *args: Any,
        **kwargs: Any,
    ) -> httpx.Response:
        if not _is_in_process_transport(self):
            _assert_local_url(request.url)
        return await original_httpx_async_send(self, request, *args, **kwargs)

    httpx.AsyncClient.send = guarded_httpx_async_send  # type: ignore[method-assign]

    # ----- requests (conditional — not in pyproject.toml) -----------------
    original_requests_send = None
    requests_module = None
    try:
        import requests  # type: ignore[import-untyped, unused-ignore]
        from requests.adapters import HTTPAdapter  # type: ignore[import-untyped, unused-ignore]

        requests_module = requests
        original_requests_send = HTTPAdapter.send

        def guarded_requests_send(
            self: Any,
            request: Any,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            _assert_local_url(getattr(request, "url", None))
            return original_requests_send(self, request, *args, **kwargs)

        HTTPAdapter.send = guarded_requests_send  # type: ignore[method-assign, unused-ignore]
    except ImportError:
        # requests is not installed (it is not in pyproject.toml). The patch
        # is a no-op until some future task adds it as a dependency.
        pass

    # ----- urllib.request.urlopen (defensive) -----------------------------
    import urllib.request

    original_urlopen = urllib.request.urlopen

    def guarded_urlopen(url: Any, *args: Any, **kwargs: Any) -> Any:
        # ``url`` may be a string or a ``urllib.request.Request`` instance.
        target = getattr(url, "full_url", None) or url
        _assert_local_url(target)
        return original_urlopen(url, *args, **kwargs)

    urllib.request.urlopen = guarded_urlopen

    try:
        yield
    finally:
        # ----- Restore originals ------------------------------------------
        httpx.Client.send = original_httpx_send  # type: ignore[method-assign]
        httpx.AsyncClient.send = original_httpx_async_send  # type: ignore[method-assign]
        urllib.request.urlopen = original_urlopen
        if requests_module is not None and original_requests_send is not None:
            from requests.adapters import HTTPAdapter  # type: ignore[import-untyped, unused-ignore]

            HTTPAdapter.send = original_requests_send  # type: ignore[method-assign, unused-ignore]
