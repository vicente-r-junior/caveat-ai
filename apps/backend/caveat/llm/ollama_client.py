"""Ollama HTTP client — the single seam for every LLM call in Caveat AI.

Per Constitution I (Local-only by construction), this module is the *only*
place in the backend that performs outbound HTTP. It talks exclusively to
``http://localhost:11434`` (the Ollama daemon running on the lawyer's own
machine) and to no other host, ever. Any new LLM-related call must route
through this module so the prohibition on non-localhost traffic stays
trivially auditable.

Per Constitution VI (Honesty over polish), parsing failures surface as
explicit exceptions (:class:`OllamaInvalidJSONError`,
:class:`OllamaUnreachableError`) rather than empty defaults. Callers are
expected to handle them — silent retries are the caller's decision, not
this module's.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from caveat.config import get_settings

OLLAMA_BASE_URL = "http://localhost:11434"
"""Hard-coded Ollama URL. Constitution I forbids any other host."""

_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
"""Generous read timeout: per Constitution VII a 30-page contract may take
~60s, so we give the pipeline meaningful headroom before declaring the
daemon hung."""


class OllamaError(Exception):
    """Base class for all Ollama client failures."""


class OllamaUnreachableError(OllamaError):
    """Raised when the Ollama daemon cannot be contacted on localhost:11434."""


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
    httpx.HTTPStatusError
        If Ollama returns a non-2xx status.
    """
    payload: dict[str, Any] = {
        "model": _resolve_model(model),
        "prompt": prompt,
        "stream": False,
    }
    if format is not None:
        payload["format"] = format
    if options is not None:
        payload["options"] = options

    try:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
    except httpx.ConnectError as exc:
        raise OllamaUnreachableError(
            "Ollama not reachable at http://localhost:11434 — "
            "is `ollama serve` running?"
        ) from exc

    response.raise_for_status()
    body: dict[str, Any] = response.json()
    text = body.get("response", "")
    if not isinstance(text, str):
        # Ollama always returns a string here; if it doesn't, surface it
        # rather than silently coerce (Constitution VI).
        raise OllamaError(
            f"Ollama returned a non-string `response` field: {type(text).__name__}"
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
        raise OllamaInvalidJSONError(raw) from exc
    if not isinstance(parsed, dict):
        raise OllamaInvalidJSONError(raw)
    return parsed
