# CLAUDE.md

This file gives Claude Code the persistent context it needs every time it works in this repo. Read this first before answering anything substantial.

## What we are building

**Caveat AI** — a local-first contract review web application for transactional lawyers practicing in the United States. Lawyers upload contract PDFs, the application runs Gemma 4 locally on the lawyer's machine, identifies risk clauses with mandatory citations, generates a plain-English client summary, and lets the lawyer chat with up to 5 loaded documents at once.

The non-negotiable promise: **nothing leaves the machine**. No telemetry, no cloud calls, no external API. The lawyer's privileged work product stays on the lawyer's PC, full stop. This is the entire point of the product.

## Source of truth, in priority order

If two of these conflict, the higher one wins:

1. `.specify/memory/constitution.md` — non-negotiable principles
2. `specs/001-caveat-ai/spec.md` — what we are building and for whom
3. `specs/001-caveat-ai/plan.md` — how we are building it
4. `sprints/sprint-N.md` — the active sprint scope (whatever sprint is in progress)
5. `design-tokens.md` — visual identity
6. `docs/caveat-prototype-v3.html` — visual reference for layout
7. This file (`CLAUDE.md`)

## How we work — sprints

Work is delivered in 7 sprints (Sprint 0 through Sprint 6). Each sprint has its scope defined in `sprints/sprint-N.md`. A sprint is run in one or two focused Claude Code sessions, then committed directly to `main` with a clear commit message.

**At the start of every Claude Code session:**

1. Read in this order: `CLAUDE.md`, `.specify/memory/constitution.md`, the active sprint file in `sprints/`, the relevant user stories from `specs/001-caveat-ai/spec.md`
2. Confirm what you've read out loud and which sprint is active
3. If `tasks.md` doesn't exist for the active sprint, run `/speckit.tasks` to generate it from the sprint scope plus the spec/plan
4. Pick the next unchecked task from `tasks.md` and start

**During a sprint:**

- Stay strictly within the active sprint's scope. Out-of-scope work is rejected.
- Delegate to subagents (see below) when the task fits a subagent's domain.
- Run `just check` after every meaningful change.

**At the end of a sprint:**

You MUST produce `sprints/sprint-N-validation.md`. Per Constitution Principle X, the sprint is not done without it. The file contains:

- Summary of what changed
- Unit tests added and what they cover
- E2E tests added and what they cover
- Numbered manual validation scenarios for the human, each with explicit expected behavior
- The verification command (`just verify-sprint-N`)

Then prompt the human: "Sprint N is ready for validation. Run `just verify-sprint-N` and walk through the manual scenarios in `sprints/sprint-N-validation.md`. Tell me what you find."

## Subagents available in this repo

Four specialized subagents are configured in `.claude/agents/`. The main agent should delegate to them when tasks match their domain:

| Subagent | Use for |
|---|---|
| `backend-python` | Anything in `apps/backend/` — FastAPI routes, pipeline stages, Ollama client, exports, storage, prompts |
| `frontend-react` | Anything in `apps/frontend/` — React components, Tailwind styling, page logic, API calls |
| `test-engineer` | Writing unit tests, E2E tests (Playwright + pytest+httpx), and producing the manual scenarios for `sprint-N-validation.md` |
| `code-reviewer` | Read-only review of the diff before commit. Validates against the constitution: zero-network, citation rules, disclaimers present, performance budgets respected |

Use `@backend-python`, `@frontend-react`, `@test-engineer`, `@code-reviewer` to delegate explicitly. The main agent owns planning, integration, and the validation file.

**Sprint closure flow** (last step of every sprint):

1. Main agent finishes implementation
2. Delegate to `test-engineer` to write/run all tests for the sprint
3. Delegate to `code-reviewer` to review the diff against the constitution
4. Main agent generates `sprints/sprint-N-validation.md`
5. Stop and hand off to the human

## Stack — locked, do not propose alternatives

| Layer | Choice |
|---|---|
| Backend runtime | Python 3.11 + FastAPI |
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS |
| Inference | Ollama (HTTP API on `localhost:11434`) |
| Primary model | `gemma4:31b-instruct-q4_K_M` |
| Fallback model | `gemma4:e4b-instruct` |
| PDF parsing | `pypdf` |
| Word generation | `python-docx` |
| PDF generation | `weasyprint` |
| Storage | SQLite via stdlib |
| Package manager (Python) | `uv` |
| Package manager (JS) | `pnpm` |
| Unit tests (Python) | `pytest` |
| Unit tests (JS) | `vitest` |
| E2E tests (frontend) | `playwright` |
| E2E tests (backend) | `pytest + httpx` |
| Task runner | `just` |

Do **not** suggest swapping any of these for Tauri, Electron, LangChain, vector databases, RAG frameworks, hosted Gemini API, OpenAI, Anthropic Claude API, Pinecone, or any cloud SDK. They are explicitly out of scope per the constitution.

## Project layout

