---

description: "Sprint 2 — Frontend vertical slice. Per-sprint tasks (overwritten each sprint by /speckit.tasks)."
---

# Tasks: Caveat AI — Sprint 2 (Frontend Vertical Slice)

**Input**: `sprints/sprint-2-frontend-slice.md`, `specs/001-caveat-ai/spec.md` (US1 acceptance scenarios — frontend portion, NFR-005 accessibility), `specs/001-caveat-ai/plan.md` (§1 stack, §5 testing strategy), `.specify/memory/constitution.md` (I, IV, VI, X), `design-tokens.md`, `docs/caveat-prototype-v3.html` (screens 01, 03, 04 reference)

**Tests**: REQUIRED (Sprint 2 Definition of Done lists Vitest + one Playwright happy-path test; Constitution X requires unit + E2E for sprint closure).

**Organization**: Strictly scoped to Sprint 2. Sidebar with multiple documents (Sprint 4), Source/Summary tabs (Sprint 3), Chat tab (Sprint 4), Export (Sprint 5), and persistent finding state (Sprint 4 findings router) are explicitly out of scope. Findings accept/dismiss state lives in React only this sprint, ephemeral per page load.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Different file, no dependency on an incomplete task — safe to run in parallel.
- **[Story]**: US1 only this sprint; setup / polish tasks carry no story label.
- All paths relative to repo root.

## Path Conventions

- Frontend source: `apps/frontend/src/...`
- Frontend unit tests: colocated `apps/frontend/src/**/*.test.tsx`
- Frontend E2E: `apps/frontend/e2e/*.spec.ts`
- Backend (one carry-forward tweak only): `apps/backend/caveat/routers/documents.py`, `apps/backend/tests/e2e/test_documents_e2e.py`
- Repo-level: `Justfile`, `sprints/sprint-2-validation.md`

## Locked design decisions (from Sprint 2 brief)

- **Recent reviews**: live `GET /api/documents/`, max 5 visible, empty state copy "Drop your first contract above".
- **Pipeline UX**: 6-stage timed progression; active stage pulses burgundy; fast-forward when backend responds early; hold-pulse on last stage if backend slower than timer; copy-only cold-start hedge.
- **Finding state**: React-only, ephemeral per page load. No backend persistence (Sprint 4 owns that).
- **Cold start**: Processing screen sub-line — *"first analysis after starting may take 3–5 min while Gemma loads into RAM; subsequent analyses are 30–120s"*. No warmup endpoint.
- **Warnings (Constitution VI)**: dedicated banner ABOVE the Findings summary cards; verbatim list, never summarized.
- **Empty findings**: when `findings=[]` AND `warnings.length > 0` → show warnings + *"Analysis incomplete — see warnings above"*, never *"no risks found"*.

---

## Phase 1: Setup

**Purpose**: Add React Router, lock the routing surface, prep the page/tab/component scaffolding directories already created in Sprint 0.

- [ ] T001 Install React Router: `cd apps/frontend && pnpm add react-router-dom@^6.28.0` (single dependency added to `apps/frontend/package.json`; pnpm lock updated). No other npm deps this sprint.
- [ ] T002 [P] Update `apps/frontend/index.html` `<title>` to `"Caveat AI — Local-first contract review"` so the browser tab matches the product. Confirm referrer meta and the no-Google-Fonts comment (Constitution I) remain intact.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Typed API surface every page consumes, plus the always-visible chrome (topbar, disclaimer footer) shared across screens. Must complete before any page lands.

**⚠️ CRITICAL**: No US1 implementation begins until this phase is complete.

