"""Playbook loader — pure file I/O, no network.

Reads ``caveat/playbooks/{contract_type.lower()}.json`` and returns the
parsed dict. If a playbook for the requested type does not exist on disk,
falls back to a built-in minimal playbook so the pipeline can keep
functioning on unknown contract types (Constitution VI: degrade gracefully).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PLAYBOOK_DIR = Path(__file__).parent.parent / "playbooks"


def load_playbook(contract_type: str) -> dict[str, Any]:
    """Load the playbook JSON for *contract_type* (e.g., ``"MSA"`` -> ``msa.json``).

    Returns the parsed dict on a hit. On a miss (no file on disk for this
    contract type), returns a minimal built-in playbook with an empty
    ``sections`` map. The fallback IS the contract — callers do not need
    to handle a missing-playbook case.
    """
    path = _PLAYBOOK_DIR / f"{contract_type.lower()}.json"
    if path.exists():
        loaded: Any = json.loads(path.read_text())
        if isinstance(loaded, dict):
            # Narrow Any -> dict[str, Any] for mypy strict mode.
            return dict(loaded)
    return {
        "contract_type": contract_type,
        "description": "Generic playbook (no specialized rules for this type)",
        "sections": {},
    }
