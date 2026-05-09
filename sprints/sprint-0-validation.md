# Sprint 0 — Validation

**Status**: Ready for human review
**Generated**: 2026-05-09
**Scope reference**: `sprints/sprint-0-setup.md`
**Verification command**: `just verify-sprint-0`

---

## Summary of what changed

Sprint 0 delivered the scaffolding the rest of the project will be built on. No product features — just the skeleton, tooling, and a single end-to-end "hello" wire from browser → React → FastAPI to prove the plumbing works.

**Implemented:**

- Project layout per `CLAUDE.md` § Project layout (`apps/backend/`, `apps/frontend/`, `fixtures/contracts/`, `.gitkeep` anchors in folders future sprints will fill).
- **Backend** (`apps/backend/`): Python 3.11 + FastAPI managed by `uv`. Hello-world `GET /api/health` returns `{"status":"ok","model":<active>}`. Pydantic-settings `Settings` class with the model name overridable via the `CAVEAT_MODEL` env var (default `gemma4:e4b`, production target documented as `gemma4:31b-instruct-q4_K_M` per Constitution VIII). CORS locked to `http://localhost:5173` only. No HTTP client, no Ollama call, no DB.
- **Frontend** (`apps/frontend/`): React 18 + Vite + TypeScript + Tailwind, managed by `pnpm`. Single page rendering "Caveat AI", a status pill containing `Local · Gemma 4 · <model>`, the "Backend status: ok" line, and a non-conditional disclaimer footer (Constitution IV). `src/api/client.ts` is the only sanctioned outbound path and rejects any absolute URL at runtime (Constitution I guard from day one).
- **Tailwind tokens** (`tailwind.config.js`) mirror `design-tokens.md` exactly: full burgundy/ink/line palette and the Fraunces/Geist/Geist Mono font stacks. Burgundy `#7a1f2b` is wired in even though the scaffold doesn't use it yet (it's there for Sprint 2).
- **Justfile** at the repo root with the eight commands from `CLAUDE.md`: `install`, `dev`, `build`, `start`, `check`, `test-e2e`, `verify-sprint-0`, `demo`. Backend dev tools are invoked as `uv run python -m <tool>` so pyenv shims (if present) cannot intercept.
- **README** quickstart updated to reflect the dev/prod model split and the `CAVEAT_MODEL` override knob.
- **Hardware-aware default**: model defaults to `gemma4:e4b` so Sprint 0 (and Sprint 1's Ollama integration) runs on the operator's M4 Air. Hardware auto-detection (Sprint 5) will replace this manual default with first-launch capability detection.

**Explicitly NOT delivered** (out of scope for Sprint 0):

- The analysis pipeline (Sprint 1)
- Any UI screen from the prototype (Sprint 2)
- Ollama HTTP integration (Sprint 1)
- PDF parsing / document upload (Sprint 1)
- Hardware auto-detection (Sprint 5)
- Export formats (Sprint 5)
- LICENSE file (Sprint 6 — dev.to submission requires it)

---

## Unit tests added

**Backend** — `apps/backend/tests/unit/test_health.py` (2 tests, runs in ~1.3s):

1. `test_health_default_model` — `GET /api/health` returns 200 and JSON `{"status":"ok","model":"gemma4:e4b"}`. Locks the response shape Sprint 1's Ollama integration must preserve.
2. `test_health_env_override` — Monkeypatches `CAVEAT_MODEL=gemma4:31b-instruct-q4_K_M`, clears the `get_settings` LRU cache, rebuilds the app, and asserts the `model` field reflects the override. Proves the production switch works.

**Frontend** — `apps/frontend/src/App.test.tsx` and `apps/frontend/src/api/client.test.ts` (11 tests, runs in ~1.9s):

1. `App.test.tsx::App renders the title and disclaimer footer` — confirms the heading "Caveat AI", the eyebrow, and the disclaimer text are rendered unconditionally (Constitution IV).
2. `App.test.tsx::App displays backend health and model name when fetch succeeds` — mocks `apiGet` to resolve `{status:'ok', model:'gemma4:e4b'}`, asserts "Backend status: ok" and the model name appear in the status pill.
3. `App.test.tsx::App shows unreachable state when fetch rejects` — mocks `apiGet` to reject, asserts "Backend status: unreachable" and the danger-colored dot.
4. `App.test.tsx::App starts in loading state` — deterministic loading state assertion (no flicker).
5. `client.test.ts::apiGet rejects http:// absolute URLs` — Constitution I runtime guard.
6. `client.test.ts::apiGet rejects https:// absolute URLs` — same guard.
7. `client.test.ts::apiGet prepends /api to relative paths` — confirms the path-rewriting behavior.
8. `client.test.ts::apiGet handles a leading slash correctly` — single `/api/...` prefix, no double-slashes.
9. `client.test.ts::apiGet throws on non-2xx responses` — error contract.
10. `client.test.ts::apiPost serializes JSON body and sets headers` — the POST happy path.
11. `client.test.ts::apiPost rejects absolute URLs` — same Constitution I guard on the POST side.

**Total unit suite**: 13 tests, runs in **~3.2s** combined (well under the Constitution X 10-second budget).

---

## E2E tests added

**Frontend** — `apps/frontend/e2e/health.spec.ts` (1 test, ~6.8s including server warmup):

1. `frontend renders backend health response` — Playwright (chromium) test driven by Playwright's `webServer` block which auto-boots BOTH the FastAPI backend (`uvicorn` on `:8787`) AND the Vite dev server (`:5173`). The test:
   - Navigates to `/`
   - Asserts the heading "Caveat AI" is visible
   - Asserts the eyebrow "Sprint 0 — Scaffold" is visible
   - Waits for and asserts "Backend status: ok"
   - Asserts the status pill contains `gemma4:e4b`, `Local`, and `Gemma 4`
   - Asserts the disclaimer footer is rendered (case-insensitive — text is lowercase, Tailwind `uppercase` transforms it visually)

This is the wire-end-to-end proof of the scaffold. Sprint 1's first backend E2E test (pytest+httpx) will append to `just test-e2e` without renaming this target.

---

## Manual validation scenarios

Run these after `just verify-sprint-0` passes. Each scenario lists the exact expected behavior. If any deviates, note it and stop — that's a regression to fix before declaring Sprint 0 done.

### Scenario 1 — Fresh clone install

```bash
# In a temp directory:
git clone <THIS_REPO_URL> caveat-ai-fresh
cd caveat-ai-fresh
just install
```

**Expected**:
- `uv sync` succeeds for the backend, creating `apps/backend/.venv/` with `fastapi`, `pydantic-settings`, `pytest`, `ruff`, `mypy`, etc.
- `pnpm install` succeeds for the frontend, creating `apps/frontend/node_modules/`.
- Exit code 0.
- Total wall time on the M4 Air: typically < 90s for the first run (network-bound for Python wheels and the npm registry).
- **Note**: If you see `pyenv: version '3.11' is not installed`, run `uv python install 3.11` once and re-run `just install`. The `.python-version` file declares 3.11 and uv will use its own managed CPython if pyenv doesn't have it.

### Scenario 2 — Both servers reachable in dev mode

In one terminal:

```bash
just dev
```

**Expected**:
- Backend log line: `INFO:caveat:caveat backend ready, model=gemma4:e4b` and `Uvicorn running on http://127.0.0.1:8787`.
- Vite log line: `VITE v6.x.x ready in <ms>` and `Local: http://localhost:5173/`.

In another terminal:

```bash
curl -s http://localhost:8787/api/health
# Expected: {"status":"ok","model":"gemma4:e4b"}

curl -s http://localhost:5173/api/health
# Expected: same — proves the Vite proxy forwards /api → backend
```

Press `Ctrl-C` in the `just dev` terminal — both processes terminate together.

### Scenario 3 — Frontend proves the wire is connected

With `just dev` still running, open `http://localhost:5173/` in a browser.

**Expected**:
- Page renders without console errors.
- Mono uppercase eyebrow: **SPRINT 0 — SCAFFOLD**.
- Serif heading: **Caveat AI**.
- Status pill with a green dot reads: **Local · Gemma 4 · gemma4:e4b**.
- Below the pill: **Backend status: ok**.
- Footer (mono, uppercase, ink-muted): **AI-GENERATED OUTPUT — ATTORNEY REVIEW REQUIRED**.
- Visit DevTools → Network: only requests are to `localhost:5173` (the page itself) and `localhost:8787` (the proxied `/api/health`). **No requests to any external host**. The `index.html` deliberately does not load Google Fonts — system-font fallbacks render instead until Sprint 5 self-hosts the woff2 files.

### Scenario 4 — `just check` returns green

```bash
just check
```

**Expected**:
- Backend: `ruff` reports "All checks passed!", `mypy` reports "Success: no issues found in 5 source files", `pytest` runs `2 passed` in under 2s.
- Frontend: `eslint` produces no output (max-warnings 0 enforced), `tsc --noEmit` exits clean, `vitest run` reports `11 passed (11)` in under 2s.
- Total wall time: < 15s on the M4 Air.
- Exit code 0.

### Scenario 5 — `just test-e2e` returns green

```bash
just test-e2e
```

**Expected**:
- Playwright auto-boots backend on `:8787` and frontend on `:5173` via its `webServer` block. **Do not** have `just dev` running in another terminal — Playwright's `reuseExistingServer: !process.env.CI` will reuse it locally, but it's cleaner to start from a clean state for validation.
- Console output: `1 passed` and a total wall time of roughly 5-15s (mostly server boot; the test itself runs in ~1s).
- Exit code 0.
- An HTML report is written to `apps/frontend/playwright-report/` (gitignored).

### Scenario 6 — Tailwind tokens are wired

```bash
grep -E "burgundy|7a1f2b" apps/frontend/tailwind.config.js
```

**Expected**: at least one match for `burgundy: '#7a1f2b'` in `tailwind.config.js`.

```bash
grep -E "Fraunces|Geist" apps/frontend/tailwind.config.js
```

**Expected**: matches for `Fraunces`, `Geist`, and `Geist Mono` in the `fontFamily` extension.

### Scenario 7 — Constitution I (zero network) sanity check

With the app NOT running, search for any non-localhost URL in app code:

```bash
grep -rE "https?://(?!(localhost|127\.0\.0\.1))" \
  apps/backend/caveat \
  apps/frontend/src \
  apps/frontend/index.html \
  | grep -v node_modules \
  | grep -v ".venv"
```

**Expected**: no matches. (The `evil.com` strings in `client.test.ts` are negative-path assertions that the runtime guard rejects them — those live in test files, not app code, and are not flagged.)

### Scenario 8 — Constitution VIII (model default) sanity check

```bash
grep -E "gemma4:e4b|gemma4:31b-instruct-q4_K_M" \
  apps/backend/caveat/config.py \
  apps/backend/.env.example \
  README.md
```

**Expected**: dev default `gemma4:e4b` and production target `gemma4:31b-instruct-q4_K_M` both referenced in all three files.

```bash
CAVEAT_MODEL=foo-bar uv run --project apps/backend python -c \
  "from caveat.config import get_settings; print(get_settings().model_name)"
```

**Expected output**: `foo-bar` — proves the env override works at the process level too, not just in the unit test.

### Scenario 9 — Constitution IV (disclaimer) sanity check

With the page open, view the page source (Cmd+U / Ctrl+U) and search for "attorney review required". The disclaimer text is in the rendered HTML, in a non-conditional element. There is no UI control to hide it.

---

## Verification command

```bash
just verify-sprint-0
```

Runs `just install && just check && just test-e2e` and prints a success line. Exit code 0 means the automated suite is green; the human walks through the manual scenarios above to close the sprint.

---

## Caveats and notes for the next sprint

- **Pyenv interaction**: The repo's `.python-version` declares 3.11. If the operator has pyenv installed but doesn't have 3.11 installed via pyenv, `uv` falls back to its own managed CPython (run `uv python install 3.11` once). The `Justfile` invokes backend dev tools as `uv run python -m <tool>` to bypass any pyenv shim that might intercept after the venv is built.
- **Fonts**: `index.html` deliberately does NOT load Google Fonts (Constitution I). System-font fallbacks render. Sprint 5 will bundle Fraunces / Geist / Geist Mono as self-hosted woff2 files.
- **CORS**: `apps/backend/caveat/main.py` allows `*` for methods and headers from the single localhost origin. Sprint 1 should narrow these to the actual methods/headers used as endpoints land. Flagged as a soft note in code review.
- **Backend E2E directory** (`apps/backend/tests/e2e/`) exists but is empty. Sprint 1 will add the first httpx-based test there and append `pytest tests/e2e` to the `test-e2e` Justfile recipe.
- **`.env.example`** is committed; `.env` is gitignored. The operator can copy and customize without leaking secrets.
- The `App.tsx` eyebrow currently reads "Sprint 0 — Scaffold" — Sprint 2 will replace this with the real screen but should keep the disclaimer footer pattern intact.

---

**Sprint 0 is ready for validation.** Run `just verify-sprint-0` and walk through scenarios 1–9 above. Tell me what you find.
