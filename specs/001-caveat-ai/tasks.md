---

description: "Sprint 1 — Backend vertical slice. Per-sprint tasks (overwritten each sprint by /speckit.tasks)."
---

# Tasks: Caveat AI — Sprint 1 (Backend Vertical Slice)

**Input**: `sprints/sprint-1-backend-slice.md`, `specs/001-caveat-ai/spec.md` (US1, FR-001 to FR-006, FR-012), `specs/001-caveat-ai/plan.md` (§3 pipeline), `.specify/memory/constitution.md` (I, II, III, VI, X)

**Tests**: REQUIRED (per Sprint 1 Definition of Done and Constitution X)

**Organization**: Tasks are scoped strictly to Sprint 1. Frontend, chat, export, hardware detection, and multi-document support are out of scope (later sprints).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Sprint 1 only touches US1 (backend portion). Setup/foundational/polish tasks carry no story label.
- All paths are relative to repo root unless otherwise noted.

## Path Conventions

- Backend: `apps/backend/caveat/...` (source), `apps/backend/tests/unit/...` and `apps/backend/tests/e2e/...` (tests)
- Fixtures: `fixtures/contracts/`
- Justfile / repo-level config: repo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: One-time per-sprint scaffolding; no backend logic yet.

- [X] T001 Pin feature directory at `.specify/feature.json` so speckit scripts work on `main` (already done in this run)
- [ ] T002 [P] Add `pypdf`, `httpx`, `python-multipart` to `apps/backend/pyproject.toml` and run `uv sync` (Sprint 0 already has fastapi, pydantic-settings, pytest, ruff, mypy)
- [ ] T003 [P] Create empty package directories with `__init__.py` files: `apps/backend/caveat/llm/`, `apps/backend/caveat/pipeline/`, `apps/backend/caveat/storage/`, `apps/backend/caveat/playbooks/` (folders exist from Sprint 0; ensure `__init__.py` is present in each)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Modules every Sprint 1 pipeline stage depends on. Must be done before any US1 task.

**⚠️ CRITICAL**: No US1 work begins until this phase is complete.

- [ ] T004 Implement `apps/backend/tests/conftest.py` with an **autouse session-scoped no-network fixture** that monkey-patches `httpx.Client.send`, `httpx.AsyncClient.send`, and `requests.adapters.HTTPAdapter.send` to raise `RuntimeError` on any URL whose host is not `localhost`/`127.0.0.1`. This is the NFR-001 unmovable guard — every backend test runs under it. Constitution I.
- [ ] T005 Implement `apps/backend/caveat/llm/ollama_client.py` — thin sync HTTP client wrapping `POST http://localhost:11434/api/generate` and `POST /api/chat`. Single seam for LLM calls. Functions: `generate(prompt: str, *, model: str | None = None, format: str | None = None, options: dict | None = None) -> str` and `generate_json(prompt: str, *, schema: dict | None = None, model: str | None = None) -> dict`. Reads default model from `caveat.config.get_settings().model_name`. No streaming yet (Sprint 4).
- [ ] T006 [P] Implement `apps/backend/caveat/llm/prompts.py` — three prompt template constants (or callables): `CLASSIFY_PROMPT`, `ANALYZE_PROMPT`, `CLIENT_SUMMARY_PROMPT`. Each enforces Constitution II/III: outputs cite verbatim from source, model says "I don't know" rather than guessing, model speaks only of what's in the loaded text. Each returns a callable like `build_classify_prompt(text: str) -> str`.
- [ ] T007 [P] Implement `apps/backend/caveat/storage/db.py` — SQLite via stdlib (`sqlite3`). Schema: `documents(id TEXT PK, filename TEXT, contract_type TEXT, page_count INT, text TEXT, created_at TEXT)` and `findings(id TEXT PK, document_id TEXT FK, severity TEXT, title TEXT, quote TEXT, explanation TEXT, redline TEXT NULL, status TEXT DEFAULT 'pending', created_at TEXT)`. Helpers: `get_db_path()`, `init_db()`, `insert_document()`, `get_document()`, `list_documents()`, `delete_document()`, `insert_findings()`, `list_findings_for_document()`. DB lives at `~/.caveat/data.db` (configurable via env). Idempotent `init_db()` called on FastAPI startup.

---

