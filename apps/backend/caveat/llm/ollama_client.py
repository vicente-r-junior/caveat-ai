"""Ollama HTTP client — the single seam for every LLM call in Caveat AI.

Per Constitution I (Local-only by construction), this module is the *only*
place in the backend that performs outbound HTTP. It talks exclusively to
``http://localhost:11434`` (the Ollama daemon running on the lawyer's own
machine) and to no other host, ever. Any new LLM-related call must route
through this module so the prohibition on non-localhost traffic stays
trivially auditable.

Per Constitution VI (Honesty over polish), parsing failures surface as
explicit exceptions (:class:`OllamaInvalidJSONError`,
:class:`OllamaUnreachableError`, :class:`OllamaTimeoutError`) rather than
empty defaults. Callers are expected to handle them — silent retries are
the caller's decision, not this module's.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import httpx

from caveat.config import get_settings

OLLAMA_BASE_URL = "http://localhost:11434"
"""Hard-coded Ollama URL. Constitution I forbids any other host."""

_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=600.0, write=10.0, pool=5.0)
"""Generous read timeout: per Constitution VII a 30-page contract may take
~60s, so we give the pipeline meaningful headroom before declaring the
daemon hung.

Calibration note: 600s (10 minutes) is the **absolute ceiling for dev
hardware fallback**. Sprint 1 fixup-1 raised this from 120s to 300s for
analyze cold-start; Sprint 2 fixup-3 raises it again to 600s because the
*summary* stage on E4B / M4 Air 24GB sustains 150-200s wall-clock and
runs back-to-back with analyze in the same pipeline — the 300s ceiling
was tripping on the second call even when the first had used most of
the headroom. The production target (gemma4:31b-instruct-q4_K_M on
32GB+ RAM with a capable GPU) is well under 60s per stage, so this
ceiling is a fallback, not a target.

Per Constitution VI we'd rather wait visibly than fail with an opaque
ReadTimeout — and when we *do* time out, the pipeline catches
:class:`OllamaTimeoutError` and surfaces a structured warning rather
than letting the exception escape as an HTTP 500 with stack trace."""


class OllamaError(Exception):
    """Base class for all Ollama client failures."""


class OllamaUnreachableError(OllamaError):
    """Raised when the Ollama daemon cannot be contacted on localhost:11434."""


class OllamaTimeoutError(OllamaError):
    """Raised when Ollama exceeds the configured httpx timeout window.

    Wraps :class:`httpx.ReadTimeout`, :class:`httpx.ConnectTimeout`, and
    :class:`httpx.WriteTimeout` so callers (the pipeline stages) can
    distinguish a *slow* daemon from a *missing* one
    (:class:`OllamaUnreachableError`) and from a *malformed* response
    (:class:`OllamaInvalidJSONError`).

    Carries the elapsed seconds at the moment the timeout fired so the
    pipeline can build a verbatim warning that names the actual wait the
    user experienced (Constitution VI: surface, do not paper over).
    """

    def __init__(self, elapsed_seconds: float, timeout_kind: str) -> None:
        super().__init__(
            f"Ollama {timeout_kind} timeout after "
            f"{elapsed_seconds:.1f}s. The daemon is reachable but the model "
            "did not produce a response in time."
        )
        self.elapsed_seconds: float = elapsed_seconds
        self.timeout_kind: str = timeout_kind


class OllamaInvalidJSONError(OllamaError):
    """Raised when Ollama's response cannot be parsed as JSON.

    Carries the raw response so callers (and future logging) can show the
    user what the model actually returned instead of papering over it with
    an empty dict (Constitution VI).
    """

    def __init__(self, raw_response: str) -> None:
        super().__init__(
            "Ollama returned a response that is not valid JSON. "
            "See `raw_response` for the unparsed text."
        )
        self.raw_response: str = raw_response


_DEBUG_TRUNCATE_CHARS = 4000
"""Hard cap on how much prompt/response text the debug emitter will print.

