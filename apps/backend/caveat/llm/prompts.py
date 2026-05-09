"""Prompt builders for every LLM call in Caveat AI.

All prompts live in this single module so they are reviewable, testable,
and version-controlled in one place. Each builder is a pure function that
takes structured inputs and returns the full prompt string — no I/O, no
side effects.

Constitutional guard rails baked into every prompt:

* **Constitution II — Citations are mandatory.** Findings must include a
  ``quote`` field that is a verbatim substring of the contract text. If
  the model cannot quote, it is told to omit the finding (the citation
  validator in :mod:`caveat.pipeline.validate_citations` enforces this
  downstream as a substring check).
* **Constitution III — The model does not invent.** The prompts forbid
  speculation about clauses or facts that are not in the supplied text.
* **Constitution VI — Honesty over polish.** When uncertain, the model is
  instructed to omit the finding or return ``Other``, never to guess.
* **Constitution IV — Disclaimers.** The client-summary prompt does NOT
  ask the model to author a disclaimer. The disclaimer is a non-removable
  constant attached by :mod:`caveat.pipeline.client_summary` (T020); the
  model must not generate, paraphrase, or omit it.
"""

from __future__ import annotations

import json
from typing import Any

CLASSIFY_TRUNCATE_CHARS = 8000
"""Classification only needs the opening pages — a contract's type is
almost always determinable from the first ~8K chars (title, recitals,
section 1)."""

CLIENT_SUMMARY_TRUNCATE_CHARS = 20000
"""Client summary works from the validated findings plus a bounded slice
of source text. The findings carry the verbatim quotes already; the
truncated source is context, not citation material."""


def build_classify_prompt(text: str) -> str:
    """Build the classification prompt.

    The model is asked to return strict JSON with one of five contract
    types. If it cannot determine the type, it MUST return ``"Other"``
    rather than guess (Constitution VI).
    """
    truncated = text[:CLASSIFY_TRUNCATE_CHARS]
    return f"""You are classifying a US legal document for a transactional lawyer.

Read the document text below and identify which type of contract it is.
Respond with EXACTLY ONE of these values:

- "MSA"          (Master Services Agreement, Master Service Agreement, or similar)
- "NDA"          (Non-Disclosure Agreement, Confidentiality Agreement)
- "SaaS"         (Software-as-a-Service agreement, subscription agreement)
- "Employment"   (employment contract, offer letter, severance agreement)
- "Other"        (anything that does not clearly fit one of the above, including
                  invoices, news articles, or documents that are not contracts)

If you cannot determine the type, return "Other". Do not guess.

Output strict JSON only, with no prose, no markdown, no code fences:

{{"contract_type": "MSA"}}

DOCUMENT TEXT:
\"\"\"
{truncated}
\"\"\"
"""


def build_analyze_prompt(
    text: str,
    contract_type: str,
    playbook: dict[str, Any],
) -> str:
    """Build the risk-analysis prompt.

    The model is told the contract type, given a US-norms playbook to
    check against, and instructed to return findings each with a verbatim
    ``quote`` field. The downstream citation validator drops any finding
    whose quote is not a literal substring of the source.
    """
    playbook_json = json.dumps(playbook, indent=2)
    return f"""You are a US transactional lawyer's assistant. You analyze contracts only
against US law conventions and customary US drafting practice. You do not
apply UK, EU, or any non-US legal framework.

Your job: review the {contract_type} contract text below and produce a list
of findings. A finding is a clause (or absence of a clause) that the
reviewing attorney needs to look at — high risk, off-market terms,
missing protections, or items that warrant negotiation.

NON-NEGOTIABLE RULES:

1. Every finding MUST include a `quote` field containing a VERBATIM
   substring from the contract text below. The quote must appear in the
   contract text exactly as you write it, character-for-character. If
   you cannot find a verbatim quote that supports the finding, OMIT the
   finding. Do not paraphrase. Do not summarize.

2. For "missing" findings (e.g., "no DPA reference"), set `severity` to
   "missing" and supply the closest related clause as the `quote` so the
   reviewer can locate the spot where the clause should appear. If no
   related clause exists at all, omit the finding.

3. Do not invent clauses. Speak only about what is in the contract text
   below. Do not introduce outside legal knowledge unless it is needed
   to explain a finding that is grounded in a verbatim quote.

4. If you are uncertain whether something is a finding, OMIT it. Do not
   guess. The reviewing attorney will catch what you miss; they cannot
   easily catch what you fabricate.

PLAYBOOK (US norms checklist for {contract_type}):
{playbook_json}

OUTPUT FORMAT — strict JSON, no prose, no markdown, no code fences:

{{
  "findings": [
    {{
      "severity": "high",
      "title": "Liability cap is 3 months of fees",
      "quote": "<verbatim substring from contract>",
      "explanation": "US market norm for an MSA of this size is 12 months of fees minimum...",
      "redline": "Increase liability cap to the greater of $1M or 12 months of fees..."
    }}
  ]
}}

`severity` must be one of: "high", "medium", "low", "missing".
`redline` is optional — set to "" if you do not have a concrete proposal.

CONTRACT TEXT:
\"\"\"
{text}
\"\"\"
"""


def build_client_summary_prompt(
    findings: list[dict[str, Any]],
    contract_type: str,
    source_text: str,
) -> str:
    """Build the client-summary prompt — the four-section plain-English memo.

    The model returns a JSON object with four fields. The disclaimer
    required by Constitution IV is NOT generated by the model — it is
    attached by the caller in :mod:`caveat.pipeline.client_summary`.
    """
    findings_json = json.dumps(findings, indent=2)
    truncated = source_text[:CLIENT_SUMMARY_TRUNCATE_CHARS]
    return f"""You are writing a plain-English memo to a non-lawyer client about a
{contract_type} they are about to sign. The reviewing attorney has
already identified the findings below. Your job is to translate them
into language the client will understand.

NON-NEGOTIABLE RULES:

1. Speak only about what is in the findings and the contract text below.
   Do not invent obligations, risks, or facts.

2. If you are uncertain about something, say so plainly or omit it. Do
   not guess.

3. Do not write a disclaimer. The system attaches a disclaimer
   automatically; you must not generate, paraphrase, or include one.

4. Use plain English. Avoid Latin. Avoid jargon. Short sentences.

OUTPUT FORMAT — strict JSON, no prose, no markdown, no code fences:

{{
  "what_this_contract_is": "One short paragraph describing the contract in plain English.",
  "what_youre_committing_to": "One short paragraph describing the client's main obligations.",
  "biggest_risks": [
    "First biggest risk in one sentence.",
    "Second biggest risk in one sentence.",
    "Third biggest risk in one sentence."
  ],
  "recommendation": "One short paragraph: sign as-is, negotiate specific items, or do not sign."
}}

`biggest_risks` MUST be a list of exactly three strings, ordered by
severity (highest first). If there are fewer than three meaningful risks,
repeat the most important one or use a phrase like "No additional
material risks identified."

FINDINGS (already validated, each quote appears verbatim in the contract):
{findings_json}

CONTRACT TEXT (excerpt):
\"\"\"
{truncated}
\"\"\"
"""
