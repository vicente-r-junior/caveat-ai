# Caveat AI — contract fixtures

Test fixtures for the Caveat AI analysis pipeline. Three of these are **synthetic** (rendered by `fixtures/build_fixtures.py` from inline source) and one is a **real public-domain SEC EDGAR filing** with party names pseudonymized.

| File | Pages | Source | Used by |
|---|---|---|---|
| `msa-acme.pdf` | 8 | Synthetic — see `build_fixtures.py::msa_acme` | Unit + E2E (mocked LLM) and manual scenarios |
| `nda-techcorp.pdf` | 3 | Synthetic — see `build_fixtures.py::nda_techcorp` | Unit + E2E (mocked LLM) and manual scenarios |
| `invoice-not-a-contract.pdf` | 1 | Synthetic — see `build_fixtures.py::invoice` | Unit + E2E (classifier "Other" edge case) |
| `real-msa-edgar.pdf` | 12 | SEC EDGAR Exhibit 10.13, pseudonymized | **Manual validation only** — real Gemma 4 hits this |

To regenerate any of these from source:

```bash
cd apps/backend
uv sync --group fixtures        # one-time, installs reportlab into the dev venv
uv run python ../../fixtures/build_fixtures.py
```

The PDFs are committed (binary, not human-diffable). The build script is idempotent and overwrites the output files; use `git diff --stat fixtures/contracts/` to see whether your run changed anything before committing.

---

## Synthetic fixtures (used in the automated suite)

Each synthetic PDF has **deliberately planted issues** designed to exercise specific paths through the analysis pipeline. The Caveat AI analyzer should flag these issues — and only these issues, plus any genuinely odd boilerplate it surfaces. False positives on the planted-safe clauses are regressions.

### `msa-acme.pdf` — fictional Acme Software, Inc. MSA

| ID | Severity | Issue | Where in document |
|---|---|---|---|
| (a) | **high** | Liability cap of **only 3 months** of fees — well below the US norm of 12+ months | § 9.2 |
| (b) | **high** | **One-way indemnification** running from Customer → Provider only; no reciprocal Provider → Customer obligation | § 10.1 (no § 10.2 on Provider Indemnity) |
| (c) | **medium** | **Termination for convenience** by Provider with **no refund of prepaid fees** and unpaid term fees accelerated | § 8.3 |
| (d) | **missing** | **No DPA reference** — there is no Data Protection Addendum mentioned anywhere in the document, despite the agreement contemplating processing of Customer Data (cf. §§ 1.4, 6.2). § 11A talks about general security commitments but does not reference a DPA | (deliberately absent) |

**Safe / normal clauses** (analyzer should NOT flag these):

- Delaware governing law and exclusive jurisdiction (§ 15.1)
- Mutual confidentiality with 3-year survival, perpetual for trade secrets (§§ 7, 11)
- Mutual reps and warranties (§ 3)
- Standard insurance requirements ($1M/$2M CGL, $2M E&O) (§ 12)
- Standard mutual termination for cause with 30-day cure (§ 8.2)
- Force majeure (§ 13)
- Audit rights with notice and standard limits (§ 11C)
- Subprocessor flow-down (§ 11B)
- Compliance with FCPA and U.K. Bribery Act (§ 11D)
- Standard counterparts, severability, no third-party beneficiaries clauses (§§ 15.6–15.10)
- Informal dispute resolution + equitable relief carve-out (§§ 16.1–16.2)

**Why this fixture exists**: it gives the analyzer a realistic 8-page MSA with a known answer key. Findings should map cleanly to the four planted issues above (give or take one false positive at most).

### `nda-techcorp.pdf` — fictional TechCorp Industries, Inc. mutual NDA

| ID | Severity | Issue | Where in document |
|---|---|---|---|
| (a) | **medium** | **Overly broad "Confidential Information" definition** — includes "any and all information ... whether marked as confidential or not ... regardless of whether such information would ordinarily be considered confidential or proprietary in nature" | § 1 |
| (b) | **medium** | **No survival period** for confidentiality obligations after termination (§ 8 covers misc terms but no Survival section anywhere) | (deliberately absent) |

**Safe / normal clauses** (analyzer should NOT flag these):

- Mutual structure (either party may be Disclosing or Receiving) (preamble)
- Standard exceptions: prior possession, public domain, third-party receipt, independent development, required by law (§ 2)
- Standard receiving-party obligations: use restriction, reasonable care, limited disclosure with flow-down (§ 3)
- No license / no warranty (§ 4)
- Mutual injunctive-relief remedy (§ 5)
- Return-or-destroy with retention carve-out for legal/policy holds (§ 6)
- New York governing law (§ 7)
- Standard miscellaneous (entire agreement, amendment, severability) (§ 8)

### `invoice-not-a-contract.pdf` — Northbrook Office Supplies invoice

A 1-page commercial invoice. **Not a contract.** Used to test the classifier edge case from the spec ("non-contract PDF uploaded → classifier says 'Other'") and FR-004. The analyzer should classify this as `Other` and the surrounding flow should either decline analysis or run analysis with a banner. There are no planted contract-style issues — it's just an invoice.

---

## Real fixture (used in manual validation only)

### `real-msa-edgar.pdf` — pseudonymized SEC EDGAR Exhibit 10.13

- **Source**: SEC EDGAR Exhibit 10.13 from accession `0001104659-20-080690` (filed July 2020 by Kubient, Inc., a Delaware corporation; the underlying MSA is dated June 1, 2018).
- **Original URL**: <https://www.sec.gov/Archives/edgar/data/1729750/000110465920080690/tm2023792d1_ex10-13.htm>
- **Status**: SEC filings are public domain (17 U.S.C. § 105 effects on works prepared by the U.S. Government do not apply, but the SEC publishes filings under the public-disclosure regime; redistribution of registered filings is unrestricted). See the SEC's Privacy and Security policy: <https://www.sec.gov/privacy>.
- **Pseudonymization**: party names and signatory names were replaced via simple substring substitutions to keep the fixture neutral. Contract structure, language, and section organization are intact verbatim.
  - `Kubient, Inc.` → `Acme Provider Solutions, Inc.`
  - `Sphere Digital, LLC` → `Counterparty Holdings, LLC`
  - Signatory names → fictional (Anita Vasquez, Daniel Reyes)
  - Specific street addresses → fictional placeholders
- **Source-of-truth file**: the cleaned text is committed at `fixtures/raw/edgar-msa-source.txt`. The build script reads that file and renders the PDF — no network call is required to regenerate. This file is the only thing reviewers need to diff if they want to confirm pseudonymization.
- **Used by**: **manual validation scenarios only** (Sprint 1 onward). The automated suite mocks the LLM at the `ollama_client` boundary and uses the synthetic fixtures. Real Gemma 4 e4b is exercised by the human running the manual scenarios in `sprints/sprint-N-validation.md` against this real-feeling MSA.
- **Planted issues**: none. The analyzer is left to find what it finds. This makes it a good "real-world feel" smoke test — useful for spotting prompt regressions that mocked tests cannot catch.

---

## Versioning and stability

Tests treat the synthetic PDFs as a stable contract: tests assert that specific verbatim quotes appear in the parsed text. **If you regenerate `msa-acme.pdf` or `nda-techcorp.pdf`, you may break those tests.** When changing fixture content, run `just check` and update affected test expectations in the same commit.

The EDGAR fixture is intentionally only consumed by manual scenarios and is therefore safe to regenerate without breaking automated tests.