The analyse prompt for a 30-page contract is ~50K characters; dumping the
whole thing on every call drowns the terminal. 4K is enough to see the
prompt header, the playbook, the first chunk of contract text, and the
JSON instructions — i.e. enough to confirm the prompt structure is sane
without flooding stderr."""


def _truncate_for_debug(s: str) -> str:
    if len(s) <= _DEBUG_TRUNCATE_CHARS:
        return s
    return f"{s[:_DEBUG_TRUNCATE_CHARS]}... [truncated {len(s) - _DEBUG_TRUNCATE_CHARS} chars]"


def _debug_emit(message: str) -> None:
    """Print *message* to stderr when ``CAVEAT_DEBUG_LLM`` is enabled.

    Uses ``print(..., file=sys.stderr)`` rather than the ``logging`` module
    because pytest's ``capsys`` reassigns ``sys.stderr`` per-test; a
    ``logging.StreamHandler(sys.stderr)`` would have captured the original
    stream at construction time and silently miss the redirected one. The
    flag is read each call so flipping ``CAVEAT_DEBUG_LLM`` and clearing
    the settings cache (in tests) takes effect without reimport.
    """
    if not get_settings().debug_llm:
        return
    print(f"[caveat.llm.debug] {message}", file=sys.stderr, flush=True)


def _resolve_model(model: str | None) -> str:
    if model is not None:
        return model
    return get_settings().model_name


def generate(
    prompt: str,
    *,
    model: str | None = None,
    format: str | None = None,
    options: dict[str, Any] | None = None,
) -> str:
    """Call Ollama's ``/api/generate`` endpoint and return the raw response text.

    Parameters
    ----------
    prompt:
        The full prompt string to send. Prompt construction happens in
        :mod:`caveat.llm.prompts`; this function does not template anything.
    model:
        Optional model override. Defaults to
        :attr:`caveat.config.Settings.model_name` (Gemma 4 e4b in dev,
        Gemma 4 31B in production per Constitution VIII).
    format:
        Optional Ollama format hint, e.g. ``"json"`` to request JSON-mode
        output.
    options:
        Optional Ollama generation options (``temperature``, ``num_ctx``,
        etc.).

    Returns
    -------
    str
        The contents of the ``response`` field from Ollama's JSON envelope.

    Raises
    ------
    OllamaUnreachableError
        If the Ollama daemon is not running on ``localhost:11434``.
    OllamaTimeoutError
        If the read/connect/write timeout fires before Ollama responds.
        Carries the elapsed wall-clock seconds so callers can surface a
        verbatim warning that names the actual wait the user endured.
    httpx.HTTPStatusError
        If Ollama returns a non-2xx status.
    """
    resolved_model = _resolve_model(model)
    payload: dict[str, Any] = {
        "model": resolved_model,
        "prompt": prompt,
        "stream": False,
    }
    if format is not None:
        payload["format"] = format
    if options is not None:
        payload["options"] = options

    _debug_emit(
        f"-> POST /api/generate model={resolved_model} format={format!r} "
        f"prompt_len={len(prompt)} prompt={_truncate_for_debug(prompt)!r}"
    )

    # Track wall-clock so OllamaTimeoutError can name the actual wait the
    # user experienced. httpx itself doesn't expose that on the exception.
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
    except httpx.ConnectError as exc:
        raise OllamaUnreachableError(
            "Ollama not reachable at http://localhost:11434 — "
            "is `ollama serve` running?"
        ) from exc
    except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout) as exc:
        # Map all three timeout flavours onto a single typed exception.
        # The pipeline stages (analyze, client_summary) catch this and
        # convert it into a structured warning per Constitution VI; the
        # router has a defensive fallback that returns 504 (never 500) if
        # somehow it slips past the pipeline.
        elapsed = time.perf_counter() - start
        kind = type(exc).__name__.removesuffix("Timeout").lower() or "read"
        raise OllamaTimeoutError(elapsed_seconds=elapsed, timeout_kind=kind) from exc

    response.raise_for_status()
    body: dict[str, Any] = response.json()
    text = body.get("response", "")
    if not isinstance(text, str):
        # Ollama always returns a string here; if it doesn't, surface it
        # rather than silently coerce (Constitution VI).
        raise OllamaError(
            f"Ollama returned a non-string `response` field: {type(text).__name__}"
        )
    _debug_emit(
        f"<- model={resolved_model} response_len={len(text)} "
        f"response={_truncate_for_debug(text)!r}"
    )
    return text


def generate_json(
    prompt: str,
    *,
    model: str | None = None,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call :func:`generate` in JSON mode and parse the response.

    The ``schema`` argument is reserved for a future Ollama feature
    (structured output / JSON schema constraint). Currently it is not
    forwarded to Ollama; we rely on prompt-side instructions plus the
    ``format="json"`` flag.

    Raises
    ------
    OllamaInvalidJSONError
        If the response cannot be decoded as JSON. The raw response text
        is attached to the exception so callers can decide how to surface
        it (Constitution VI: do not pretend the model said ``{}``).
    """
    del schema  # reserved for future use
    raw = generate(prompt, model=model, format="json")
    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Surface the offending substring around the parse position so the
        # human can see *where* Gemma drifted from JSON, not just that it
        # did. The full raw response is still on the exception for callers.
        snippet_start = max(0, exc.pos - 80)
        snippet_end = min(len(raw), exc.pos + 80)
        _debug_emit(
            f"!! JSON parse error at pos={exc.pos}: {exc.msg} | "
            f"context={raw[snippet_start:snippet_end]!r} | "
            f"raw_len={len(raw)}"
        )
        raise OllamaInvalidJSONError(raw) from exc
    if not isinstance(parsed, dict):
        _debug_emit(
            f"!! JSON parsed but is {type(parsed).__name__}, not dict; "
            f"raw={_truncate_for_debug(raw)!r}"
        )
        raise OllamaInvalidJSONError(raw)
    return parsed
