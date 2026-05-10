"""Unit tests for the Ollama HTTP client.

The client is the single seam for every LLM call (Constitution I). Tests
verify that:

1. URLs are hard-coded to ``http://localhost:11434``.
2. The configured model name is forwarded.
3. ``generate_json`` enforces ``format="json"`` and rejects non-object responses.
4. Connection failures surface as :class:`OllamaUnreachableError` so callers
   can return a clean 503 (Constitution VI: do not paper over daemon-down).

These tests run under the autouse no-network fixture, but we patch
``httpx.Client`` itself so requests are intercepted before they ever reach
the wire — the no-network guard is belt-and-suspenders.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from caveat.config import get_settings
from caveat.llm import ollama_client
from caveat.llm.ollama_client import (
    OLLAMA_BASE_URL,
    OllamaError,
    OllamaInvalidJSONError,
    OllamaTimeoutError,
    OllamaUnreachableError,
    generate,
    generate_json,
)


class _FakeResponse:
    """Stand-in for ``httpx.Response`` that captures status + body."""

    def __init__(self, json_body: dict[str, Any], status_code: int = 200) -> None:
        self._json = json_body
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "boom", request=httpx.Request("POST", "http://localhost"), response=self  # type: ignore[arg-type]
            )


class _FakeClient:
    """Minimal context-manager replacement for ``httpx.Client``.

    Records every ``post`` call so tests can assert on URL and body, and
    returns whatever response (or raises whatever exception) the test
    plugged in via the class-level ``response_factory``.
    """

    calls: list[dict[str, Any]] = []
    response_factory: Any = None  # set per-test; takes (url, json) -> _FakeResponse

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None

    def post(self, url: str, *, json: dict[str, Any]) -> _FakeResponse:
        type(self).calls.append({"url": url, "json": json})
        factory = type(self).response_factory
        if factory is None:
            return _FakeResponse({"response": ""})
        return factory(url, json)  # type: ignore[no-any-return]


@pytest.fixture(autouse=True)
def _reset_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install ``_FakeClient`` for every test in this module."""
    _FakeClient.calls = []
    _FakeClient.response_factory = None
    monkeypatch.setattr("caveat.llm.ollama_client.httpx.Client", _FakeClient)
    # Make sure settings are fresh — other tests may have mutated env.
    get_settings.cache_clear()


def test_generate_posts_to_localhost_with_configured_model() -> None:
    _FakeClient.response_factory = lambda _url, _json: _FakeResponse({"response": "ok"})
    expected_model = get_settings().model_name

    result = generate("hello")

    assert result == "ok"
    assert len(_FakeClient.calls) == 1
    call = _FakeClient.calls[0]
    assert call["url"] == f"{OLLAMA_BASE_URL}/api/generate"
    assert call["url"].startswith("http://localhost:11434")
    body = call["json"]
    assert body["model"] == expected_model
    assert body["prompt"] == "hello"
    assert body["stream"] is False


def test_generate_with_explicit_model_override() -> None:
    _FakeClient.response_factory = lambda _url, _json: _FakeResponse({"response": "ok"})

    generate("hi", model="gemma4:31b-instruct-q4_K_M")

    assert _FakeClient.calls[0]["json"]["model"] == "gemma4:31b-instruct-q4_K_M"


def test_generate_returns_response_field() -> None:
    _FakeClient.response_factory = lambda _url, _json: _FakeResponse(
        {"response": "hello world"}
    )

    assert generate("x") == "hello world"


