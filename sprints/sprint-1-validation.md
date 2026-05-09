# Sprint 1 — Validation

**Status**: Ready for human review
**Generated**: 2026-05-09
**Scope reference**: `sprints/sprint-1-backend-slice.md`
**Verification command**: `just verify-sprint-1`

---

## Summary of what changed

Sprint 1 delivered the full backend vertical slice for User Story 1 (single-document risk analysis): a contract PDF goes in via HTTP, validated risk findings + a four-section client summary come out. No UI yet (Sprint 2). The pipeline runs entirely against `localhost` (Ollama for inference, SQLite for persistence) and is hardened against the model fabricating citations or the network being touched at all.

**Implemented (per sprint scope):**

- **`apps/backend/caveat/llm/ollama_client.py`** — single seam for LLM calls. Hardcoded base URL `http://localhost:11434` (Constitution I). `generate()` and `generate_json()` (the latter sets Ollama's JSON-mode `format="json"` and parses the response). Custom typed exceptions: `OllamaError` → `OllamaUnreachableError`, `OllamaInvalidJSONError(raw_response)`. 120-second read timeout to give the analyze pipeline headroom under the 60s budget.
- **`apps/backend/caveat/llm/prompts.py`** — `build_classify_prompt`, `build_analyze_prompt`, `build_client_summary_prompt`. Each enforces Constitution II/III: verbatim quoting required for findings, model speaks only of what's in the loaded text, model says "I don't know" rather than guess. The disclaimer is **explicitly forbidden** from the model's output (it's attached by `client_summary.py`, never paraphrased).
- **`apps/backend/caveat/pipeline/parse.py`** — `parse_pdf(path)` using `pypdf`. Detects sections via simple regex on numbered headings. **Rejects scanned/image-only PDFs** with `ScannedPDFError` rather than analyzing 5 chars of garbage (Constitution VI).
- **`apps/backend/caveat/pipeline/classify.py`** — calls Ollama, returns one of `MSA | NDA | SaaS | Employment | Other`. Defaults to `Other` on parse failure or unknown response. `OllamaUnreachableError` is re-raised so the router returns a clean 503 (don't paper over a dead daemon).
- **`apps/backend/caveat/pipeline/load_playbook.py`** — reads `caveat/playbooks/{type}.json`; falls back to a built-in minimal playbook for unknown types. Pure file I/O.
- **`apps/backend/caveat/pipeline/validate_citations.py`** — **the unmovable seam, Constitution II**. Pure function with no I/O, no globals, no Ollama dependency. Frozen dataclasses, tuple-only return shapes. Whitespace is normalized on both sides; **smart quotes vs straight quotes are deliberately NOT normalized** (the difference is a fabrication signal); punctuation is preserved exactly. 13 unit tests pin the boundary tightly.
- **`apps/backend/caveat/pipeline/analyze.py`** — orchestrates parse → analyze → validate. Retries ONCE if `failure_rate > 0.30` with a stricter prompt that emphasizes verbatim quoting. Surfaces a warning whenever a retry was triggered (even on success) and again when post-retry still has drops (Constitution VI: surface, never paper over).
- **`apps/backend/caveat/pipeline/client_summary.py`** — four-section memo (`what_this_contract_is`, `what_youre_committing_to`, `biggest_risks`, `recommendation`) built from validated findings. **Disclaimer attached unconditionally** as a separate field — present even on the malformed-JSON fallback path (Constitution IV).
- **`apps/backend/caveat/storage/db.py`** — SQLite via stdlib `sqlite3`. Schema: `documents` + `findings` with `ON DELETE CASCADE` and `PRAGMA foreign_keys = ON`. `list_documents()` deliberately excludes the `text` column at the SQL level so a careless `**row` spread can't leak full contract text in list views.
- **`apps/backend/caveat/playbooks/msa.json`** + **`nda.json`** — full US-norm playbook for MSAs (liability cap, indemnification, termination, IP, confidentiality, governing law, DPA) and a short one for NDAs. Each section: `expected`, `severity_if_missing`, `description`, `red_flags`.
- **`apps/backend/caveat/routers/documents.py`** — `POST /api/documents/` (multipart, ≤ 10 MB PDF only), `GET /` (list, no text), `GET /{id}` (single), `DELETE /{id}`. 415 for non-PDF, 413 for oversized, 422 for scanned/unparseable, 404 for unknown id.
- **`apps/backend/caveat/routers/analyze.py`** — `POST /api/analyze/{document_id}`. Runs the full 6-stage pipeline. Returns `{document_id, contract_type, findings[], client_summary{disclaimer}, warnings[], elapsed_seconds}`. 503 on `OllamaUnreachableError`, 502 on other `OllamaError`. The 60s budget is observable via `elapsed_seconds`, deliberately not enforced via timeout (M4 Air dev hardware can legitimately exceed it).
- **`apps/backend/caveat/main.py`** — both routers wired in. **CORS narrowed** (carry-forward from sprint-0): `allow_methods=["GET","POST","DELETE"]`, `allow_headers=["Content-Type"]`, single origin unchanged. `init_db()` called in the `lifespan` startup so the schema is present before the first request.
- **Tests**: `apps/backend/tests/conftest.py` autouse session-scoped no-network fixture (Constitution I unmovable guard); 9 unit test files (64 tests) + 3 backend E2E test files (13 tests). Full unit suite **0.95s**.
- **Fixtures**: 3 synthetic PDFs with planted issues (`msa-acme.pdf`, `nda-techcorp.pdf`, `invoice-not-a-contract.pdf`) rendered via `fixtures/build_fixtures.py` using `reportlab` (in the new `fixtures` dep group, NOT a runtime dep). One pseudonymized real SEC EDGAR MSA (`real-msa-edgar.pdf`) for manual scenarios; cleaned source committed at `fixtures/raw/edgar-msa-source.txt` for offline reproducibility. Provenance and planted-issue answer key documented in `fixtures/contracts/README.md`.
- **Tooling**: `Justfile` `test-e2e` now runs `pytest tests/e2e -q` before Playwright (carry-forward from sprint-0). `verify-sprint-1` recipe added. `check-backend` extends mypy strict to `tests/`. `.specify/feature.json` pins the feature directory so speckit scripts work on `main`.

**Carry-forward items from sprint-0-validation.md, both addressed:**

- ✅ CORS narrowed in `apps/backend/caveat/main.py` — methods/headers no longer `*`
- ✅ Backend E2E wired into `Justfile` — `pytest tests/e2e -q` runs before Playwright; placeholder no-op gone

**Explicitly NOT delivered** (out of scope for Sprint 1):

- Frontend (Sprint 2 — UI consumes this API)
- Chat endpoint with multi-doc context + SSE streaming (Sprint 4)
- Findings router for accept/edit/dismiss/ask-in-chat decisions (Sprint 4)
- Export router for Word/PDF/redline/email (Sprint 5)
- Hardware auto-detection for model variant selection (Sprint 5)
- Multi-document support / 5-doc cap enforcement at the router level (Sprint 4)

---

## Unit tests added

64 unit tests across 9 files. Full suite runs in **0.95s** (Constitution X budget: 10s). All run under the autouse no-network fixture.

### `apps/backend/tests/conftest.py` — autouse no-network fixture (NFR-001 enforcement)

Session-scoped autouse fixture monkey-patches `httpx.Client.send`, `httpx.AsyncClient.send`, `requests.adapters.HTTPAdapter.send` (conditional on `requests` being installed), and `urllib.request.urlopen`. Allowlist: `localhost`, `127.0.0.1`, `::1`, plus `testserver` for FastAPI's `TestClient` (which uses `ASGITransport` in-process, double-checked via class isinstance/name). Any blocked egress raises `RuntimeError("Constitution I violation: blocked outbound request to <host>")`.

### `apps/backend/tests/unit/test_validate_citations.py` — 13 tests (the most important file in Sprint 1)

Pin the Constitution II seam:
1. `test_valid_quote_found_verbatim` — quote appears verbatim → kept, failure_rate 0.0
2. `test_quote_missing_entirely` — quote absent → dropped with "not found" reason
3. `test_quote_partial_word_match` — quote longer than what's in source (model fabrication of trailing words) → dropped
4. `test_whitespace_normalized_match_succeeds` — `"Provider\n\nshall   maintain"` source vs `"Provider shall maintain"` quote → matches
5. `test_smart_quotes_do_not_match_straight_quotes` — `"Provider's"` (U+2019) vs `"Provider's"` (ASCII) → dropped (anti-fabrication signal preserved)
6. `test_punctuation_preserved_exactly` — `"Section 7"` source vs `"Section 7."` quote → dropped
7. `test_empty_quote_dropped` — empty `quote=""` → "Empty quote" reason
8. `test_empty_source_drops_everything` — every finding dropped with "Source text is empty" reason
9. `test_quote_longer_than_source_dropped` — "Quote longer than source" reason
10. `test_mixed_valid_and_invalid_split_correctly` — 3 valid + 2 invalid → kept=3, dropped=2 with correct reasons
11. `test_failure_rate_arithmetic` — `pytest.approx`, empty input → 0.0
12. `test_findings_iterable_can_be_generator` — `Iterable[Finding]` works with a generator (catches `len()`-on-generator regressions in `analyze.py`)
13. `test_result_is_immutable` — `ValidationResult.kept` is a tuple; mutation raises `dataclasses.FrozenInstanceError`

### `apps/backend/tests/unit/test_parse.py` — 4 tests

- `test_parse_msa_acme_happy_path` — 8 pages, > 5000 chars, ≥ 5 sections detected
- `test_parse_nda_techcorp_happy_path` — non-zero pages, > 1000 chars
- `test_parse_invoice_happy_path` — 1 page, > 200 chars, sections list empty/near-empty
- `test_parse_scanned_pdf_raises` — generates an in-test image-only PDF via reportlab, asserts `ScannedPDFError`

### `apps/backend/tests/unit/test_classify.py` — 10 tests (parametrized over the 5 known types + happy/error paths)

- Per-type happy path (parametrized for MSA/NDA/SaaS/Employment/Other)
- Unknown type from model → `Other`
- Missing `contract_type` field → `Other`
- `OllamaInvalidJSONError` → `Other` (defaulting, not crashing)
- `OllamaUnreachableError` → re-raises (caller decides 503; don't paper over a dead daemon)

### `apps/backend/tests/unit/test_load_playbook.py` — 4 tests

- MSA playbook shape: every section has `expected`, `severity_if_missing`, `description`, `red_flags`
- NDA playbook shape: same
- Unknown type returns minimal fallback with `contract_type=="<requested>"`
- Case-insensitive lookup (`"msa"` and `"MSA"` resolve to the same dict)

### `apps/backend/tests/unit/test_analyze.py` — 6 tests

Mocks use **real verbatim substrings from the parsed `msa-acme.pdf`** (e.g. `"THREE (3) MONTHS IMMEDIATELY PRECEDING THE EVENT"`, `"Customer shall indemnify"`, `"no refund of prepaid fees"`) so the validator's behavior is exercised against the real fixture rather than synthetic strings. A `_verify_quotes_real` helper guards against fixture drift.

- Happy path: 3 valid + 1 with bad quote → 3 returned, no warnings (failure_rate 0.25 < 0.30)
- All-bad on first call, 2 valid on retry → 2 returned + warning about retry
- Post-retry still has drops → warning about failure rate
- `OllamaInvalidJSONError` → empty findings + warning about malformed JSON
- `OllamaUnreachableError` → re-raises
- Malformed finding dicts (missing `title`/`severity`) → silently skipped, valid ones returned

### `apps/backend/tests/unit/test_client_summary.py` — 5 tests

- Happy path: four fields populated + canonical disclaimer
- Missing fields → "(Not available...)" placeholder, disclaimer present
- More than 3 risks → trimmed to 3
- `["", "Real risk", ""]` → `("Real risk",)` (empty strings filtered)
- **`OllamaInvalidJSONError` → all four fields fall back, disclaimer STILL present (Constitution IV: non-removable, attached even on errors)**

### `apps/backend/tests/unit/test_storage_db.py` — 8 tests

- `init_db` idempotent
- Document insert + get round-trip
- `list_documents` does NOT include `text` field (privacy invariant at SQL level)
- `delete_document` returns True then False
- `update_document_type` round-trip
- Findings insert + list round-trip
- Empty findings list is a no-op (no rows added)
- FK cascade: deleting a document removes its findings

### `apps/backend/tests/unit/test_ollama_client.py` — 8 tests

- POSTs to `http://localhost:11434/api/generate` with the configured model from settings
- Explicit model override flows through
- Returns the `response` field
- `httpx.ConnectError` → `OllamaUnreachableError`
- `generate_json` sets `format="json"` in the body
- Parses string response as JSON
- Invalid JSON → `OllamaInvalidJSONError`
- Non-object JSON (list, scalar) → `OllamaInvalidJSONError` (typed callers expect `dict[str, Any]`)

### `apps/backend/tests/unit/test_no_network_guard.py` — 4 tests (explicit positive test of the autouse fixture, named scenario for this file)

- `test_httpx_get_to_external_host_blocked` — `httpx.get("https://example.com")` raises `RuntimeError("Constitution I…")`
- `test_httpx_async_to_external_host_blocked` — async equivalent
- `test_httpx_to_localhost_allowed_to_attempt` — `httpx.get("http://localhost:11434/...")` does NOT raise the Constitution I error (may raise connect error if nothing is listening; that's fine — proves the guard let it through)
- `test_urllib_to_external_host_blocked` — `urllib.request.urlopen("https://example.com")` raises `RuntimeError("Constitution I…")`

---

## E2E tests added

13 backend E2E tests across 3 files. All use `fastapi.testclient.TestClient(create_app())` against the real ASGI app with the LLM mocked at the `caveat.llm.ollama_client.generate_json` boundary. All run under the autouse no-network fixture and complete in **1.94s**.

### `apps/backend/tests/e2e/test_documents_e2e.py` — 7 tests

- Upload `msa-acme.pdf` → 200 + `document_id`, `page_count==8`, `contract_type is None`
- List documents shows the upload, no `text` field
- Get single → metadata or 404 for unknown id
- Delete → 204 then 404
- Non-PDF extension (`hello.txt`) → 415
- Oversized (11 MB) → 413
- Image-only PDF (generated in-test) → 422 with the scanned-PDF message in `detail`

### `apps/backend/tests/e2e/test_analyze_e2e.py` — 5 tests

Mocks return real verbatim quotes from `msa-acme.pdf` so the citation validator behavior is exercised end-to-end.

- Happy path: upload → analyze → 200 with `document_id`, `contract_type=="MSA"`, 3 findings, `client_summary.disclaimer` non-empty mentioning "attorney review", `elapsed_seconds > 0`
- Unknown document → 404
- Findings persisted to the DB (verified via direct `list_findings_for_document` call)
- `OllamaUnreachableError` → 503 with daemon-down message in detail
- Pipeline retry → response includes non-empty `warnings` list

### `apps/backend/tests/e2e/test_pipeline_no_network.py` — 1 test (named scenario for this validation file)

- `test_full_analyze_pipeline_runs_under_no_network_guard` — full pipeline runs to 200 under the autouse fixture, with an explicit `httpx.get("https://example.com")` at the end that asserts `RuntimeError`. The test passing AT ALL while the guard is active is the constitutional proof.

---

## Manual validation scenarios

Run these after `just verify-sprint-1` passes. Each scenario lists the exact expected behavior. If any deviates, note it and stop — that's a regression to fix before declaring Sprint 1 done.

### Scenario 1 — Health check

```bash
just dev   # in one terminal
```

Wait for `caveat backend ready, model=gemma4:e4b, db=/Users/<you>/.caveat/data.db`. In another terminal:

```bash
curl -s http://localhost:8787/api/health
```

**Expected**: `{"status":"ok","model":"gemma4:e4b"}` (Sprint 0 contract preserved exactly).

### Scenario 2 — Upload an MSA fixture, get a document_id

```bash
curl -s -X POST http://localhost:8787/api/documents/ \
  -F "file=@fixtures/contracts/msa-acme.pdf;type=application/pdf" | python3 -m json.tool
```

**Expected**: a JSON object with `document_id` (UUID-like), `filename: "msa-acme.pdf"`, `page_count: 8`, `contract_type: null`. Save the `document_id` for the next step.

```bash
curl -s http://localhost:8787/api/documents/ | python3 -m json.tool
```

**Expected**: a list containing your upload. Each entry has `id`, `filename`, `contract_type`, `page_count`, `created_at`. **Verify there is NO `text` field** (privacy invariant).

### Scenario 3 — Run analyze, inspect findings JSON

**Prerequisite**: `ollama serve` running, `gemma4:e4b` pulled.

```bash
DOC_ID=<from scenario 2>
time curl -s -X POST http://localhost:8787/api/analyze/$DOC_ID | python3 -m json.tool
```

**Expected**:
- HTTP 200, response time on M4 Air typically 30–90 seconds (gemma4:e4b is the fallback model; expect higher latency than the production target gemma4:31b).
- Top-level fields: `document_id`, `contract_type` (probably `"MSA"`), `findings` (list, ≥ 3 entries), `client_summary` (object with 5 fields), `warnings` (list, may be empty), `elapsed_seconds` (number).
- Each finding has: `severity` (`"high"` / `"medium"` / `"low"` / `"missing"`), `title`, `quote`, `explanation`, `redline` (may be empty).
- `client_summary` has: `what_this_contract_is`, `what_youre_committing_to`, `biggest_risks` (list of up to 3), `recommendation`, **`disclaimer`** (must mention "attorney review" — Constitution IV).

### Scenario 4 — Verify quote of every finding exists in source PDF text

This is the Constitution II promise: every model claim is grounded in a verbatim source quote.

```bash
# Save the analyze response to a file for inspection:
curl -s -X POST http://localhost:8787/api/analyze/$DOC_ID > /tmp/analysis.json

# Extract the parsed source text:
python3 - <<'EOF'
import json, re
from pypdf import PdfReader
r = PdfReader('fixtures/contracts/msa-acme.pdf')
source = "\n\n".join(p.extract_text() for p in r.pages)
def normalize(s): return re.sub(r"\s+", " ", s).strip()
norm_source = normalize(source)

analysis = json.load(open('/tmp/analysis.json'))
print(f"Checking {len(analysis['findings'])} findings...\n")
all_ok = True
for i, f in enumerate(analysis['findings']):
    quote = f['quote']
    if normalize(quote) in norm_source:
        print(f"  [OK]   {f['severity']:<8} {f['title'][:60]}")
    else:
        print(f"  [MISS] {f['severity']:<8} {f['title'][:60]}")
        print(f"         quote={quote[:120]!r}")
        all_ok = False
print("\nAll findings cite verbatim from source:", all_ok)
EOF
```

**Expected**: Every finding prints `[OK]`. If anything prints `[MISS]`, the citation validator failed to drop a hallucinated quote — that is a Constitution II failure and a hard-stop bug.

### Scenario 5 — Force a bad citation, assert it's dropped

This proves the validator drops hallucinated quotes. Done as a unit test (`test_validate_citations.py::test_quote_missing_entirely` and friends), but for a manual proof:

```bash
cd apps/backend && uv run python - <<'EOF'
from caveat.pipeline.validate_citations import Finding, validate_citations
fake = [
    Finding(severity="high", title="Real", quote="State of Delaware", explanation="...", redline=""),
    Finding(severity="high", title="Hallucinated", quote="State of Atlantis", explanation="...", redline=""),
]
source = "This Agreement shall be governed by the laws of the State of Delaware..."
result = validate_citations(fake, source)
print(f"kept ({len(result.kept)}):  {[f.title for f in result.kept]}")
print(f"dropped ({len(result.dropped)}):  {[(d.finding.title, d.reason) for d in result.dropped]}")
assert len(result.kept) == 1 and result.kept[0].title == "Real"
assert len(result.dropped) == 1 and result.dropped[0].finding.title == "Hallucinated"
print("\nValidator correctly dropped the hallucinated quote.")
EOF
```

**Expected output**: `kept (1): ['Real']`, `dropped (1): [('Hallucinated', '...')]`, then `Validator correctly dropped...`.

### Scenario 6 — Run analyze with airplane mode on (Constitution I)

Toggle Wi-Fi off (or just disable Ethernet/Wi-Fi at the OS level — leave loopback alone). With Ollama still running locally and `just dev` still serving on `:8787`:

```bash
curl -s -X POST http://localhost:8787/api/analyze/$DOC_ID | python3 -m json.tool | head -30
```

**Expected**: identical behavior to Scenario 3 — full analysis completes successfully. The application makes no calls outside `localhost`.

For an even stronger proof, in another terminal monitor outbound traffic:

```bash
sudo tcpdump -nn -i en0 'not net 127.0.0.0/8 and not net ::1/128 and (host <your-machine-ip> and (tcp port 80 or tcp port 443))' -c 20
```

Run an analyze. **Expected**: `tcpdump` captures **zero packets** during analysis. Re-enable Wi-Fi when done.

### Scenario 7 — Upload a scanned PDF, assert clear error message

The fixtures don't include a scanned PDF (the unit test generates one in-test). For a manual proof, use any image-only PDF (e.g. a screenshot saved as PDF, or a Word doc rendered with no text layer). If you don't have one handy, generate one quickly:

```bash
cd apps/backend && uv run --group fixtures python - <<'EOF'
from reportlab.pdfgen.canvas import Canvas
c = Canvas("/tmp/scanned.pdf")
c.showPage()  # blank page, no text drawn
c.save()
EOF

curl -s -X POST http://localhost:8787/api/documents/ \
  -F "file=@/tmp/scanned.pdf;type=application/pdf" | python3 -m json.tool
```

**Expected**: HTTP 422 with a `detail` field that says something like `"This appears to be a scanned/image-only PDF. OCR is not supported in the MVP. Please upload a text-based PDF."` — clear, user-facing, no stack trace.

### Scenario 8 — Real-Ollama smoke test on the EDGAR fixture (REAL Gemma 4 e4b on M4 Air)

This is the integration test that the automated suite cannot run (mocked LLM). The real model on real hardware against a real-feeling MSA. Expect 1–3 minutes wall-clock.

**Prerequisite**: `ollama serve` running, `gemma4:e4b` pulled (≈9.6 GB).

```bash
# Upload the pseudonymized real EDGAR MSA:
curl -s -X POST http://localhost:8787/api/documents/ \
  -F "file=@fixtures/contracts/real-msa-edgar.pdf;type=application/pdf" | tee /tmp/upload.json

DOC_ID=$(python3 -c "import json; print(json.load(open('/tmp/upload.json'))['document_id'])")

# Run analyze and time it:
time curl -s -X POST http://localhost:8787/api/analyze/$DOC_ID > /tmp/edgar_analysis.json

# Sanity:
python3 -c "
import json
a = json.load(open('/tmp/edgar_analysis.json'))
print(f\"contract_type: {a['contract_type']}\")
print(f\"findings:      {len(a['findings'])} returned\")
print(f\"warnings:      {a['warnings']}\")
print(f\"elapsed:       {a['elapsed_seconds']:.1f}s\")
print(f\"summary recommendation: {a['client_summary']['recommendation'][:200]}\")
"
```

**Expected**:
- HTTP 200, no errors.
- `contract_type` is most likely `"MSA"`.
- `findings` is non-empty (typically 5–15 entries on a 12-page real MSA). Some may be in `warnings` if the citation validator dropped any.
- The recommendation is a coherent sentence or two.
- `elapsed_seconds` will be 30–180s on M4 Air with `gemma4:e4b` (the fallback model). The 60-second budget is calibrated for the production target `gemma4:31b-instruct-q4_K_M` on recommended hardware (32 GB RAM + GPU). Going over on the dev machine is expected and not a regression.

Spot-check a few findings: pick three at random and confirm their `quote` strings appear verbatim in `fixtures/raw/edgar-msa-source.txt`. If any quote is fabricated, that's a Constitution II failure. (The validator should have already caught it; this is belt-and-suspenders.)

### Scenario 9 — Unit suite is fast (Constitution X budget)

```bash
cd apps/backend && uv run python -m pytest tests/unit -q
```

**Expected**: `64 passed in <1.5s` (current measurement: 0.95s on M4 Air; budget is 10s).

---

## Verification command

```bash
just verify-sprint-1
```

Runs `just install && just check && just test-e2e` and prints a `Sprint 1 verification: PASS` line. Exit code 0 means the automated suite is green; the human walks through the 9 manual scenarios above to close the sprint.

Test breakdown:
- Backend unit: 64 tests, ~1.2s
- Frontend unit: 11 tests, ~2.0s (Sprint 0, unchanged)
- Backend E2E (pytest+httpx): 13 tests, ~2.0s
- Frontend E2E (Playwright): 1 test, ~9s (Sprint 0, unchanged)

---

## Caveats and notes for the next sprint

Carried forward from the code review (8 soft notes; none are blockers):

1. **FastAPI/Starlette deprecation warnings** — `apps/backend/caveat/routers/documents.py` uses `status.HTTP_413_REQUEST_ENTITY_TOO_LARGE` and `status.HTTP_422_UNPROCESSABLE_ENTITY`, both renamed in Starlette to `HTTP_413_CONTENT_TOO_LARGE` and `HTTP_422_UNPROCESSABLE_CONTENT`. Non-failing warnings show up during `just test-e2e`. Cosmetic; trivial to fix in Sprint 2 or as part of a maintenance pass.

2. **`OllamaError` 502 path is currently unreachable from the analyze pipeline** — `routers/analyze.py` catches `OllamaError` parent class and returns 502, but `OllamaInvalidJSONError` is absorbed into pipeline warnings before the router sees it. The 502 path will become exercisable when Sprint 4's chat endpoint is wired in (different error envelope).

3. **`build_fixtures.py` runtime safety** — confirming for the human reviewer: `fixtures/build_fixtures.py` is dev-only (in the `fixtures` dep group, NOT the runtime `dependencies` list) and renders the EDGAR MSA from the committed `fixtures/raw/edgar-msa-source.txt`, no network call required. The one-time SEC EDGAR pull during Sprint 1 was a dev-time content-authoring operation, not a runtime path. Constitution I exception scope respected.

4. **Findings `redline` column is nullable in storage** — `storage/db.py` stores `redline TEXT` nullable, while the `FindingOut` Pydantic model defaults `redline=""`. Currently fine because the converter normalizes None → "". Sprint 4's findings router (accept/edit/dismiss) should consider tightening to `NOT NULL DEFAULT ''` for symmetry.

5. **`ollama_client.generate_json` `schema` argument is currently a silent no-op** — `del schema  # reserved for future use` per the docstring. A future caller relying on schema enforcement (Sprint 4 chat?) would get silently weakened guarantees. Suggested follow-up: raise `NotImplementedError` if `schema is not None` so the no-op is impossible.

6. **No defense against wrong-known-type misclassification** — `classify.py` accepts whatever the model says among the 5 literals. If Gemma returns `"MSA"` for an invoice, `analyze` runs the MSA playbook against the invoice. The playbook fallback in `load_playbook.py` covers unknown types; misclassification within the known set is unprotected. The citation validator still drops fabricated quotes either way. Sprint 4 to consider a confidence threshold or a "does this read like an MSA?" sanity check.

7. **`CLIENT_SUMMARY_TRUNCATE_CHARS = 20000`** — long contracts have their tail dropped before the model writes the summary. Findings carry the verbatim quotes already, so the summary is grounded — but Sprint 4 (multi-doc) needs to decide whether truncating beats per-chunk summarization.

8. **No "guard active" receipt in test output** — the autouse no-network fixture is silent on activation. A single `pytest -v` line confirming "Constitution I guard active" would make the airplane-mode guarantee visible to a human running the suite. Future polish, not a Sprint 1 issue.

Other notes carried forward from sprint-0-validation.md and not addressed here (still applicable):

- **Pyenv interaction** — `.python-version` declares 3.11; `uv` falls back to its own managed CPython if pyenv doesn't have it. Run `uv python install 3.11` once if needed.
- **Fonts** — Sprint 5 will bundle Fraunces / Geist / Geist Mono as self-hosted woff2 (frontend doesn't load Google Fonts; Constitution I).
- **App.tsx eyebrow** — Sprint 2 will replace "Sprint 0 — Scaffold" with the real screen but should keep the disclaimer footer pattern intact.

---

**Sprint 1 is ready for validation.** Run `just verify-sprint-1` and walk through scenarios 1–9 above. Tell me what you find.
