# Sprint 2 — Frontend vertical slice

**Duration**: 3 days
**Goal**: A lawyer can drag a PDF onto the browser, see the processing screen, then land on the Findings tab and review at least 3 findings with redlines. UI matches the prototype's first three screens.

## Opening prompt

```
We are starting Sprint 2 of Caveat AI. Sprints 0 and 1 should be committed
and verified — backend pipeline works.

Read in this order:
1. CLAUDE.md
2. .specify/memory/constitution.md (focus: IV, V, X)
3. specs/001-caveat-ai/spec.md (User Story 1, NFR-005 accessibility)
4. design-tokens.md
5. docs/caveat-prototype-v3.html — open and inspect screens 01, 02, 04 (Findings tab)
6. sprints/sprint-2-frontend-slice.md

Confirm what you've read. Run /speckit.tasks for this sprint. Delegate to
@frontend-react for UI, @backend-python only if a backend tweak is needed,
@test-engineer for tests, @code-reviewer at the end. Generate
sprint-2-validation.md.
```

## User stories covered

- **US1** — Single-document risk analysis (full, end-to-end through browser)

## In scope

- `App.tsx` shell with React Router and the topbar (brand, AI tag, status pills, no document loaded yet state)
- `pages/Upload.tsx` — matches prototype screen 01 (Empty/Upload). Drag-and-drop zone, recent reviews list, hero copy with "Read the contract. Keep the secret."
- `pages/Processing.tsx` — matches prototype screen 03. Pipeline visible, animated active step, "you can disconnect Wi-Fi" note
- `pages/Review.tsx` — shell with sidebar (1 doc only for now) + tab bar (Findings, Client summary, Source, Chat). Only Findings tab implemented; the other 3 show a "coming soon" placeholder.
- `tabs/Findings.tsx` — matches prototype's Findings pane: summary cards (high / medium / missing / time), filter chips, finding cards with severity badge, citation block, explanation, redline diff, accept/edit/dismiss/ask-in-chat buttons
- `api/documents.ts`, `api/analyze.ts` — typed wrappers around backend endpoints
- Tailwind config fully reflects `design-tokens.md`
- Loading states, error states, empty states for each page

## Out of scope

- Client summary tab (Sprint 3)
- Source tab (Sprint 3)
- Chat tab (Sprint 4)
- Multi-document sidebar with multiple PDFs (Sprint 4)
- Export (Sprint 5)

## Definition of Done

- `just dev` → drag PDF onto browser → processing screen → findings rendered
- Visual matches prototype screens 01, 02, 04 (Findings only) closely; burgundy accent, Fraunces titles, Geist body, Geist Mono pills
- Keyboard navigation works (tab through buttons, focus rings visible)
- One Playwright E2E test: full upload → processing → findings flow
- Vitest tests for: Upload page, Processing page, Findings tab rendering
- `just check`, `just test-e2e` green

## Validation scenarios required in sprint-2-validation.md

1. Open `localhost:5173`, see Upload screen matching prototype
2. Drag MSA fixture into drop zone, verify file accepted
3. Processing screen shows pipeline with steps progressing
4. Land on Review screen, Findings tab active, summary cards correct
5. Three findings visible, each with badge, quote, explanation, redline (where present)
6. Click "Accept" on a finding → button state changes (visual feedback)
7. Click "Dismiss" → finding hides or marks dismissed
8. Tab through all interactive elements with keyboard, focus rings visible
9. Color picker / inspector confirms burgundy `#7a1f2b` is the accent (not generic blue/purple)
10. Tabs other than Findings show "coming soon" placeholder