def test_generate_raises_unreachable_on_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the Ollama daemon is down, surface a typed exception."""

    class _ConnectingClient:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        def __enter__(self) -> _ConnectingClient:
            return self

        def __exit__(self, *_exc: Any) -> None:
            return None

        def post(self, *_a: Any, **_k: Any) -> Any:
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("caveat.llm.ollama_client.httpx.Client", _ConnectingClient)

    with pytest.raises(OllamaUnreachableError):
        generate("x")


def _install_raising_client(
    monkeypatch: pytest.MonkeyPatch, exc_factory: Any
) -> None:
    """Install a fake httpx.Client whose ``.post`` raises *exc_factory()*."""

    class _RaisingClient:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        def __enter__(self) -> _RaisingClient:
            return self

        def __exit__(self, *_exc: Any) -> None:
            return None

        def post(self, *_a: Any, **_k: Any) -> Any:
            raise exc_factory()

    monkeypatch.setattr("caveat.llm.ollama_client.httpx.Client", _RaisingClient)


def test_generate_raises_typed_timeout_on_read_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """httpx.ReadTimeout becomes OllamaTimeoutError, not bare HTTP 500.

    Sprint 2 fixup-3: a raw httpx.ReadTimeout used to bubble out of the
    pipeline as HTTP 500 with stack trace (Constitution VI violation).
    The client now wraps it in :class:`OllamaTimeoutError`, which is a
    subclass of :class:`OllamaError` — the pipeline stages catch the
    typed variant and surface a structured warning, while the router has
    a defensive 504 fallback.
    """
    _install_raising_client(monkeypatch, lambda: httpx.ReadTimeout("read timed out"))

    with pytest.raises(OllamaTimeoutError) as excinfo:
        generate("x")

    assert isinstance(excinfo.value, OllamaError)
    assert excinfo.value.timeout_kind == "read"
    # Elapsed seconds must be present and non-negative; a real timeout
    # would carry the actual wait, but the fake client returns instantly
    # so we just pin the contract that the field exists and is numeric.
    assert excinfo.value.elapsed_seconds >= 0.0
    # The exception message should be self-explanatory enough to land in
    # the FastAPI 504 detail without further formatting.
    msg = str(excinfo.value)
    assert "timeout" in msg.lower()


def test_generate_raises_typed_timeout_on_connect_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """httpx.ConnectTimeout maps to OllamaTimeoutError(kind='connect')."""
    _install_raising_client(
        monkeypatch, lambda: httpx.ConnectTimeout("connect timed out")
    )

    with pytest.raises(OllamaTimeoutError) as excinfo:
        generate("x")

    assert excinfo.value.timeout_kind == "connect"


def test_generate_raises_typed_timeout_on_write_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """httpx.WriteTimeout maps to OllamaTimeoutError(kind='write')."""
    _install_raising_client(
        monkeypatch, lambda: httpx.WriteTimeout("write timed out")
    )

    with pytest.raises(OllamaTimeoutError) as excinfo:
        generate("x")

    assert excinfo.value.timeout_kind == "write"


def test_generate_json_propagates_typed_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """generate_json must surface OllamaTimeoutError unchanged.

    The pipeline only ever calls ``generate_json``; if the wrapper
    swallowed the typed exception we'd be back to bare HTTP 500 in the
    router. Pin that the typed variant survives the JSON layer.
    """
    _install_raising_client(monkeypatch, lambda: httpx.ReadTimeout("slow"))

    with pytest.raises(OllamaTimeoutError):
        generate_json("prompt")


def test_generate_json_uses_format_json() -> None:
    _FakeClient.response_factory = lambda _url, _json: _FakeResponse(
        {"response": '{"key": "value"}'}
    )

    generate_json("prompt")

    assert _FakeClient.calls[0]["json"]["format"] == "json"


def test_generate_json_parses_string_response() -> None:
    _FakeClient.response_factory = lambda _url, _json: _FakeResponse(
        {"response": '{"key": "value", "n": 42}'}
    )

    parsed = generate_json("prompt")

    assert parsed == {"key": "value", "n": 42}


def test_generate_json_raises_on_invalid_json() -> None:
    _FakeClient.response_factory = lambda _url, _json: _FakeResponse(
        {"response": "this is not json"}
    )

    with pytest.raises(OllamaInvalidJSONError) as excinfo:
        generate_json("prompt")
    # Raw response is attached for the caller to surface.
    assert excinfo.value.raw_response == "this is not json"


def test_generate_json_rejects_non_object() -> None:
    """Valid JSON that is not an object (list, string, etc.) is invalid."""
    _FakeClient.response_factory = lambda _url, _json: _FakeResponse(
        {"response": '["a", "b"]'}
    )

    with pytest.raises(OllamaInvalidJSONError):
        generate_json("prompt")


def test_default_read_timeout_calibrated_for_e4b_cold_start() -> None:
    """The httpx read timeout must be 600s — the dev-hardware ceiling.

    Sprint 1 fixup-1 raised this from 120s to 300s after the analyze
    cold-start tripped at 120s. Sprint 2 fixup-3 raises it again to 600s
    because the *summary* stage (the longest in the pipeline) tripped the
    300s ceiling on E4B / M4 Air on the msa-acme.pdf fixture: analyze
    consumed ~150s and summary then sustained another 150-200s in the
    same pipeline run, so 300s gave summary essentially no headroom.

    600s is the **absolute ceiling for dev hardware fallback**, not a
    target. The production model (gemma4:31b on capable hardware) is
    well under 60s per stage. Pin the value here so a future "looks too
    long, let me lower it" tweak fails a test instead of the demo.
    """
    timeout = ollama_client._DEFAULT_TIMEOUT
    assert timeout.read == 600.0, f"expected read timeout 600s, got {timeout.read}"


# ---------------------------------------------------------------------------
# Sprint 1 fixup-2 — CAVEAT_DEBUG_LLM diagnostic flag.
#
# These tests pin that the debug flag is OFF by default (so test/CI output
# stays clean) and that flipping it produces visible stderr output with
# the prompt, the response, and JSON parse errors. The diagnostic surface
# is what made the silent-empty bug debuggable in the first place; it
# must keep working.
# ---------------------------------------------------------------------------


def test_debug_logging_silent_by_default(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With CAVEAT_DEBUG_LLM unset, no [caveat.llm.debug] lines hit stderr."""
    monkeypatch.delenv("CAVEAT_DEBUG_LLM", raising=False)
    get_settings.cache_clear()
    _FakeClient.response_factory = lambda _u, _j: _FakeResponse({"response": "hi"})

    generate("a unique prompt marker xyz123")

    captured = capsys.readouterr()
    assert "[caveat.llm.debug]" not in captured.err
    assert "xyz123" not in captured.err