- [ ] T003 Extend `apps/frontend/src/api/client.ts` with `apiPostFormData<T>(path: string, body: FormData): Promise<T>` for multipart upload. MUST reuse `assertRelative` and `buildUrl`. MUST NOT set `Content-Type` manually (the browser sets the multipart boundary). Update `apps/frontend/src/api/client.test.ts` to add: (a) FormData call uses `/api/...`, (b) absolute URL refused, (c) non-2xx → ApiError. Existing `apiGet`/`apiPost` tests preserved.
- [ ] T004 [P] Create `apps/frontend/src/api/documents.ts` exporting typed wrappers and types: `DocumentSummary { id, filename, contract_type, page_count, created_at }`, `UploadedDocument { document_id, filename, page_count, contract_type }`, `listDocuments(): Promise<DocumentSummary[]>` (calls `apiGet('/documents/')`), `uploadDocument(file: File): Promise<UploadedDocument>` (builds FormData with field `file`, calls `apiPostFormData('/documents/', form)`). Use exact backend response shapes from `apps/backend/caveat/routers/documents.py` (do not invent fields).
- [ ] T005 [P] Create `apps/frontend/src/api/analyze.ts` exporting types and wrapper: `Finding { severity: 'high'|'medium'|'low'|'missing', title, quote, explanation, redline, ref?: string }`, `ClientSummary { what_this_contract_is, what_youre_committing_to, biggest_risks: string[], recommendation, disclaimer }`, `AnalyzeResponse { document_id, contract_type, findings: Finding[], client_summary: ClientSummary, warnings: string[], elapsed_seconds: number }`, `analyzeDocument(documentId: string): Promise<AnalyzeResponse>` (calls `apiPost('/analyze/' + documentId, {})`). Match exactly the JSON in `apps/backend/caveat/routers/analyze.py` `AnalyzeResponse` model.
- [ ] T006 [P] Create `apps/frontend/src/components/Topbar.tsx` — persistent header (brand "Caveat" + AI tag pill + topbar-divider + topbar-doc context line + status pills on the right). Accept props `{ docContext?: { filename: string; meta?: string }, status?: 'idle' | 'working' }`. Status pill labels: `Local · Gemma 4 · {model}` (from `/api/health` cached on app mount, prop-drilled), `0 network requests`. Working state pulses warn dot. Burgundy AI tag border. Style with Tailwind tokens already in `tailwind.config.js`.
- [ ] T007 [P] Create `apps/frontend/src/components/DisclaimerFooter.tsx` — non-removable footer (Constitution IV) used on every screen with AI output. Renders the canonical line: *"AI-generated output — attorney review required. Caveat AI supports, but does not replace, the lawyer's professional judgment."* Uses mono font, ink-muted color, top border. Exported as default + named.
- [ ] T008 [P] Create `apps/frontend/src/api/health.ts` exporting `getHealth(): Promise<{ status: string; model: string }>` (calls `apiGet('/health')`). Used by App shell to feed Topbar's status pill model name.

**Checkpoint**: API surface and persistent chrome ready. Pages can now be built independently.

---

## Phase 3: User Story 1 — Single-document risk analysis (frontend portion) (Priority: P1) 🎯 MVP

**Goal**: Lawyer drags a PDF onto the browser, sees the processing screen, and lands on the Findings tab with at least 3 findings (or, on E4B, an honest warnings banner with empty-but-explained findings list).

**Independent Test**: From a clean app state, with the backend running and Ollama serving `gemma4:e4b`: `just dev` → drop `fixtures/contracts/msa-acme.pdf` into the upload zone → processing screen appears with timed pipeline → land on Review/Findings within ~30–180s → see findings cards (or warnings banner + honest empty state). Disclaimer footer visible at all times. Burgundy `#7a1f2b` is the only accent. Keyboard-tab through the upload zone → Findings reaches every interactive element with visible focus rings.

### Tests for User Story 1 (REQUIRED — Sprint 2 DoD)

> Vitest unit tests live colocated next to the component (`*.test.tsx`). Playwright E2E lives in `apps/frontend/e2e/`.

