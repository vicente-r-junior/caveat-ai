# Caveat AI

> Contract review for lawyers who keep things in-house.

A local-first web application that helps US transactional lawyers review contracts without sending any document to the cloud. Powered by Gemma 4 running locally via Ollama.

**The whole point of this product is what it does NOT do:** no cloud calls, no telemetry, no analytics, no model training on your data. The contract you upload never leaves your machine.

---

## What it does

- **Risk analysis** of uploaded contract PDFs, with mandatory citations to the source text
- **Plain-English client summary** so non-lawyers can understand what they're signing
- **Multi-document chat** — load up to 5 contracts and ask comparative questions
- **Export** to Word memo, signed PDF, redline package, or email blurb

## What it doesn't do (deliberately)

- Talk to the cloud, ever
- Drafting contracts from scratch (use Spellbook for that)
- OCR for scanned PDFs
- Languages other than English
- Jurisdictions outside the United States
- Multi-user collaboration

See [`specs/001-caveat-ai/spec.md`](specs/001-caveat-ai/spec.md) for the complete scope.

---

## Status

Early prototype, built for the [Gemma 4 challenge on dev.to](https://dev.to/devteam/join-the-gemma-4-challenge-3000-prize-pool-for-ten-winners-23in) (deadline May 24, 2026).

## Quickstart

You'll need:

- Python 3.11+
- Node 20+
- [`uv`](https://docs.astral.sh/uv/) and [`pnpm`](https://pnpm.io/) and [`just`](https://just.systems/)
- [Ollama](https://ollama.com/download) installed and running
- 16GB RAM minimum (32GB and a GPU strongly recommended for the 31B model)

```bash
# Pull a model (runs once)
# Production target — capable hardware (32GB+ RAM, GPU or M2 Pro/M3+):
ollama pull gemma4:31b-instruct-q4_K_M

# Development default — laptops (M-series Air, mid-range PC):
ollama pull gemma4:e4b

# Install the app
git clone https://github.com/YOUR_USER/caveat-ai.git
cd caveat-ai
just install

# Run
just start
```

Then open `http://localhost:8787` in your browser.

### Model selection

The default model name is **`gemma4:e4b`** so the app runs on laptops out of the box.
Override at runtime with the `CAVEAT_MODEL` environment variable, e.g.:

```bash
CAVEAT_MODEL=gemma4:31b-instruct-q4_K_M just start
```

`31B is the recommended production model; E4B is used in development on this machine.`
Hardware auto-detection (Sprint 5) will replace this manual switch with first-launch
capability detection — until then, the operator picks explicitly.

### Optional: warm the model at startup (snappier first analyze)

The first analyze call after `ollama serve` starts pays a cold-start
penalty while the model loads into RAM (≈1–3 minutes for E4B on an M4
Air, longer for 31B). If you want the very first upload to feel as fast
as the second one — useful for demos — set `CAVEAT_WARMUP_ON_STARTUP=true`:

```bash
CAVEAT_WARMUP_ON_STARTUP=true just start
```

The backend will fire a tiny "Say 'ok'." generate() during lifespan
startup. Boot takes longer, but the first real analyze is already warm.
Off by default to keep test/CI startup fast and to avoid blocking on
Ollama when you're just developing the API.

### Optional: log every Ollama prompt and response (`CAVEAT_DEBUG_LLM`)

When the analysis comes back empty or with unexpected `warnings`, the
fastest way to find out *why* is to see exactly what Gemma was sent and
what it returned. Set `CAVEAT_DEBUG_LLM=true` to make the Ollama client
emit each call to **stderr**, including the outgoing prompt (truncated
to 4 KB), the raw response, and the offending substring on JSON parse
errors:

```bash
CAVEAT_DEBUG_LLM=true just dev 2> /tmp/caveat-llm.log
# or to see it inline:
CAVEAT_DEBUG_LLM=true just start
```

Off by default — these prints are noisy and would clutter test/CI
output. Use this when investigating why the model produced empty
findings, the wrong schema, or malformed JSON.

## Architecture in one diagram

```
Browser  →  FastAPI (localhost)  →  Ollama (localhost)  →  Gemma 4 31B
                                            │
                                            ▼
                                    SQLite + local files
```

That's the entire architecture. There is no cloud component.

## Project documents

- [`.specify/memory/constitution.md`](.specify/memory/constitution.md) — non-negotiable principles
- [`specs/001-caveat-ai/spec.md`](specs/001-caveat-ai/spec.md) — what we're building
- [`specs/001-caveat-ai/plan.md`](specs/001-caveat-ai/plan.md) — how we're building it
- [`design-tokens.md`](design-tokens.md) — visual identity
- [`docs/caveat-prototype-v3.html`](docs/caveat-prototype-v3.html) — clickable visual prototype

## License

MIT. See `LICENSE`.

## Disclaimer

Caveat AI is an aid for licensed attorneys. Its outputs are not legal advice and do not replace professional review. Use of this software does not create an attorney-client relationship between you and the developers.
