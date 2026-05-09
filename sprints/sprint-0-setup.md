# Sprint 0 — Setup

**Duration**: 1 day
**Goal**: Repository scaffolded, tooling installed, Justfile working, first commit pushed to GitHub. The repo is ready for Sprint 1 to start writing real code.

## Opening prompt for Claude Code

```
We are starting Sprint 0 of Caveat AI.

Read in this order:
1. CLAUDE.md
2. .specify/memory/constitution.md (focus on Principle X)
3. specs/001-caveat-ai/spec.md
4. specs/001-caveat-ai/plan.md (sections 1, 2, 6)
5. sprints/sprint-0-setup.md (this sprint's scope)

Confirm what you've read and which sprint is active. Then run /speckit.tasks
scoped to this sprint, and execute. When all tasks pass, generate
sprints/sprint-0-validation.md per Constitution Principle X.
```

## In scope

- Project directory structure exactly as specified in `CLAUDE.md`
- `pyproject.toml` for backend with all listed Python deps (FastAPI, pypdf, python-docx, weasyprint, pytest, httpx, ruff, mypy)
- `package.json` for frontend with all listed JS deps (React, Vite, TypeScript, Tailwind, vitest, playwright)
- `Justfile` with: `install`, `dev`, `build`, `start`, `check`, `test-e2e`, `verify-sprint-0`, `demo`
- A "hello world" FastAPI app at `apps/backend/caveat/main.py` that returns `{"status": "ok"}` on `GET /api/health`
- A "hello world" React app at `apps/frontend/` that fetches `/api/health` and displays the result
- One unit test (`pytest`) and one component test (`vitest`) confirming the scaffolding works
- One E2E test (Playwright) that loads the frontend and asserts the health response renders
- Tailwind configured with the design tokens from `design-tokens.md` (colors, fonts) wired up
- `tailwind.config.js` extends with the burgundy accent and custom font stacks
- README updated with the actual quickstart commands

## Out of scope (do NOT do these)

- The analysis pipeline (Sprint 1)
- Any UI screen from the prototype (Sprint 2)
- Ollama integration (Sprint 1)
- PDF parsing (Sprint 1)

## Definition of Done

- `just install` succeeds from a clean clone
- `just dev` starts both backend and frontend, both reachable
- `just check` passes (lint + types + unit tests)
- `just test-e2e` passes (the one Playwright test)
- `just verify-sprint-0` runs the above three and confirms green
- `sprints/sprint-0-validation.md` exists with the standard structure
- First commit to `main` with message "sprint 0: scaffold repo and tooling"

## Validation scenarios that must be in sprint-0-validation.md

1. Fresh clone → `just install` succeeds
2. `just dev` opens backend on :8787 and frontend on :5173 with both reachable
3. Frontend loads, shows "Backend status: ok" (or similar) — proves the wire is connected
4. `just check` returns green
5. `just test-e2e` returns green
6. Tailwind colors include burgundy `#7a1f2b` (verifiable by inspecting `tailwind.config.js` or generated CSS)
