"""Unit tests for the playbook loader.

The loader is pure file I/O — no network, no LLM. These tests pin the shape
of the on-disk playbooks (so analyze.py knows what to feed the model) and
verify the case-insensitive lookup and minimal-fallback behavior.
"""

from __future__ import annotations

from typing import Any

from caveat.pipeline.load_playbook import load_playbook


def _assert_section_shape(section: dict[str, Any], section_name: str) -> None:
    """Each playbook section must carry the four fields analyze.py relies on."""
    for key in ("expected", "severity_if_missing", "description", "red_flags"):
        assert key in section, f"section {section_name!r} missing key {key!r}"


def test_load_msa_playbook() -> None:
    playbook = load_playbook("MSA")

    assert playbook["contract_type"] == "MSA"
    sections = playbook["sections"]

    # Every section the MSA playbook ships with must have the canonical shape.
    for required_section in (
        "liability_cap",
        "indemnification",
        "termination",
        "ip_ownership",
        "confidentiality",
        "governing_law",
        "dpa",
    ):
        assert required_section in sections, f"MSA playbook missing {required_section}"
        _assert_section_shape(sections[required_section], required_section)


def test_load_nda_playbook() -> None:
    playbook = load_playbook("NDA")

    assert playbook["contract_type"] == "NDA"
    sections = playbook["sections"]

    for required_section in (
        "confidential_information_scope",
        "term_and_survival",
        "return_or_destruction",
        "mutuality",
        "exceptions",
        "governing_law",
    ):
        assert required_section in sections, f"NDA playbook missing {required_section}"
        _assert_section_shape(sections[required_section], required_section)


def test_load_unknown_playbook_returns_minimal_fallback() -> None:
    playbook = load_playbook("Pizza")

    assert playbook["contract_type"] == "Pizza"
    assert playbook["sections"] == {}
    # Description should be present so the LLM prompt has something to read.
    assert "description" in playbook


def test_load_playbook_case_insensitive_lookup() -> None:
    """``msa`` and ``MSA`` must resolve to the same on-disk file."""
    upper = load_playbook("MSA")
    lower = load_playbook("msa")
    mixed = load_playbook("MsA")

    assert upper == lower == mixed