- [ ] T009 [P] [US1] Replace `apps/frontend/src/App.test.tsx` with shell tests: routes render the right page (`/` → Upload, `/processing/abc` → Processing with mocked analyze pending, `/review/abc` → Review with Findings active). Use `MemoryRouter` from react-router-dom with `initialEntries`. Disclaimer footer present on all three. Topbar status pill renders model from mocked `/api/health`. (Existing Sprint-0 health-only tests are removed; this file is rewritten.)
- [ ] T010 [P] [US1] Create `apps/frontend/src/pages/Upload.test.tsx`: (a) hero copy renders ("Read the contract.", "Keep the secret."); (b) drop zone renders with click-to-pick fallback button; (c) recent reviews list populates from mocked `listDocuments`; (d) empty recent state shows "Drop your first contract above"; (e) selecting a non-PDF surfaces an error message; (f) successful upload calls `uploadDocument` and navigates to `/processing/{docId}` (assert via mocked `useNavigate`).
- [ ] T011 [P] [US1] Create `apps/frontend/src/pages/Processing.test.tsx`: (a) renders 6 pipeline stages from the prototype with the right copy; (b) initial state has Parse `active`, others `pending`; (c) stages advance on `vi.useFakeTimers()` + `vi.advanceTimersByTime()`; (d) sub-line cold-start copy is present verbatim; (e) when mocked `analyzeDocument` resolves before the timer reaches stage 6, stages fast-forward and `useNavigate` fires `/review/{docId}`; (f) when mocked `analyzeDocument` rejects with a 503 message, an error pane shows the verbatim message + "Back to upload" link; (g) when the timer would exhaust before the response, the active stage stays pulsing (no "complete" deception).
- [ ] T012 [P] [US1] Create `apps/frontend/src/pages/Review.test.tsx`: (a) sidebar shows the loaded document; (b) tab bar lists Findings (active by default), Client summary, Source, Chat; (c) clicking a non-Findings tab shows "Coming in Sprint N" copy with the right sprint number; (d) Re-analyze button is rendered but disabled (placeholder) with title="Sprint 5"; (e) sidebar-footer privacy note is visible.
- [ ] T013 [P] [US1] Create `apps/frontend/src/tabs/Findings.test.tsx`: this is the most important new test file in Sprint 2.
  - **happy path**: 3 findings, `warnings=[]` → 3 cards rendered, warnings banner absent, summary cards reflect counts.
  - **warnings present**: 2 findings + 1 warning string → banner renders ABOVE summary cards with "WARNINGS" mono eyebrow and the warning text verbatim.
  - **honest empty state**: `findings=[]` + warnings non-empty → warnings banner + "Analysis incomplete — see warnings above" copy + NO "no risks found" copy. Assert the exact NEGATIVE: `expect(screen.queryByText(/no risks/i)).toBeNull()`.
  - **truly empty + no warnings**: `findings=[]` + `warnings=[]` → benign "No findings produced" empty state (this is the rare clean path; still no false reassurance).
  - **severity badges**: each of high/med/low/missing maps to the right Tailwind class.
  - **accept toggles state**: clicking ✓ Accept changes the button visual to "Accepted" without removing the card; second click un-accepts.
  - **dismiss hides**: clicking ✕ Dismiss removes the card from the rendered list.
  - **filter chips**: "High only" hides medium/missing; "Accepted (N)" updates the count when an accept happens.
- [ ] T014 [P] [US1] Replace `apps/frontend/e2e/health.spec.ts` with `apps/frontend/e2e/sprint-2-flow.spec.ts`: full upload → processing → findings flow with `page.route()` mocks for `POST /api/documents/`, `POST /api/analyze/{id}`, `GET /api/documents/`, `GET /api/health`. Drop a synthetic in-test PDF (`Buffer.from(...)`), assert: warnings banner visible when present, severity badges visible, accept button visual changes on click, dismiss removes the card, disclaimer footer visible. Plus a second test (`honest empty state`): mock analyze to return `findings=[]` + 2 warnings → assert warnings banner shows both warnings verbatim AND "Analysis incomplete" copy is visible AND "no risks found" copy is absent.

**Checkpoint after T014**: Vitest + Playwright green; the failing-tests-first ethos satisfied because the implementation tasks below are the first thing that flips them green.

### Implementation for User Story 1

