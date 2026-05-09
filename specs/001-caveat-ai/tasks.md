---
description: "Tasks for Caveat AI — Sprint 0 (scaffold repo and tooling)"
---

# Tasks: Caveat AI — Sprint 0 (Scaffold)

**Input**: Design documents from `/specs/001-caveat-ai/`, sprint scope from `/sprints/sprint-0-setup.md`
**Sprint goal**: Repo + tooling ready for Sprint 1 to start writing real code. No pipeline, no Ollama, no UI screens, no PDF parsing.

**Note on user-story mapping**: Sprint 0 implements zero user stories from `spec.md` (those land in Sprints 1–5). Tasks below are pure scaffolding, organized by phase rather than by story. Constitution Principle X still applies: a validation file is required before sprint close.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- No `[Story]` labels in Sprint 0 — see note above

## Hardware-aware model default

This sprint plants the env-overridable model constant **but does NOT call Ollama**. Default value: `gemma4:e4b` (per the operator's M4 Air constraints; production target remains `gemma4:31b-instruct-q4_K_M` per Constitution VIII). Override mechanism: `CAVEAT_MODEL` environment variable.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project layout and dependency manifests in place

- [ ] T001 Create directory tree per `CLAUDE.md` § Project layout: `apps/backend/caveat/{routers,pipeline,llm,export,storage,playbooks}/`, `apps/backend/tests/{unit,e2e}/`, `apps/frontend/src/{pages,tabs,components,api}/`, `apps/frontend/e2e/`, `fixtures/contracts/`. Place `.gitkeep` in empty subfolders that future sprints will populate.
- [ ] T002 [P] Create `apps/backend/pyproject.toml` configured for `uv`. Deps: `fastapi`, `uvicorn[standard]`, `pypdf`, `python-docx`, `weasyprint`, `httpx`, `pydantic`, `pydantic-settings`. Dev deps: `pytest`, `pytest-asyncio`, `ruff`, `mypy`. Python = 3.11. Configure ruff (line-length 100, target-version py311) and mypy (strict on `caveat/`) in the same file.
- [ ] T003 [P] Create `apps/frontend/package.json` (pnpm) with deps: `react`, `react-dom`. Dev deps: `vite`, `@vitejs/plugin-react`, `typescript`, `@types/react`, `@types/react-dom`, `tailwindcss`, `postcss`, `autoprefixer`, `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`, `@playwright/test`, `eslint`, `@typescript-eslint/parser`, `@typescript-eslint/eslint-plugin`. Scripts: `dev`, `build`, `preview`, `test`, `test:e2e`, `lint`, `type-check`.
- [ ] T004 [P] Create `apps/frontend/tsconfig.json`, `apps/frontend/tsconfig.node.json`, `apps/frontend/vite.config.ts`. Vite config must proxy `/api` → `http://localhost:8787` so the React dev server (5173) reaches the backend.
- [ ] T005 [P] Create `apps/frontend/index.html` and `apps/frontend/src/main.tsx`, `apps/frontend/src/index.css` (with `@tailwind base/components/utilities`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting plumbing every later sprint will depend on. Must be complete before T013 onward.

- [ ] T006 Create root `Justfile` with targets: `install`, `dev`, `build`, `start`, `check`, `test-e2e`, `verify-sprint-0`, `demo`. `install` calls `uv sync` in backend and `pnpm install` in frontend. `dev` runs both servers in parallel. `check` = ruff + mypy + pytest (backend) + eslint + tsc + vitest (frontend). `verify-sprint-0` = `just install && just check && just test-e2e`. `demo` is a stub for Sprint 6 (`echo` placeholder is fine).
- [ ] T007 Create `apps/backend/caveat/__init__.py` and `apps/backend/caveat/config.py`. `config.py` exposes `Settings` (pydantic-settings) with `model_name: str = "gemma4:e4b"` overridable via `CAVEAT_MODEL`, plus `host: str = "127.0.0.1"`, `port: int = 8787`, `data_dir: Path` defaulting to `~/.caveat/`. Include a docstring noting `gemma4:31b-instruct-q4_K_M` is the production target and the env var is the switch.
- [ ] T008 [P] Create `apps/backend/.env.example` documenting `CAVEAT_MODEL=gemma4:e4b` (default) with a comment showing the production override line `# CAVEAT_MODEL=gemma4:31b-instruct-q4_K_M`.
- [ ] T009 Create `apps/frontend/tailwind.config.js` and `apps/frontend/postcss.config.js`. Tailwind `theme.extend.colors` mirrors `design-tokens.md`: `bg`, `bg-soft`, `bg-tint`, `ink`, `ink-soft`, `ink-muted`, `line`, `line-soft`, `burgundy` (`#7a1f2b`), `burgundy-soft` (`#faf2f3`), `danger`, `danger-soft`, `warn`, `warn-soft`, `safe`, `safe-soft`, `gold`. `theme.extend.fontFamily`: `serif: ['Fraunces', 'Georgia', 'serif']`, `sans: ['Geist', '-apple-system', 'sans-serif']`, `mono: ['Geist Mono', 'monospace']`. Content globs: `./index.html`, `./src/**/*.{ts,tsx}`.
- [ ] T010 Update root `README.md` quickstart: replace the `ollama pull gemma4:31b-instruct-q4_K_M` line with a two-line block — production tag `gemma4:31b-instruct-q4_K_M` and dev tag `gemma4:e4b` (smaller, fits laptops). Add a "Model selection" subsection explaining `CAVEAT_MODEL` override and noting that proper hardware auto-detection lands in Sprint 5.
- [ ] T011 [P] Add `apps/backend/.gitkeep`-style anchors as needed and verify root `.gitignore` already covers `apps/frontend/dist/`, `apps/backend/static/`, `.venv/`, `node_modules/`, `~/.caveat/`. Patch any gaps.
- [ ] T012 [P] Add `.python-version` (3.11) at backend root, and `.nvmrc` (20) at frontend root if appropriate.

**Checkpoint**: tooling compiles. `just install` should succeed at this point.

---

## Phase 3: Health-check vertical slice

**Purpose**: Prove the wire from browser → React → FastAPI works end-to-end. This is **scaffolding**, not US1.

### Backend

- [ ] T013 Create `apps/backend/caveat/main.py`: a FastAPI app with `GET /api/health` returning `{"status": "ok", "model": settings.model_name}`. CORS allowed only for `http://localhost:5173` (the Vite dev server). Lifespan startup logs the active model name. No Ollama calls.
- [ ] T014 [P] Create `apps/backend/caveat/routers/__init__.py` and `apps/backend/caveat/routers/health.py` to keep the routing pattern future-proof. Wire it into `main.py`.

### Frontend

- [ ] T015 Create `apps/frontend/src/api/client.ts`: a thin `fetch` wrapper that prepends `/api` and never accepts an absolute URL (defends Constitution I from day one — out-of-host calls are impossible by API).
- [ ] T016 Create `apps/frontend/src/App.tsx`: on mount, calls `client.get('/health')`, displays "Backend status: ok" when reachable. Uses Tailwind: serif `text-3xl` heading "Caveat AI", mono uppercase eyebrow "SPRINT 0 — SCAFFOLD", burgundy accent on the status dot. Disconnected state shows "Backend status: unreachable".

---

## Phase 4: Tests (Constitution Principle X gate)

- [ ] T017 [P] Create `apps/backend/tests/__init__.py`, `apps/backend/tests/unit/__init__.py`, and `apps/backend/tests/unit/test_health.py`. Use FastAPI's `TestClient` to assert `/api/health` returns 200, status `"ok"`, and that the `model` field equals `"gemma4:e4b"` by default. Add a second test that monkeypatches `CAVEAT_MODEL=gemma4:31b-instruct-q4_K_M` and asserts the override is reflected.
- [ ] T018 [P] Create `apps/frontend/src/App.test.tsx` (vitest + RTL): mock `fetch` to return `{status:'ok'}`, render `<App/>`, assert "Backend status: ok" appears. Configure `apps/frontend/vitest.config.ts` with `jsdom` and `setupFiles` for `@testing-library/jest-dom`.
- [ ] T019 Create `apps/frontend/playwright.config.ts` (chromium, baseURL `http://localhost:5173`, `webServer` block boots `just dev` or equivalently a backend+frontend pair) and `apps/frontend/e2e/health.spec.ts`. The test loads `/`, waits for "Backend status: ok", asserts the heading "Caveat AI" is visible.
- [ ] T020 Run `just install` from a clean state (delete `.venv` and `node_modules` first, then re-install). Confirm exit code 0.
- [ ] T021 Run `just check`. Confirm exit code 0. Fix any lint/type/unit-test issues without expanding scope.
- [ ] T022 Run `just test-e2e`. Confirm exit code 0. Fix any wiring issues without expanding scope.

---

## Phase 5: Sprint closure (Constitution Principle X)

- [ ] T023 Delegate to `@code-reviewer`: review the diff vs Constitution I, II, IV, VII. For Sprint 0 most of these are forward-looking — main checks: no network calls baked into scaffolding, no fake disclaimers/citations promised that aren't enforced, performance budgets not violated by the dev tooling itself.
- [ ] T024 Generate `sprints/sprint-0-validation.md` per the Constitution-X structure: summary, unit tests added, E2E tests added, numbered manual scenarios, the `just verify-sprint-0` command. Manual scenarios cover the six bullets in `sprint-0-setup.md` § Validation.
- [ ] T025 `git add -A && git commit -m "sprint 0: scaffold repo and tooling"` then `gh repo create caveat-ai --public --source=. --push`. Confirm the push lands and the repo URL is reachable.

---

## Dependencies & Execution Order

- Phase 1 (T001–T005) — no dependencies. T002–T005 can run in parallel after T001.
- Phase 2 (T006–T012) — depends on Phase 1. T008, T011, T012 are [P].
- Phase 3 (T013–T016) — depends on Phase 2. T014 is [P] with T013 only after T013 is staged.
- Phase 4 (T017–T022) — T017 and T018 are [P] after Phase 3. T019–T022 are sequential.
- Phase 5 (T023–T025) — strictly sequential after Phase 4 is green.

## Parallel Example

```bash
# After T001:
T002, T003, T004, T005    # all [P]

# After T007:
T008, T009, T011, T012    # all [P]

# After T016:
T017, T018                # all [P]
```

## Implementation Strategy

Sprint 0 is single-track scaffolding — no incremental MVP slicing. Run phases in order; do not ship Sprint 0 without `sprints/sprint-0-validation.md`.

## Out of scope for Sprint 0 (rejected if proposed)

- Ollama HTTP calls (Sprint 1)
- PDF parsing (Sprint 1)
- Pipeline stages (Sprint 1)
- Any UI screen from `docs/caveat-prototype-v3.html` (Sprint 2)
- Hardware auto-detection logic (Sprint 5)
- Export formats (Sprint 5)
- LICENSE file (Sprint 6 — dev.to submission requires it)

## Notes

- The `model` field on `/api/health` is the only product surface this sprint exposes the Sprint-1 work to. Keep it stable so Sprint 1's Ollama integration can swap implementation without breaking the contract.
- All test mocks use canned data — no real Gemma calls. Constitution I says network calls are forbidden in tests too; if any test inadvertently hits the network, that's a bug to fix in this sprint.
