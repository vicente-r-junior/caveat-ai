"""Contract-type classifier — wraps a single Ollama call.

Returns one of five US-relevant contract types. When the model is uncertain
or returns malformed output, the classifier defaults to ``"Other"`` rather
than guess (Constitution VI: honesty over polish).

Per Constitution I, all network I/O happens inside :mod:`caveat.llm.ollama_client`.
This module imports that seam and adds no other I/O of its own.
"""

from __future__ import annotations

from typing import Literal, get_args

from caveat.llm import ollama_client
from caveat.llm.prompts import build_classify_prompt

ContractType = Literal["MSA", "NDA", "SaaS", "Employment", "Other"]
"""The five contract types the MVP recognises. ``Other`` is the catch-all
returned whenever the model is uncertain or the response is malformed."""

_KNOWN_TYPES: frozenset[str] = frozenset(get_args(ContractType))


def classify(text: str) -> ContractType:
    """Classify *text* into one of :data:`ContractType`.

    The function calls Ollama once via :func:`caveat.llm.ollama_client.generate_json`
    and inspects the ``contract_type`` field of the response. If the value
    is not one of the recognised types, or if the model returns malformed
    JSON, the function returns ``"Other"``. Network errors are NOT swallowed
    — they propagate so the caller can surface them honestly (Constitution VI).
    """
    prompt = build_classify_prompt(text)
    try:
        response = ollama_client.generate_json(prompt)
    except ollama_client.OllamaInvalidJSONError:
        # Malformed JSON from the model is a soft failure for classification:
        # we fall back to "Other" rather than crash the upload pipeline.
        return "Other"

    raw = response.get("contract_type")
    if isinstance(raw, str) and raw in _KNOWN_TYPES:
        # ``raw in _KNOWN_TYPES`` narrows the value at runtime; mypy can't
        # see that, so we cast through Literal explicitly.
        return _coerce_known(raw)
    return "Other"


def _coerce_known(value: str) -> ContractType:
    """Cast a string already known to be in :data:`_KNOWN_TYPES` to ContractType.

    Centralised here so the cast assertion lives next to the membership check.
    """
    # Mypy cannot infer the Literal narrowing from ``in frozenset[str]``.
    # The runtime check above guarantees safety; this helper is the single
    # place we acknowledge the gap.
    if value == "MSA":
        return "MSA"
    if value == "NDA":
        return "NDA"
    if value == "SaaS":
        return "SaaS"
    if value == "Employment":
        return "Employment"
    return "Other"