- [ ] T015 [US1] Replace `apps/frontend/src/App.tsx` with the shell: `BrowserRouter`, three `Route` entries (`/`, `/processing/:docId`, `/review/:docId`). Layout grid `flex flex-col min-h-screen`. Renders `<Topbar />` (state from `/api/health`), `<Outlet />` for the route, and `<DisclaimerFooter />` at the bottom on every screen. Removes the Sprint 0 placeholder copy. Topbar `docContext` derives from the active route + a small in-memory cache of the active document name (derived from `documents.list` on mount).
- [ ] T016 [US1] Create `apps/frontend/src/pages/Upload.tsx`: matches prototype screen 01 exactly. Two-column `upload-wrap` (lg breakpoint+; stacks on mobile). Hero left: eyebrow "A new instrument · for old standards", title "Read the contract." + `<em>Keep the secret.</em>` (burgundy italic), lead copy verbatim from prototype, hero stats (`0 requests sent`, `~45s avg. analysis`, `128K context window`). Upload right: label "Begin a review", drop zone with `↓` glyph, "Drop PDFs here" + sub "or click · up to 5 documents", recent reviews from `listDocuments()`. Drop zone uses `onDragOver`/`onDragLeave`/`onDrop` with burgundy hover state via local `isOver` state OR `:hover` Tailwind class (prefer Tailwind for `:hover`, JS for `:dragOver`). Click-to-pick uses a hidden `<input type="file" accept="application/pdf">`. PDF-only filter (reject by extension AND `file.type`). On `uploadDocument` success: `navigate('/processing/' + uploaded.document_id, { state: { filename: uploaded.filename } })`. On 415/413/422 errors: surface the backend `detail` verbatim above the drop zone in danger-soft styled box.
- [ ] T017 [US1] Create `apps/frontend/src/pages/Processing.tsx`: matches prototype screen 03. Pulls `docId` from `useParams`, `filename` from router state. Renders `processing-doc-pill` (filename · `parsing | analyzing` meta), `processing-title` "Reading carefully." (burgundy italic em), sub-line **verbatim**: *"Gemma 4 is parsing your contract and cross-referencing the playbook. First analysis after starting may take 3–5 min while Gemma loads into RAM; subsequent analyses are 30–120s. Estimated stages — actual timing varies."* Pipeline of 6 stages from prototype with calibrated dwell times: Parse (1500ms), Classify (5000ms), Load playbook (500ms), Analyze (70000ms), Validate citations (2000ms), Build summary (30000ms). Active stage: `bg-bg-soft`, burgundy pulse on time/dot. Done stages: checkmark, ink-muted text. State machine via `useEffect` + `setTimeout`; each tick advances `currentStage`. When `currentStage === 5` (last stage) the timer holds and lets the analyze response decide completion (no further auto-advance). Fires `analyzeDocument(docId)` on mount. On resolve: fast-forward all remaining stages to "done" then `navigate('/review/' + docId, { state: { analysis, filename } })`. On reject: render error pane with `err.message` + "Back to upload" link, do not navigate. `processing-note` callout: *"Privileged work product — computation is on this device only. You can disconnect from Wi-Fi without affecting the result."* (Constitution I made visible.)
- [ ] T018 [US1] Create `apps/frontend/src/pages/Review.tsx`: matches prototype screen 04. Pulls `analysis` and `filename` from router state (re-fetch via `analyzeDocument` if state missing — covers a hard refresh; a basic loading state is fine, full restore is Sprint 4's job). Layout: `grid grid-cols-[260px_1fr]` for sidebar + main. Sidebar: section label "Documents · 1", one `doc-item active` (filename + `risk-high N↑` + `risk-med M` + page count), Add document button (disabled, title="Sprint 4"). Sidebar footer: privacy note. Main area: tab bar (Findings active w/ count badge, Client summary / Source / Chat as buttons that switch local `activeTab` state), `tab-actions` Re-analyze button (disabled, title="Sprint 5"), `<Findings />` rendered when `activeTab === 'findings'`, `<TabPlaceholder sprint=3 title="Client summary" />` etc. for the other three tabs. The tab badges show: Findings → kept count (danger if any high), Source → page count, Chat → 0.
- [ ] T019 [US1] Create `apps/frontend/src/components/TabPlaceholder.tsx` — simple "Coming in Sprint N" pane: serif heading, mono eyebrow, lead copy. Sprint 3 placeholders for Summary and Source; Sprint 4 placeholder for Chat. Disclaimer footer continues to render at app shell level so it's already present.
- [ ] T020 [US1] Create `apps/frontend/src/tabs/Findings.tsx`: the centerpiece. Props `{ analysis: AnalyzeResponse }`. Layout matches the prototype `findings-wrap`. Order:
  1. **Pane header**: eyebrow "Tab 01 · technical analysis", title `"<N> things <em>worth knowing.</em>"` (use English-pluralized number word for ≤12, else digit; fallback to "Findings" if N=0). Lead copy adapts: "Each finding cites exact language…" when findings present, or just absent when empty.
  2. **WARNINGS banner** (only when `analysis.warnings.length > 0`): burgundy left border (3px), `bg-burgundy-soft`, mono uppercase eyebrow "WARNINGS · model honesty", then a `<ul>` of `analysis.warnings` rendered verbatim (no truncation, no summarization — Constitution VI). Carries `data-testid="warnings-banner"`.
  3. **Findings summary** (always shown): 4-cell grid — High (danger value), Medium (warn value), Missing (ink value), Analysis time (`elapsed_seconds.toFixed(1) + 's'`).
  4. **Filter chips** (only when findings present): All N · High only · Missing · Accepted (M). Local state `activeFilter`.
  5. **Empty states**:
     - `findings=[]` AND `warnings.length>0` → render banner above (already done) + a single muted card: *"Analysis incomplete — see warnings above. The model may be undersized for this contract; consider re-running with `gemma4:31b-instruct-q4_K_M` on capable hardware."* `data-testid="findings-empty-with-warnings"`.
     - `findings=[]` AND no warnings → muted card: *"No findings produced. The contract appears clean against the loaded playbook, but please review manually before accepting this result."* `data-testid="findings-empty-clean"`.
  6. **Finding cards** (one per kept finding after filter): severity badge (`high → bg-danger`, `medium → bg-warn`, `low → bg-gold`, `missing → bg-ink`), serif title, optional `§ ref` mono on right, `finding-quote` (burgundy left-border, burgundy-soft bg, italic serif), `finding-explain` paragraph, `finding-redline` block (only if `redline` non-empty), action row (✓ Accept / Edit (disabled w/ Sprint 4 title) / Ask in chat (disabled w/ Sprint 4 title) / ✕ Dismiss). Local React state `Map<index, 'pending'|'accepted'|'dismissed'>`. Dismissed cards filtered out. Accepted cards keep border-color `safe` and the ✓ button reads "Accepted" (toggle on second click). `accepted` count drives the filter chip badge.
- [ ] T021 [US1] Backend carry-forward (one-line tweak): in `apps/backend/caveat/routers/documents.py`, replace `status.HTTP_413_REQUEST_ENTITY_TOO_LARGE` → `status.HTTP_413_CONTENT_TOO_LARGE` and `status.HTTP_422_UNPROCESSABLE_ENTITY` → `status.HTTP_422_UNPROCESSABLE_CONTENT`. Update `apps/backend/tests/e2e/test_documents_e2e.py` if any assertion references the old constant names. Goal: kill the deprecation warnings emitted during `just test-e2e`. Delegate to `@backend-python`.

**Checkpoint**: User Story 1 fully functional in browser. Disclaimer present, warnings surfaced verbatim, citation block visually distinct in burgundy, no external network calls.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T022 [P] Add `verify-sprint-2` recipe to `Justfile` mirroring `verify-sprint-1`: runs `just install && just check && just test-e2e` then prints `Sprint 2 verification: PASS` and reminds the human to walk the manual scenarios.
- [ ] T023 Run `just check` and fix any lint/type/unit failures end-to-end (cache results for the validation file's test counts).
- [ ] T024 Run `just test-e2e` and fix any backend or Playwright failures; capture timings.
- [ ] T025 Delegate to `@code-reviewer` to review the diff vs `main` against Constitution I (no external URLs in any frontend file), IV (disclaimer non-removable on every screen with AI output), VI (warnings surfaced verbatim, honest empty state), II (citation block visually distinct + structural hooks ready for Sprint 4 wiring), V (every finding can be edited/dismissed), and NFR-005 (keyboard reach + visible focus + WCAG 2.2 AA contrast on burgundy `#7a1f2b` against white).
- [ ] T026 Write `sprints/sprint-2-validation.md` per Constitution X. Sections: Summary of changes (incl. carry-forward T021 addressed), Unit tests added (one bullet per file, what each test pins), E2E tests added, Numbered manual validation scenarios (the 10 from `sprint-2-frontend-slice.md` plus an honest-empty-state scenario), `just verify-sprint-2` command, Caveats/notes for Sprint 3.
- [ ] T027 Commit on `main` with message `sprint 2: frontend vertical slice` and push to `origin/main`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: T001 (router install) blocks T015 (App shell). T002 is independent.
- **Phase 2 (Foundational)**: T003 blocks T004 (uses `apiPostFormData`). T004 blocks T010 + T016. T005 blocks T011 + T017. T006/T007/T008 are independent leaves and block T015.
- **Phase 3 (US1)**: tests T009–T014 are written next to or before their implementations T015–T020 per TDD norm. T015 blocks T016/T017/T018 (route shell must exist first). T018 blocks T020 (Review hosts Findings). T021 (backend) is independent of all React tasks and can run any time after Phase 2 starts.
- **Phase 4 (Polish)**: T022 independent. T023 → T024 → T025 → T026 → T027 sequential.

### Parallel Opportunities

- Phase 1: T001, T002 in parallel (different files).
- Phase 2: T004, T005, T006, T007, T008 in parallel after T003 lands.
- Phase 3 tests: T009, T010, T011, T012, T013, T014 in parallel (different files).
- Phase 3 implementation: T016, T017, T019, T021 can run in parallel after T015. T020 starts after T018.
- T021 (backend tweak) parallelizes against the entire frontend block.

---

## Parallel Example: User Story 1 — tests-first burst

```bash
# Once Phase 2 lands, kick all six test files at once:
Task: "Replace App.test.tsx with shell + routing tests"
Task: "Create pages/Upload.test.tsx"
Task: "Create pages/Processing.test.tsx"
Task: "Create pages/Review.test.tsx"
Task: "Create tabs/Findings.test.tsx"
Task: "Create e2e/sprint-2-flow.spec.ts"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 + Phase 2 land the chrome and the API surface.
2. Phase 3 lands the three pages + Findings tab. After T020 the slice is demo-able.
3. Phase 4 polishes, validates, and commits.

### Incremental Delivery

Each Phase-3 page is independently testable:
- Upload: drag a PDF, observe network request, error states.
- Processing: navigate to `/processing/abc` with a mocked failing analyze, observe the error pane.
- Findings: render with three different `analysis` shapes (happy, warnings, honest-empty) via a tiny in-test mount.

### Risk Watch

- **R1 — Cold start ≈ 4 min on first analyze.** Mitigated by Processing copy + the hold-pulse contract in T011/T017. If the user reports the UI feels broken, we revisit warmup-on-mount in Sprint 5 polish.
- **R2 — System-fallback fonts (no Geist/Fraunces yet).** The serif headlines will render in Georgia / system serif. This is the documented Sprint 5 deferral; do not let visual fidelity slip become a Sprint 2 blocker.
- **R3 — Hard refresh on `/review/:id`.** The router state is lost; T018 includes a thin re-fetch via `analyzeDocument`. On E4B that re-fetches the slow analyze — acceptable for Sprint 2 (real solution lives behind the Sprint 4 findings router).

---

## Notes

- [P] tasks = different files, no dependencies.
- T013 (Findings.test.tsx) is the most important new test file — pins Constitution VI in the UI surface.
- Disclaimer footer renders at App shell level (T015) so every page inherits it automatically. Don't re-add it inside pages.
- Backend tweak T021 stays a one-shot: NO scope creep into chat/findings routers (Sprint 4) or export (Sprint 5).
- Commit at sprint close (T027) is the only commit; per CLAUDE.md, sprints commit directly to `main` with a single clear message.