## Phase 3: User Story 1 — Single-document risk analysis (backend portion) (Priority: P1) 🎯 MVP

**Goal**: `POST /api/documents` accepts a PDF and returns `document_id`. `POST /api/analyze/{document_id}` runs the full 6-stage pipeline and returns validated findings + client summary. No UI.

**Independent Test**: With a fixture MSA (`fixtures/contracts/msa-acme.pdf`) and a fake Ollama server returning canned JSON: upload → analyze → assert at least 3 findings returned, every finding's `quote` exists verbatim in the source PDF text, response includes `client_summary` with the four sections.

### Fixtures (US1)

- [ ] T008 [P] [US1] Author `fixtures/contracts/msa-acme.pdf` (8–15 pages, fictional Acme Inc. MSA). Plant **deliberate issues** for the analyzer to flag: (a) 3-month liability cap (high severity); (b) one-way indemnification favoring Provider only (high); (c) termination for convenience with no refund clause (medium); (d) missing DPA reference / data-protection addendum (missing). Plus 2–3 normal/safe clauses (governing law: Delaware; standard confidentiality; mutual representations) so the analyzer doesn't false-positive. Source from a markdown draft, render to PDF via `reportlab` or `fpdf2` (lightweight, can be a dev-only dep).
- [ ] T009 [P] [US1] Author `fixtures/contracts/nda-techcorp.pdf` (3–5 pages, mutual NDA). Plant: (a) overly broad "Confidential Information" definition (medium); (b) survival period absent or unclear (medium). Plus 1–2 normal clauses (mutuality, standard remedies).
- [ ] T010 [P] [US1] Author `fixtures/contracts/invoice-not-a-contract.pdf` (1 page). Either an invoice or a news-article excerpt. Used by the classifier edge-case test ("Other" / "not a contract").
- [ ] T011 [P] [US1] Source one short MSA (~10–15 pp) from SEC EDGAR exhibits, pseudonymize party names ("Counterparty Inc." etc.) but preserve structure and language. Save as `fixtures/contracts/real-msa-edgar.pdf`. Used in the manual validation scenarios only (real Gemma 4 hits this one).
- [ ] T012 [US1] Write `fixtures/contracts/README.md` documenting provenance: where each fixture came from, what each is testing, and exactly what synthetic issues each contains (so reviewers can verify the analyzer found them).

### Playbooks (US1)

- [ ] T013 [P] [US1] Create `apps/backend/caveat/playbooks/msa.json` — full US-norm playbook for MSAs. Required sections: liability cap (with US norms: typically 12 months of fees minimum), indemnification (mutual; carve-outs for IP/confidentiality breach), termination (notice period, refund obligations), IP ownership (work product, pre-existing IP), confidentiality (definition tightness, survival period 3–5 years), governing law (US state, prefer Delaware/NY/CA), DPA / data protection addendum reference. Each section: `expected: bool`, `severity_if_missing`, `description`, `red_flags: list[str]`.
- [ ] T014 [P] [US1] Create `apps/backend/caveat/playbooks/nda.json` — short US-norm playbook for NDAs. Sections: scope of confidential information (tight definition required), term and survival, return/destruction obligations, mutuality, exceptions (independently developed, public domain, required by law), governing law.

### Pipeline stages (US1)

