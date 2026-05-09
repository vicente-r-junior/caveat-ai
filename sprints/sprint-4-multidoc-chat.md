# Sprint 4 — Multi-document + Chat

**Duration**: 4 days
**Goal**: Up to 5 PDFs loaded simultaneously. Sidebar lists them. Chat tab works with streaming responses and validated citations across all loaded docs.

## Opening prompt

```
We are starting Sprint 4 of Caveat AI. Sprints 0–3 should be committed.

Read in this order:
1. CLAUDE.md
2. .specify/memory/constitution.md (focus: II — citations, III — no invention, VII — performance)
3. specs/001-caveat-ai/spec.md (User Story 3 specifically, FR-008, FR-015, NFR-003)
4. specs/001-caveat-ai/plan.md (section 4 — chat implementation)
5. design-tokens.md
6. docs/caveat-prototype-v3.html — inspect sidebar and Chat tab
7. sprints/sprint-4-multidoc-chat.md

This is the largest sprint. Plan carefully before coding. Confirm scope,
then run /speckit.tasks. Delegate aggressively. Generate
sprint-4-validation.md at the end.
```

## User stories covered

- **US3** — Multi-document chat

## In scope

**Backend:**
- Multi-document support: `/api/documents` POST accepts up to 5 docs cumulatively; rejects the 6th with a clear error
- `caveat/routers/chat.py` — POST /api/chat with SSE response. Streams tokens as they arrive from Ollama.
- Token budget guard: if loaded docs would exceed 100K tokens, refuse to load more and report the count
- Citation post-processor: extracts `<cite>name §X.Y: "..."</cite>` tags from streaming output, validates against source documents, re-emits as structured citation blocks the frontend renders
- `caveat/routers/findings.py` — full version with accept / edit / dismiss / persist

**Frontend:**
- `App.tsx` topbar updated to show document count and active doc
- Sidebar component with document list, active state, mini-stats per doc, "+ Add document" button, footer privacy note
- Document switcher logic — clicking a doc swaps the Findings/Summary/Source tabs to show that doc's data
- `tabs/Chat.tsx` — full implementation matching prototype. Context indicator at top showing doc count and token usage. Message list. Suggested prompts. Composer with chips (`@all docs`, `/cite`, `/redline`).
- SSE consumer in `api/chat.ts` — opens EventSource, streams tokens, renders progressively
- Citation block component shared between Findings and Chat
- Proposed-redline citation variant (green/safe-colored border) for chat-generated redlines

## Out of scope

- Export (Sprint 5)
- Hardware detection / fallback (Sprint 5)
- Per-document playbook customization (out of MVP entirely)

## Definition of Done

- 5 documents can be uploaded; 6th is rejected with clear message
- Chat streams responses with first token under 5 seconds (NFR-003)
- Cross-document chat query works: "which has the harshest liability cap?" returns comparison with citations from each doc
- Token budget guard works: tested by trying to load 5 large PDFs that exceed 100K tokens
- Backend E2E test: cross-document query returns response with valid citation
- Frontend Playwright test: full chat flow with mocked SSE responses
- `just check`, `just test-e2e` green

## Validation scenarios required in sprint-4-validation.md

1. Upload 5 different contracts, verify all show in sidebar
2. Try to upload a 6th, verify clear error message
3. Click each doc in sidebar, verify Findings/Summary/Source update
4. Open Chat tab, verify context indicator shows "5 documents loaded · ~X,000 tokens of 128,000"
5. Ask "which contract has the most aggressive limitation of liability?" and verify a comparison response with at least one citation from the harshest document
6. Verify the citation visible in the chat response actually exists in the source document (cross-check)
7. Ask a follow-up "draft a more aggressive redline of acme §4.2" and verify a proposed-redline block (green border) appears
8. Ask something not in any loaded contract (e.g. "what's the weather in Paris?") and verify the bot says it can't answer from loaded contracts (no hallucination)
9. Time the first token: should arrive within 5 seconds of pressing send
10. Try to load a contract that would push past 100K tokens; verify the budget guard message
