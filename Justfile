# Caveat AI — task runner
# All paths are relative to the repo root.
# Backend lives in apps/backend (uv-managed).
# Frontend lives in apps/frontend (pnpm-managed).

set shell := ["bash", "-cu"]

backend := "apps/backend"
frontend := "apps/frontend"

# Default: list available targets
default:
    @just --list

# ----------------------------------------------------------------------
# Install — backend (uv) + frontend (pnpm)
# ----------------------------------------------------------------------
install:
    cd {{backend}} && uv sync
    cd {{frontend}} && pnpm install

# ----------------------------------------------------------------------
# Dev — run backend and frontend in parallel
# Backend: http://localhost:8787
# Frontend: http://localhost:5173 (proxies /api → 8787)
# Ctrl-C kills both.
# ----------------------------------------------------------------------
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' INT TERM EXIT
    (cd {{backend}} && uv run uvicorn caveat.main:app --host 127.0.0.1 --port 8787 --reload) &
    (cd {{frontend}} && pnpm dev) &
    wait

# ----------------------------------------------------------------------
# Build — frontend production build, copied into backend/static
# (The copy step is wired up in Sprint 5 when the production server starts
#  serving static files. For now, build emits to apps/frontend/dist/.)
# ----------------------------------------------------------------------
build:
    cd {{frontend}} && pnpm build

# ----------------------------------------------------------------------
# Start — production-mode local server on :8787
# (Sprint 5 will teach FastAPI to serve the built frontend from /static.
#  For Sprint 0, start is identical to backend-only dev mode without --reload.)
# ----------------------------------------------------------------------
start:
    cd {{backend}} && uv run uvicorn caveat.main:app --host 127.0.0.1 --port 8787

# ----------------------------------------------------------------------
# Check — lint + types + unit tests, both stacks
# Must finish in well under 30s. Constitution X expects unit suite < 10s.
# ----------------------------------------------------------------------
check: check-backend check-frontend

check-backend:
    # Invoke linters as Python modules so pyenv shims (if present) cannot
    # intercept — `uv run python -m <tool>` runs the venv's Python, which
    # imports the tool from the venv's site-packages directly.
    cd {{backend}} && uv run python -m ruff check caveat tests
    cd {{backend}} && uv run python -m mypy caveat tests
    cd {{backend}} && uv run python -m pytest tests/unit -q

check-frontend:
    cd {{frontend}} && pnpm lint
    cd {{frontend}} && pnpm type-check
    cd {{frontend}} && pnpm test

# ----------------------------------------------------------------------
# E2E — Playwright tests (frontend) + pytest+httpx tests (backend)
# Requires `just install` to have run first.
# Backend E2E uses fastapi.testclient; LLM is mocked at the
# ollama_client boundary. Real Gemma is exercised only by the
# manual validation scenarios in sprints/sprint-N-validation.md.
# ----------------------------------------------------------------------
test-e2e:
    cd {{backend}} && uv run python -m pytest tests/e2e -q
    cd {{frontend}} && pnpm test:e2e

# ----------------------------------------------------------------------
# Sprint verification — runs install + check + test-e2e end to end.
# Each sprint owns its own target. Future sprints add verify-sprint-N.
# ----------------------------------------------------------------------
verify-sprint-0:
    just install
    just check
    just test-e2e
    @echo ""
    @echo "Sprint 0 verification passed."
    @echo "Now walk through the manual scenarios in sprints/sprint-0-validation.md."

verify-sprint-1:
    just install
    just check
    just test-e2e
    @echo ""
    @echo "Sprint 1 verification: PASS"
    @echo "Now walk through the manual scenarios in sprints/sprint-1-validation.md."
    @echo "(The real-Ollama scenario requires `ollama serve` running with gemma4:e4b pulled.)"

# ----------------------------------------------------------------------
# Demo — load seed data for the contest demo (Sprint 6).
# Stub for now.
# ----------------------------------------------------------------------
demo:
    @echo "Demo mode lands in Sprint 6. For now: just dev"