- [ ] T015 [P] [US1] Implement `apps/backend/caveat/pipeline/parse.py` — `parse_pdf(path: Path) -> ParsedDocument` using `pypdf`. Extracts page text, joins with `\n\n`, detects sections by simple heuristic (lines matching `§ \d+(\.\d+)*` or `\d+\.\s+[A-Z]`). Returns `ParsedDocument(text: str, pages: list[str], sections: list[Section], page_count: int)`. **Rejects scanned/image-only PDFs** (no text layer) by raising `ScannedPDFError` with a clear message — caught by the router and returned as HTTP 422.
- [ ] T016 [P] [US1] Implement `apps/backend/caveat/pipeline/classify.py` — `classify(text: str) -> Literal["MSA", "NDA", "SaaS", "Employment", "Other"]`. Calls `ollama_client.generate_json` with `CLASSIFY_PROMPT(text[:8000])`. Returns one of the five values; defaults to "Other" on parse failure or unknown response.
- [ ] T017 [P] [US1] Implement `apps/backend/caveat/pipeline/load_playbook.py` — `load_playbook(contract_type: str) -> dict`. Reads `caveat/playbooks/{type.lower()}.json`. Falls back to a built-in minimal playbook for unknown types. Pure file I/O — no network.
- [ ] T018 [US1] Implement `apps/backend/caveat/pipeline/validate_citations.py` — **the unmovable seam, Constitution II**. Pure function: `validate_citations(findings: list[Finding], source_text: str) -> ValidationResult`. `ValidationResult` exposes `kept: list[Finding]`, `dropped: list[DroppedFinding]`, and `failure_rate: float`. Validation rule: each finding's `quote` must appear verbatim (case-sensitive substring match) in `source_text`. Whitespace is normalized (collapse runs of whitespace to single space) on BOTH sides before comparison; punctuation is preserved exactly. No I/O, no network, no Ollama dependency. Findings whose quote fails validation are dropped, NOT silently retried — the caller decides whether to re-analyze.
- [ ] T019 [US1] Implement `apps/backend/caveat/pipeline/analyze.py` — `analyze(text: str, contract_type: str, playbook: dict) -> list[Finding]`. Builds the analyze prompt with playbook + text, calls `ollama_client.generate_json`, parses returned JSON list of findings (`severity`, `title`, `quote`, `explanation`, `redline`). Calls `validate_citations`. If `failure_rate > 0.30`, retries ONCE with a stricter prompt variant emphasizing verbatim quoting (Constitution VI: never silently retry past that). On second failure, returns the kept findings and includes a warning in the result. Depends on T015–T018.
- [ ] T020 [US1] Implement `apps/backend/caveat/pipeline/client_summary.py` — `build_client_summary(findings: list[Finding], contract_type: str, source_text: str) -> ClientSummary`. Calls `ollama_client.generate_json` with `CLIENT_SUMMARY_PROMPT(findings, contract_type, source_text[:20000])`. Returns the four-section memo: `what_this_contract_is`, `what_youre_committing_to`, `biggest_risks` (top 3), `recommendation`. Each must include the disclaimer string per Constitution IV (returned as a separate field, not concatenated into prose). Depends on T019.

### Routers (US1)