```
caveat-ai/
├── CLAUDE.md
├── README.md
├── Justfile
├── .gitignore
├── design-tokens.md
├── .claude/
│   └── agents/
│       ├── backend-python.md
│       ├── frontend-react.md
│       ├── test-engineer.md
│       └── code-reviewer.md
├── docs/
│   └── caveat-prototype-v3.html
├── .specify/
│   └── memory/
│       └── constitution.md
├── specs/
│   └── 001-caveat-ai/
│       ├── spec.md
│       ├── plan.md
│       └── tasks.md           (generated per-sprint by /speckit.tasks)
├── sprints/
│   ├── README.md
│   ├── sprint-0-setup.md
│   ├── sprint-0-validation.md (generated at end of sprint)
│   ├── sprint-1-backend-slice.md
│   ├── sprint-1-validation.md
│   └── ...
├── apps/
│   ├── backend/
│   │   ├── pyproject.toml
│   │   ├── caveat/
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   ├── pipeline/
│   │   │   ├── llm/
│   │   │   ├── export/
│   │   │   ├── storage/
│   │   │   └── playbooks/
│   │   └── tests/
│   │       ├── unit/
│   │       └── e2e/
│   └── frontend/
│       ├── package.json
│       ├── vite.config.ts
│       ├── tailwind.config.js
│       ├── index.html
│       ├── src/
│       │   ├── App.tsx
│       │   ├── pages/
│       │   ├── tabs/
│       │   ├── components/
│       │   └── api/
│       └── e2e/
│           └── *.spec.ts
└── fixtures/
    └── contracts/
```

## Performance budgets (hard)

- Single-document analysis of a 30-page contract: ≤ 60 seconds on recommended hardware
- Chat: first token streamed within 5 seconds of submission
- App startup to first response served: ≤ 10 seconds (excluding initial model download)

## Commands you can rely on

```bash
just install              # install backend + frontend deps
just dev                  # run backend + frontend in parallel
just build                # build frontend, copy static files into backend
just start                # run production-mode local server on :8787
just check                # lint + type-check + unit tests
just test-e2e             # run all E2E tests
just verify-sprint N      # run the validation block for sprint N
just demo                 # run with seed data loaded for the contest demo
```

If a command doesn't exist yet, propose adding it to the `Justfile` rather than working around it.

## Things that will get rejected if you propose them

- Any external API call from the application (analytics, telemetry, model inference, search, anything)
- Any feature that ships without a disclaimer on its outputs
- Any model output that lacks a validated citation when it claims a fact about a contract
- Multi-tenant features, sign-up/sign-in, user accounts (this is a single-user local app)
- "For the cloud version" — there isn't one
- "Just use OpenAI for now" — no
- Languages other than English in the MVP
- Civil-law jurisdictions in the MVP (US only)
- Skipping the validation file at the end of a sprint
- Working on a task that belongs to a future sprint

## Submission target

Gemma 4 challenge on dev.to, deadline May 24, 2026.

## Sprint 3 — Lessons Learned

These are durable lessons surfaced during Sprint 3 closure. Read them before the next sprint closure walk; they describe categories of failure that automated tests alone do not catch.

### Playwright with `page.route()` is browser-integration, not real E2E

The current `apps/frontend/e2e/` suite mocks all backend responses at the browser layer via `page.route()` for speed (a full Vite + React + jsdom-free Chromium run is already ~10s; adding a real FastAPI + Ollama path would push that to minutes). This catches **browser-level** bugs — React StrictMode dispatch duplication, click handlers, route transitions, focus order — but does NOT exercise the real backend → pipeline → Ollama path. The Sprint 3 fix for the duplicate `POST /api/analyze` was authored against the mocked suite and pinned by `apps/frontend/e2e/analyze-call-count.spec.ts`, which is the right tool for *that* bug because the bug is in the browser.

Implication: until Sprint 5 adds a `just test-real-e2e` recipe driving the live stack against a tiny fixture (or a stubbed-Ollama FastAPI mock returning a canned response in ms), the **manual walk against the real running stack is the only true end-to-end validation**. Treat it as a hard step in sprint closure, not a nice-to-have.

### After code-review PASS, always do a manual walk before committing the final sprint task

Sprint 3 demonstrated that automated tests (109 backend unit + 78 frontend unit + 18 backend E2E + 5 Playwright = 210 tests) and a green code-review can all PASS while real-world behavior is broken. The Sprint 3 duplicate-analyze bug had:

1. A docstring in `Processing.tsx` explicitly stating *"passing the analysis through router state to avoid a re-fetch"*.
2. A `Review.tsx` implementation that ignored the router state and re-fetched anyway.
3. A green `processing-review-transition.test.tsx` that mocked away the StrictMode double-mount behavior.
4. A green `@code-reviewer` PASS that checked implementation in isolation.

All four things were true simultaneously. Only the manual upload of `nda-techcorp.pdf` exposed `POST /api/analyze` appearing twice in the backend log. Per Constitution Principle X (per-sprint validation), the manual walk is non-negotiable; the lesson is to never let "all tests green" stand in for it.

The Sprint 3 fix landed in `Processing.tsx` and `Review.tsx` (useRef-based dedupe scoped by docId, set *before* fetch dispatch) plus a browser-level Playwright counter (`analyze-call-count.spec.ts`) that would have caught the original divergence. The `@code-reviewer` subagent prompt now carries an explicit "documented intent vs. actual implementation" check to make this class of divergence visible at review time.
