# Sprint 1 — Backend vertical slice

**Duration**: 3 days
**Goal**: The full analysis pipeline works end-to-end via HTTP. POST a PDF, get back validated findings. No UI yet.

## Opening prompt

```
We are starting Sprint 1 of Caveat AI. Sprint 0 should be committed and
verified.

Read in this order:
1. CLAUDE.md
2. .specify/memory/constitution.md (focus: I, II, III, VI, X)
3. specs/001-caveat-ai/spec.md (User Story 1 specifically, plus FR-001 through FR-006, FR-012)
4. specs/001-caveat-ai/plan.md (sections 3 — pipeline)
5. sprints/sprint-1-backend-slice.md

Confirm what you've read and that Sprint 0 is green. Then run /speckit.tasks
for this sprint. Delegate Python work to @backend-python. Delegate test work
to @test-engineer. At the end, @code-reviewer reviews. Then generate
sprints/sprint-1-validation.md.
```

## User stories covered

- **US1** — Single-document risk analysis (backend portion)

## In scope

- `caveat/llm/ollama_client.py` — thin HTTP client to `http://localhost:11434`. The single seam for LLM calls.
- `caveat/llm/prompts.py` — all prompt templates: classify, analyze, client_summary
- `caveat/pipeline/parse.py` — pypdf-based parser; extracts text and detects sections; rejects scanned PDFs
- `caveat/pipeline/classify.py` — calls Ollama, returns one of MSA/NDA/SaaS/Employment/Other
- `caveat/pipeline/load_playbook.py` — reads `caveat/playbooks/{type}.json`
- `caveat/playbooks/msa.json` — at least one playbook, fully filled (US norms for MSA: liability cap, indemnification, termination, IP, confidentiality, governing law, DPA)
- `caveat/playbooks/nda.json` — second playbook for the test set (less detailed is fine, but enough to drive analysis)
- `caveat/pipeline/analyze.py` — calls Ollama with prompt + playbook + contract text, returns structured findings JSON
- `caveat/pipeline/validate_citations.py` — exact substring match. Findings whose quote is not in source are dropped.
- `caveat/pipeline/client_summary.py` — calls Ollama again with validated findings, returns the four-section memo
- `caveat/storage/db.py` — SQLite schema for documents and findings; basic CRUD
- `caveat/routers/documents.py` — POST /api/documents (upload), GET /api/documents (list), DELETE /api/documents/{id}
- `caveat/routers/analyze.py` — POST /api/analyze/{document_id} runs the pipeline, returns findings + summary
- `fixtures/contracts/` — at least 2 public-domain US contracts (one MSA, one NDA) for tests

## Out of scope

- Frontend (Sprint 2)
- Chat endpoint (Sprint 4)
- Findings router (accept/dismiss/edit) — minimal version is fine here, full version is Sprint 4
- Export router (Sprint 5)
- Hardware detection (Sprint 5)
- Multi-document support (Sprint 4)

## Definition of Done

- POST /api/documents with a valid PDF returns a document_id
- POST /api/analyze/{id} returns within 60s on the dev machine, with at least 3 findings, all with validated citations
- Citation validator unit test: bad citations are rejected
- No-network test: `httpx.get` and `requests.get` monkey-patched to raise on non-localhost; full pipeline still passes
- `just check` and `just test-e2e` green
- `sprints/sprint-1-validation.md` exists with manual scenarios

## Validation scenarios required in sprint-1-validation.md

1. Health check: `curl localhost:8787/api/health` returns 200
2. Upload an MSA fixture, get document_id
3. Run analyze, inspect findings JSON: each has severity, title, quote, explanation, optional redline
4. Verify quote of every finding exists in source PDF text (manual grep test)
5. Force a bad citation (manual edit of fake-Ollama response), assert it's dropped from output
6. Run analyze with airplane mode on (or `httpx` patched), assert it works
7. Upload a scanned PDF (image-only), assert clear error message