def test_debug_logging_emits_prompt_and_response_when_enabled(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With CAVEAT_DEBUG_LLM=true, both directions are visible on stderr."""
    monkeypatch.setenv("CAVEAT_DEBUG_LLM", "true")
    get_settings.cache_clear()
    _FakeClient.response_factory = lambda _u, _j: _FakeResponse(
        {"response": "model-said-hi-back-MARKER"}
    )

    generate("prompt-marker-OUT")

    captured = capsys.readouterr()
    assert "[caveat.llm.debug]" in captured.err
    assert "prompt-marker-OUT" in captured.err
    assert "model-said-hi-back-MARKER" in captured.err


def test_debug_logging_truncates_long_payloads(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prompts/responses over the 4K cap are truncated; full text is not dumped.

    The analyse prompt for a 30-page contract is ~50K characters; without
    truncation the debug emitter would flood the terminal on every call
    and obscure the parse-error context that motivated the flag.
    """
    monkeypatch.setenv("CAVEAT_DEBUG_LLM", "true")
    get_settings.cache_clear()

    long_prompt = "X" * 5000
    _FakeClient.response_factory = lambda _u, _j: _FakeResponse({"response": "ok"})

    generate(long_prompt)

    captured = capsys.readouterr()
    assert "truncated" in captured.err
    # Full 5000-char string must not be present verbatim.
    assert long_prompt not in captured.err


def test_debug_logging_emits_json_parse_error_context(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """When generate_json hits a JSONDecodeError, the offending substring is logged.

    This is the single most useful piece of information when Gemma drifts
    from JSON: the bytes immediately around the parse failure point.
    """
    monkeypatch.setenv("CAVEAT_DEBUG_LLM", "true")
    get_settings.cache_clear()
    _FakeClient.response_factory = lambda _u, _j: _FakeResponse(
        {"response": '{"findings": [{"severity": "high",}]}'}  # trailing comma → invalid JSON
    )

    with pytest.raises(OllamaInvalidJSONError):
        generate_json("any prompt")

    captured = capsys.readouterr()
    assert "[caveat.llm.debug]" in captured.err
    assert "JSON parse error" in captured.err
    # The context substring includes characters from around the parse point.
    assert "findings" in captured.err or "severity" in captured.err
