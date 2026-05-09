# Sprint 3 — Client summary + Source viewer

**Duration**: 2 days
**Goal**: Three of the four review tabs functional. Client summary in plain English; source viewer shows the original PDF text with risk passages highlighted.

## Opening prompt

```
We are starting Sprint 3 of Caveat AI. Sprints 0–2 should be committed.

Read in this order:
1. CLAUDE.md
2. .specify/memory/constitution.md (focus: III, IV — disclaimers; V — lawyer in loop)
3. specs/001-caveat-ai/spec.md (User Story 2 specifically)
4. design-tokens.md
5. docs/caveat-prototype-v3.html — inspect Client summary and Source tabs
6. sprints/sprint-3-summary-source.md

Confirm. Run /speckit.tasks. Delegate as appropriate. Generate
sprint-3-validation.md.
```

## User stories covered

- **US2** — Plain-English client summary

## In scope

- `tabs/ClientSummary.tsx` — renders the four-section memo (What this contract is / What you're committing to / The biggest risks / Recommendation), letterhead at top, verdict box, disclaimer footer that cannot be hidden
- Edit-in-place for summary sentences (simple contentEditable or textarea-based, not full WYSIWYG)
- `tabs/Source.tsx` — renders the parsed contract sections from the backend, with highlights on passages that are quoted in any finding. Click a highlight → scroll to that finding in the Findings tab.
- Backend tweak if needed: `/api/analyze` response includes section-structured source text and finding→source-offset mapping
- Tests for both tabs

## Out of scope

- Chat tab (Sprint 4)
- Multi-document support (Sprint 4)
- Export (Sprint 5)

## Definition of Done

- Both new tabs render real data from backend
- Summary disclaimer is rendered and cannot be dismissed via UI
- Source highlights correctly match findings (cross-tab linking works)
- Vitest tests for both tabs
- One Playwright E2E test: switch through all 3 tabs, verify content
- `just check`, `just test-e2e` green

## Validation scenarios required in sprint-3-validation.md

1. From Findings tab, switch to Client summary; the four sections render with content
2. The disclaimer is visible at the bottom; try to remove it via DevTools and confirm it always re-renders
3. Edit a sentence in the summary; verify the edit persists in the local state
4. Switch to Source tab; confirm contract sections render in order
5. Verify the §4.2 passage (or whatever the high-risk finding cites) is highlighted in burgundy
6. Click the highlight; verify it navigates back to Findings with that finding scrolled into view
7. A non-lawyer reads the summary, can answer "what's the recommendation?" and "what are the top 3 risks?" without seeing the contract