- [ ] T021 [US1] Implement `apps/backend/caveat/routers/documents.py` — `APIRouter(prefix="/api/documents")`. Endpoints: `POST /` (multipart upload, single PDF, max 10 MB; calls `parse_pdf`, persists via `storage.db.insert_document`, returns `{document_id, filename, page_count, contract_type: null}`); `GET /` (list metadata only, never text); `GET /{id}` (single document metadata); `DELETE /{id}` (remove from DB, no findings cleanup needed yet). Returns 422 on `ScannedPDFError` with the user-facing message. Depends on T007, T015.
- [ ] T022 [US1] Implement `apps/backend/caveat/routers/analyze.py` — `APIRouter(prefix="/api/analyze")`. Endpoint: `POST /{document_id}` (no body). Steps: load document text → classify → load playbook → analyze → build client summary → persist findings → return `{document_id, contract_type, findings: [...], client_summary: {...}, warnings: [...]}`. 60-second budget tracked but not enforced via timeout (M4 Air may exceed; we surface elapsed time in the response). Depends on T015–T020, T021.
- [ ] T023 [US1] Wire both routers into `apps/backend/caveat/main.py` via `app.include_router(...)`. **Narrow CORS** (carry-forward from sprint-0): replace the `*` methods/headers with the actual surface — `allow_methods=["GET","POST","DELETE"]`, `allow_headers=["Content-Type"]`, single origin `http://localhost:5173` unchanged. Call `storage.db.init_db()` on startup. Update health-check route to keep returning `{status: "ok", model: <active>}` (no breaking change for Sprint 0's contract).

### Tests for User Story 1

> **Tests are written under the autouse no-network fixture (T004). LLM is mocked at the `ollama_client` boundary per plan §5.**

#### Unit tests

- [ ] T024 [P] [US1] `apps/backend/tests/unit/test_validate_citations.py` — exhaustive tests for the citation validator (Constitution II): valid quote present; quote missing entirely; quote partial-match (substring of a finding word but not full quote); whitespace-normalized match (multiple spaces, newlines, tabs in source vs single-space in quote); unicode normalization edge case (smart quotes vs straight quotes — must NOT be normalized away); empty findings list; empty source text; mixed valid+invalid findings produce correct `kept`/`dropped` split; `failure_rate` arithmetic.
- [ ] T025 [P] [US1] `apps/backend/tests/unit/test_parse.py` — happy path on `msa-acme.pdf` (asserts text length, page count, at least one detected section); `ScannedPDFError` raised for an image-only PDF (use a tiny generated test fixture or a 1-page no-text PDF).
- [ ] T026 [P] [US1] `apps/backend/tests/unit/test_classify.py` — mock `ollama_client.generate_json` to return `{"contract_type":"MSA"}`, assert `classify(...)` returns `"MSA"`. Test default-to-"Other" on malformed response.
- [ ] T027 [P] [US1] `apps/backend/tests/unit/test_load_playbook.py` — load `msa.json` and `nda.json`, assert required keys present. Unknown type returns the minimal fallback.
- [ ] T028 [P] [US1] `apps/backend/tests/unit/test_analyze.py` — mock `ollama_client.generate_json` to return a deterministic findings list (3 valid + 1 with bad quote). Assert: pipeline returns 3 findings, the bad one is dropped, no retry triggered (failure_rate < 0.30). Second test: mock returns all-bad findings → assert retry triggered → second mock returns 2 valid → assert 2 returned plus a warning.
- [ ] T029 [P] [US1] `apps/backend/tests/unit/test_client_summary.py` — mock LLM to return well-formed four-section JSON, assert ClientSummary populated correctly and disclaimer field is present and non-empty (Constitution IV).
- [ ] T030 [P] [US1] `apps/backend/tests/unit/test_storage_db.py` — temp-dir DB. CRUD round-trip for documents and findings. Idempotent `init_db()`.
- [ ] T031 [P] [US1] `apps/backend/tests/unit/test_ollama_client.py` — mock `httpx.Client` (still constrained by the autouse no-network fixture, so the mock returns canned responses without ever hitting the wire). Assert `generate()` posts to `http://localhost:11434/api/generate` with the configured model name.
- [ ] T032 [US1] `apps/backend/tests/unit/test_no_network_guard.py` — explicit positive test of the autouse fixture: any code path that tries `httpx.get("https://example.com")` must raise. Belt-and-suspenders for NFR-001 so we have a named test pointing at the guard in the validation file.

#### Backend E2E (pytest + httpx)

- [ ] T033 [US1] `apps/backend/tests/e2e/test_documents_e2e.py` — TestClient against the FastAPI app with `ollama_client` patched. Upload `msa-acme.pdf`, assert 200 + `document_id`. List documents, assert it appears. Upload an image-only PDF, assert 422 with the scanned-PDF message. Reject non-PDF extensions and oversized uploads (>10 MB).
- [ ] T034 [US1] `apps/backend/tests/e2e/test_analyze_e2e.py` — TestClient. With `ollama_client.generate_json` patched to return canned `{"contract_type":"MSA"}` then a deterministic findings list (3 valid for `msa-acme.pdf`) then a canned client summary: upload → analyze → assert response shape (`document_id`, `contract_type`, `findings`, `client_summary`). Assert each finding's `quote` exists verbatim in the parsed text. Assert disclaimer present in summary.
- [ ] T035 [US1] `apps/backend/tests/e2e/test_pipeline_no_network.py` — same setup as T034 but explicitly verifies the autouse no-network fixture is active during the full pipeline. The named scenario for the validation file.

**Checkpoint**: At this point, US1 backend slice is fully functional and testable independently with mocked Gemma. Manual scenario then proves real Gemma 4 e4b on the M4 Air also works.

---

## Phase 4: Polish & Cross-Cutting

- [ ] T036 [P] Append `pytest tests/unit` and `pytest tests/e2e` lines to the `test-e2e` recipe in the root `Justfile` (Sprint 0 left a no-op placeholder for backend E2E). Backend E2E now runs alongside Playwright frontend E2E. Carry-forward from sprint-0-validation.md.
- [ ] T037 [P] Add a `verify-sprint-1` recipe to `Justfile`: runs `just install && just check && just test-e2e` and prints a clearly visible `Sprint 1 verification: PASS` line on success.
- [ ] T038 Run `just check` and fix any ruff/mypy/pytest issues. Then run `just test-e2e` and fix any failures. Both must be green before moving on.
- [ ] T039 Delegate to `@code-reviewer` (read-only) — review the diff against Constitution I, II, III, IV, VI, VII, X. Specifically: zero-network test exists and is autouse; citation validator is pure and exhaustively tested; disclaimer field reachable on analyze response; CORS narrowed; no out-of-scope work.
- [ ] T040 Generate `sprints/sprint-1-validation.md` per Constitution X: summary of what changed, list of unit tests added (with what each covers), list of E2E tests added (with what each covers), the seven numbered manual validation scenarios from `sprint-1-backend-slice.md` plus a real-Ollama scenario hitting actual Gemma 4 e4b on `real-msa-edgar.pdf`, and the verification command (`just verify-sprint-1`).
- [ ] T041 Commit to `main` with message "sprint 1: backend vertical slice" and push to `origin`. Hand off to the human for validation.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: T001 done; T002–T003 can start immediately.
- **Phase 2 (Foundational)**: Depends on Setup. T004 (no-network fixture) MUST be first — every later test runs under it. T005–T007 can run in parallel after T004 lands (different files).
- **Phase 3 (US1)**: All tasks depend on Phase 2 complete.
  - Fixtures (T008–T012) and playbooks (T013–T014) are pure-content tasks and can run in parallel with everything else in Phase 3 once started.
  - Pipeline stages (T015–T020) have a chain: parse → classify → load_playbook → validate_citations → analyze → client_summary. T015–T018 are independent and can run in parallel; T019 depends on T015–T018; T020 depends on T019.
  - Routers (T021–T023) depend on storage + pipeline.
  - Unit tests (T024–T032) can be authored in parallel once their target module exists. Most are [P].
  - Backend E2E (T033–T035) require routers + pipeline complete.
- **Phase 4 (Polish)**: Depends on Phase 3 complete. T036–T037 are independent; T038 depends on both; T039 depends on T038; T040 depends on T039; T041 depends on T040.

### Sprint 1 critical path

T004 → T005, T006, T007 → T015–T018 (parallel) → T019 → T020 → T021 → T022 → T023 → T034 (E2E) → T038 → T039 → T040 → T041.

### Parallel Opportunities

- T002, T003 in parallel during Setup.
- T005, T006, T007 in parallel after T004 lands.
- All four fixture tasks (T008–T011) in parallel — different files.
- Both playbook files (T013–T014) in parallel.
- T015, T016, T017, T018 in parallel — different files, no inter-deps.
- All unit tests (T024–T032) in parallel once their target modules exist.
- T036, T037 in parallel during Polish.

---

## Implementation Strategy

### Sprint 1 = MVP backend slice

1. Phase 1 setup (1 task already done; 2 tiny tasks remain).
2. Phase 2 foundational (no-network fixture FIRST, then storage / ollama / prompts in parallel).
3. Phase 3 US1: fixtures + playbooks in parallel with pipeline stages. Routers integrate. Tests follow each module.
4. Phase 4 polish: green `just check` and `just test-e2e`, code review, validation file, commit/push.

**Stop-and-validate** after T038 (green tests). Code review must pass before generating the validation file. Validation file is the gate the human uses to commit.

### Delegation plan

- **`@backend-python`**: T002, T003, T005, T006, T007, T013, T014, T015–T023, T036, T037 (anything in `apps/backend/` or backend-adjacent config).
- **`@test-engineer`**: T004 (autouse fixture), T024–T035 (all unit + E2E tests), T040 (manual scenarios in validation file).
- **`@code-reviewer`**: T039 (read-only diff review).
- **Main agent**: T001 (done), T008–T012 (fixtures + provenance README), T038 (run-and-fix loop), T041 (commit/push), and integration glue.

---

## Notes

- Tests-required for this sprint per Sprint 1 Definition of Done.
- All LLM calls in tests are mocked at the `ollama_client` boundary. Real Gemma 4 e4b is exercised only by the manual validation scenarios.
- The no-network autouse fixture (T004) is the constitutional guard for NFR-001 — any future sprint that breaks it is a Constitution I violation.
- The citation validator (T018) is the unmovable seam between Gemma's output and what reaches the user — Constitution II.
- Sprint 1 deliberately does NOT touch frontend, chat, export, hardware detection, or multi-document support.
