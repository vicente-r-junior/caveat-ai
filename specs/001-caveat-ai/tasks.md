---

description: "Sprint 3 — Client summary + Source viewer. Per-sprint tasks (overwritten each sprint by /speckit.tasks)."
---

# Tasks: Caveat AI — Sprint 3 (Client summary + Source viewer)

**Input**: `sprints/sprint-3-summary-source.md`, `specs/001-caveat-ai/spec.md` (US2 acceptance scenarios 1–3, NFR-005 keyboard reach), `specs/001-caveat-ai/plan.md` (§1 stack, §3 pipeline stages, §5 testing strategy), `.specify/memory/constitution.md` (III no invention, IV disclaimers, V lawyer-in-loop, VI honesty over polish, X per-sprint validation), `design-tokens.md`, `docs/caveat-prototype-v3.html` (Tab 02 `client-doc` + Tab 03 `source-doc` reference)

**Tests**: REQUIRED (Sprint 3 Definition of Done lists Vitest tests for both tabs + one Playwright E2E walking the 3 working tabs; Constitution X requires unit + E2E for sprint closure).

**Organization**: Strictly scoped to Sprint 3. Chat tab (Sprint 4), multi-document sidebar (Sprint 4), summary persistence (Sprint 5), export (Sprint 5), demo seed data (Sprint 6) are explicitly out of scope and any task that drifts into them is rejected.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Different file, no dependency on an incomplete task — safe to run in parallel.
- **[Story]**: US2 only this sprint; setup / foundational / polish tasks carry no story label.
- All paths relative to repo root.

## Path Conventions

- Backend source: `apps/backend/caveat/...`
- Backend unit tests: `apps/backend/tests/unit/test_*.py`
- Backend E2E tests: `apps/backend/tests/e2e/test_*.py`
- Frontend source: `apps/frontend/src/...`
- Frontend unit tests: colocated `apps/frontend/src/**/*.test.tsx`
- Frontend E2E: `apps/frontend/e2e/*.spec.ts`
- Repo-level: `Justfile`, `sprints/sprint-3-validation.md`

## Locked design decisions (from Sprint 3 brief + opening conversation)

- **Source data shape**: section-structured + per-finding offset map. Backend persists parsed sections (number, title, body, char_start, char_end, page) at upload time via a new `sections` SQLite table. A new pipeline stage `map_finding_offsets` tags each finding with `{section_index, start, end}` via exact substring match against the canonical source text. Findings whose quote does not survive section mapping surface a Constitution VI warning rather than a silent miss.
- **`AnalyzeResponse` extension**: gains `source_sections: SourceSection[]`; each `Finding` gains `source_offset: SourceOffset | null` (nullable because the offset stage can fail honestly).
- **Summary edits**: React-only ephemeral state. Edits lost on hard refresh. Persistence lives in Sprint 5's export package work — the lawyer's edited memo will need to flow into the Word/PDF export, which is the natural place to add a backend round trip.
- **Cross-tab linking**: Source `<mark>` click → `setActiveTab('findings')` + `targetFindingIndex` lifted into `Review.tsx`; `Findings.tsx` watches the prop, scrolls the matching card into view, and clears it. No URL routing involvement (would force a route change just to scroll).
- **Disclaimer surfacing on Summary**: the App-shell `DisclaimerFooter` continues to render on every screen (Constitution IV chokepoint, kept). The summary-block's own `.disclaimer` paragraph (US2 acceptance scenario 3 — preserved through export) renders inside the memo card with `data-testid="summary-disclaimer"` and is non-editable.

---

## Phase 1: Setup

**Purpose**: Justfile recipe so the human can verify the sprint with one command.

- [x] T001 [P] Add `verify-sprint-3` recipe to `Justfile` mirroring `verify-sprint-2`: runs `just install && just check && just test-e2e` then prints `Sprint 3 verification: PASS` on success and reminds the human to walk the manual scenarios in `sprints/sprint-3-validation.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Both new tabs render real backend data. The backend must surface `source_sections` + per-finding `source_offset` on `/api/analyze` before either tab can be wired.

**⚠️ CRITICAL**: No US2 frontend implementation begins until Phase 2 lands.

- [x] T002 Extend `Section` dataclass in `apps/backend/caveat/pipeline/parse.py`: add `body: str` and `char_end: int` fields (frozen, slots). Update `_detect_sections` to (a) compute `body` as the contract text from each section's `start_offset` to the next section's `start_offset` (or end of document for the last), (b) compute `char_end = start_offset + len(heading_line + body)`. Add `start_offset` for the very first section that may be 0; emit a synthetic preamble section if any text precedes the first detected heading (so `source_sections` covers the whole document — Constitution VI: do not silently drop preamble text). Pin via unit tests in `apps/backend/tests/unit/test_parse.py`.
- [x] T003 [P] Add `sections` table + accessors to `apps/backend/caveat/storage/db.py`: extend `_SCHEMA_SQL` with `CREATE TABLE IF NOT EXISTS sections (id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE, idx INTEGER NOT NULL, number TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, char_start INTEGER NOT NULL, char_end INTEGER NOT NULL, page INTEGER NOT NULL)` plus `CREATE INDEX IF NOT EXISTS idx_sections_doc_idx ON sections(document_id, idx)`. Add `insert_sections(document_id, sections, path=None) -> list[str]` (mirrors `insert_findings` shape) and `list_sections_for_document(document_id, path=None) -> list[dict]` (oldest-first by `idx`). Schema is additive — `init_db` is idempotent so existing dev DBs gain the table on next startup.
- [x] T004 Wire section persistence into upload in `apps/backend/caveat/routers/documents.py`: after `db.insert_document(...)` returns a `document_id`, call `db.insert_sections(document_id, [{"idx": i, "number": s.number, "title": s.title, "body": s.body, "char_start": s.start_offset, "char_end": s.char_end, "page": s.page} for i, s in enumerate(parsed.sections)])`. No change to the `DocumentResponse` shape — list/get views still omit text.
- [x] T005 [P] Add new pipeline stage `apps/backend/caveat/pipeline/map_offsets.py` exposing `@dataclass(slots=True, frozen=True) class SourceOffset(section_index: int, start: int, end: int)`, `@dataclass(slots=True, frozen=True) class FindingWithOffset(finding: Finding, source_offset: SourceOffset | None)`, and `map_finding_offsets(findings: tuple[Finding, ...], sections: tuple[dict, ...], source_text: str) -> tuple[tuple[FindingWithOffset, ...], tuple[str, ...]]`. Algorithm: for each finding, do `start = source_text.find(finding.quote)` (the citation validator already used the same exact-substring rule, so this should rarely miss); on hit, locate which section by walking sections sorted by `char_start` and finding the largest `char_start <= start`; build a `SourceOffset(section_index=that_idx, start=start, end=start+len(finding.quote))`. On miss (i.e. quote validated by Constitution II but not located by `find` — only possible with overlapping/duplicate-quote edge cases or post-validator string normalization drift), produce a Constitution VI warning verbatim: `"Source viewer: finding '<title>' could not be located in the source text after citation validation. The Source tab will not show its highlight."` and a `None` offset. Module performs zero network I/O.
- [x] T006 Extend `apps/backend/caveat/routers/analyze.py`: add Pydantic models `SourceSection(idx, number, title, body, char_start, char_end, page)` and `SourceOffset(section_index, start, end)`; extend `FindingOut` with `source_offset: SourceOffset | None = None`; extend `AnalyzeResponse` with `source_sections: list[SourceSection]`. In the handler, after `analyze(...)` returns: load `sections = db.list_sections_for_document(document_id)`; call `map_finding_offsets(analysis_result.findings, tuple(sections), text)`; merge offset warnings into the response's `warnings` list (after analyze + summary warnings, in that order so the Findings warnings banner stays grouped). Keep existing 503/502/504 mapping intact.
- [x] T007 [P] Backend unit tests for the offset stage: `apps/backend/tests/unit/test_map_offsets.py`. Cover: (a) every finding maps to a section when quotes are present verbatim; (b) finding whose quote is absent → `source_offset=None` + one warning naming the title verbatim; (c) section selection on a boundary (offset == next section's `char_start` resolves to the later section); (d) two findings whose quotes appear inside the same section both map (no off-by-one); (e) zero findings → empty result + empty warnings. Use plain dataclasses for `Finding` (already in `validate_citations.py`) and a hand-built `sections` list — no Ollama mocking needed.
- [x] T008 Backend tests for the new schema + analyze surface: extend `apps/backend/tests/unit/test_db.py` with a section-CRUD round trip (insert + list returns rows in `idx` order; cascade delete still works); extend `apps/backend/tests/e2e/test_documents_e2e.py` to assert `db.list_sections_for_document(...)` returns a non-empty list after upload of `fixtures/contracts/msa-acme.pdf`; extend `apps/backend/tests/e2e/test_analyze_e2e.py` to pin (a) happy path response carries `source_sections` (non-empty) AND every finding has a `source_offset` whose `(start, end)` slice of the document text equals the finding `quote`; (b) honest empty path (analyze warning, `findings=[]`) still returns a populated `source_sections` so the Source tab renders even when findings are missing.
- [x] T009 [P] Extend frontend types in `apps/frontend/src/api/analyze.ts`: add `export type SourceOffset = { section_index: number; start: number; end: number }` and `export type SourceSection = { idx: number; number: string; title: string; body: string; char_start: number; char_end: number; page: number }`; extend `Finding` with `source_offset: SourceOffset | null`; extend `AnalyzeResponse` with `source_sections: SourceSection[]`. No runtime change; `analyzeDocument` continues to return whatever the backend sends.

**Checkpoint after T009**: `/api/analyze` carries the new shape end-to-end; backend tests green; frontend types compile (re-run `pnpm tsc --noEmit` or `just check`).

---

## Phase 3: User Story 2 — Plain-English client summary + Source viewer (Priority: P1) 🎯

**Goal**: After Sprint 2's Findings tab, the lawyer now has Tabs 02 and 03 functional. Client summary renders the four-section memo with editable sentences and a non-removable disclaimer block; Source renders the parsed contract with severity-tinted highlights anchored on the new offset map, and clicking a highlight jumps back to the matching finding.

**Independent Test**: From a clean app state, run `just dev`, drop `fixtures/contracts/msa-acme.pdf`. After analyze completes (or honest-empty surfaces): switch to Client summary → see four sections with content + verdict box + summary disclaimer line; edit a sentence → see the edit persist within the page; switch to Source → see contract sections in order with highlights on quoted passages; click a highlight → land back on Findings with the matching card scrolled into view. Disclaimer footer visible on every screen. No external network requests in DevTools Network tab.

### Tests for User Story 2 (REQUIRED — Sprint 3 DoD)

> Vitest unit tests live colocated next to the component (`*.test.tsx`). Playwright E2E lives in `apps/frontend/e2e/`. Tests are written first — implementation tasks T014–T017 below are the first thing that flips them green.

- [x] T010 [P] [US2] Create `apps/frontend/src/tabs/ClientSummary.test.tsx` (the most important new test file in Sprint 3 — pins Constitution IV in the summary surface).
  - **happy path**: pass an `analysis` whose `client_summary` has all four fields + 3 biggest_risks + disclaimer. Assert: serif title with the prototype's "*actually reads.*" copy, firm letterhead block visible, four `<section>` blocks render the verbatim content, verdict box renders `recommendation`, summary disclaimer paragraph carries `data-testid="summary-disclaimer"` AND its full text matches `analysis.client_summary.disclaimer`.
  - **disclaimer is non-removable**: get the `summary-disclaimer` node, attempt to remove via `node.remove()`, then trigger a re-render (e.g. by changing a prop on a wrapper). Assert the disclaimer is back in the DOM. (This pins Constitution IV at the component level, mirroring Sprint 2's footer DOM-removal expectation.)
  - **edit-in-place**: click the Edit affordance on the "What this contract is" section → a `<textarea>` appears prefilled with the original prose; type new text; click Save → the rendered `<p>` reflects the new text; the prop is unmodified (assert via a spy on the parent).
  - **edit-then-cancel**: starting fresh, click Edit, type, then Cancel → the rendered `<p>` reverts to the original prop value.
  - **no Edit on disclaimer**: assert there is no Edit affordance inside or adjacent to the `summary-disclaimer` node (Constitution V is for the summary fields the lawyer actually reviews; the disclaimer is structural, not editorial).
  - **biggest_risks renders as `<ul>`** with one `<li>` per entry verbatim.
  - **honest empty fallback path**: pass an `analysis` whose `client_summary` fields are all the canonical fallback strings (`"(missing)"` etc., shape from Sprint 2 fixup). Assert: the four section blocks STILL render with their fallback strings visible (never collapsed or hidden — Constitution VI: lawyer must see the model fell back).

- [x] T011 [P] [US2] Create `apps/frontend/src/tabs/Source.test.tsx`. Pins Constitution III (no invented highlights) and VI (un-located quotes surface a warning).
  - **happy path**: pass `analysis` with 3 `source_sections` and 2 findings whose `source_offset` lands inside section 0 and section 2 respectively. Assert: 3 section blocks rendered in order with mono section number eyebrow + serif title + body; section 0 contains a `<mark>` with `data-finding-index="0"`; section 2 contains a `<mark>` with `data-finding-index="1"`; section 1 contains zero `<mark>` elements (Constitution III — no invented highlights).
  - **severity-tinted classes**: a `high` finding's mark has `data-severity="high"` + Tailwind class containing `bg-danger-soft`; `medium` → `bg-danger-soft` (high+med both treated as danger per visual spec); `low` → `bg-warn-soft`; `missing` → `bg-bg-tint`.
  - **un-located finding**: pass `findings: [{ ..., source_offset: null, title: "Indemnification one-way" }]` AND a corresponding warning string in `analysis.warnings`. Assert: zero `<mark>` elements rendered for that finding; the warning appears verbatim in a Constitution VI banner above the `source-doc` block.
  - **click jumps**: render with an `onJumpToFinding` mock; click the first `<mark>` → mock called with `0`. Press Enter on the focused `<mark>` → mock called again with `0` (keyboard reach, NFR-005).
  - **role + aria**: every `<mark>` is keyboard-focusable (`tabIndex={0}`), has `role="button"` and `aria-label` containing the matching finding title.
  - **document order preserved**: when section 0 has two findings whose offsets are 100–200 and 250–350, the `<mark>` for the first appears before the `<mark>` for the second in the DOM (no off-by-one in the splitter).

- [x] T012 [P] [US2] Extend `apps/frontend/src/pages/Review.test.tsx` (do NOT remove existing tests — Sprint 2 contract carries forward):
  - Click the "Client summary" tab → the "Coming in Sprint 3" placeholder is gone and the firm letterhead "Carter & Voss LLP · Memo" (placeholder copy) renders. Replace the existing Sprint-2 placeholder assertion for this tab.
  - Click the "Source" tab → the new pane renders with at least one section heading from the mocked `source_sections`.
  - Cross-tab jump: with `activeTab='source'` and `analysis` carrying a finding at section 0, click the highlight; assert (a) `activeTab` flips to `'findings'`, (b) the matching finding card receives a `data-finding-target="true"` attribute (set briefly by the scroll handler), (c) `Element.prototype.scrollIntoView` was called (mocked via `vi.spyOn`).
  - Source tab badge now shows `analysis.source_sections.length` rather than `'—'` (closes Sprint 2 carry-forward note 8).

- [x] T013 [P] [US2] Create `apps/frontend/e2e/sprint-3-flow.spec.ts`. Use `page.route()` to mock all four backend endpoints (`/api/health`, `/api/documents/`, `/api/documents/` POST, `/api/analyze/{id}`) — the Vite webServer starts the real frontend, no Ollama needed. The mocked analyze response carries 2 findings + 3 source_sections + offsets that land each finding in a distinct section.
  - **Test 1 — three-tab walkthrough**: navigate via Upload → drop synthetic PDF → Processing → Findings (assert 2 cards) → click Client summary tab (assert four section headings: "What this contract is", "What you're committing to", "The biggest risks", "Recommendation") → assert the summary-disclaimer block is visible verbatim → click Source tab (assert 3 section blocks visible) → assert each finding has at least one `<mark>` highlight → click the first highlight → activeTab flips back to Findings AND the first finding card has `data-finding-target` attribute set OR the page scrolled to it (assert via the data attribute since headless scroll measurement is flaky). Disclaimer footer visible at every checkpoint.
  - **Test 2 — disclaimer is non-removable on Summary**: same setup, navigate to Client summary, then evaluate-in-page `document.querySelector('[data-testid="summary-disclaimer"]')?.remove()`, then trigger a small state change (toggle-edit on a different section) so the component re-renders. Assert `[data-testid="summary-disclaimer"]` is back. Constitution IV pinned.

**Checkpoint after T013**: tests written and red. Implementation tasks below flip them green.

### Implementation for User Story 2

- [x] T014 [P] [US2] Create `apps/frontend/src/tabs/ClientSummary.tsx`. Props `{ analysis: AnalyzeResponse }`. Layout matches prototype `client-doc` (lines 1656–1696):
  1. **Pane header**: eyebrow "Tab 02 · for your client" (mono burgundy uppercase), title `<h1>A version your client <em>actually reads.</em></h1>` (serif, burgundy italic em), lead "Plain English. Three risks named in order. A clear recommendation. Edit before sending."
  2. **Doc card**: `bg-bg-soft` border `line` `rounded-lg`, generous padding (`p-10`), serif by default. Letterhead block at top: "Carter & Voss LLP · Memo" placeholder (mono uppercase eyebrow) + "Re: {analysis.contract_type}" (serif title). Sprint 5 will read the firm name from `~/.caveat/firm.json`; for Sprint 3 the placeholder is acceptable and a TODO comment notes it.
  3. **Four `<section>` blocks**: one per memo field (`what_this_contract_is`, `what_youre_committing_to`, `biggest_risks`, `recommendation`). Each has a serif `<h3>` with the prototype's exact heading copy ("What this contract is", "What you're committing to", "The biggest risks", "Recommendation") and a content block. `biggest_risks` renders as `<ul>` (one `<li>` per entry); the other three render as `<p>`.
  4. **Verdict box**: dedicated styled block around `recommendation` (matches prototype `.verdict` — burgundy left border, burgundy-soft bg, mono "Recommendation" eyebrow, serif body).
  5. **Summary disclaimer**: separate `<p data-testid="summary-disclaimer">{analysis.client_summary.disclaimer}</p>` at the bottom of the doc card, mono-italic, ink-muted color, no border. Renders unconditionally — even when the disclaimer string is the constitutional fallback.
  6. **Edit affordances**: each editable field has a small `<button>Edit</button>` (mono uppercase, ink-muted, no border in resting state, ink-soft underline on hover). Click → swap the `<p>`/`<ul>` for a `<textarea>` prefilled with the current displayed value (initial = prop, subsequent = local state). Save → write into local `Map<field, string>`. Cancel → discard the textarea draft. The disclaimer field has NO Edit button.
  7. **State**: `useState<Map<FieldKey, string>>(new Map())` for edits; render uses `edits.get(field) ?? defaultFromProp(field)`. Edits are ephemeral by design — Sprint 5 wires SQLite persistence as part of the export package.
  8. **Accessibility**: every Edit button keyboard-reachable; textarea has visible focus ring (Tailwind `focus-visible:ring-burgundy`); the disclaimer block is a plain `<p>` with no interactive surface.

- [x] T015 [P] [US2] Create `apps/frontend/src/tabs/Source.tsx`. Props `{ analysis: AnalyzeResponse, onJumpToFinding: (findingIndex: number) => void }`. Layout matches prototype `source-doc` (lines 1699–1733):
  1. **Pane header**: eyebrow "Tab 03 · the original" (mono burgundy uppercase), title `<h1>The contract, <em>annotated.</em></h1>` (serif, burgundy italic em), lead "Risk passages are highlighted. Click any highlight to jump to its finding."
  2. **Constitution VI warnings banner** (only when any `analysis.warnings` entry contains the string "Source viewer:"): `bg-burgundy-soft` 3px burgundy left border, mono "WARNINGS · MODEL HONESTY" eyebrow in burgundy, then `<ul>` of the matching warning lines verbatim. Belt-and-suspenders: the Findings tab also surfaces these (warnings array is shared), but the Source tab repeats them inline so the lawyer who lands on Source first does not miss them.
  3. **Source-doc block**: `bg-bg-soft` border `line` `rounded-lg`, max-width 800px centered, padding 40px 48px, serif font.
  4. **One `source-section` per `analysis.source_sections[]`**: mono burgundy uppercase eyebrow with `§ {section.number} — {section.title}`; serif `<h3>` with `{section.title}`; body block with `font-size: 14px line-height: 1.7 text-align: justify hyphens: auto` (matches prototype CSS). Body is computed by overlaying highlights:
     - Find every `finding.source_offset` with `section_index === section.idx`. Sort by `start` ascending.
     - Walk the section's `body` and emit alternating plain text + `<mark>` spans. The `<mark>` is rendered as `<button role="button" tabIndex={0} data-finding-index={i} data-severity={finding.severity} aria-label="Jump to finding: {finding.title}" class="...severity-tinted...">{slice}</button>`. Click + Enter both call `onJumpToFinding(i)`.
     - Severity → mark class: `high|medium` → `bg-danger-soft` border-bottom `border-danger`; `low` → `bg-warn-soft` border-bottom `border-warn`; `missing` → `bg-bg-tint` border-bottom `border-ink-muted`.
  5. **Edge case**: a finding whose `source_offset` falls outside this section's `[char_start, char_end)` does NOT render here (Constitution III — no invented highlights).
  6. **Edge case**: a finding with `source_offset === null` renders nowhere; the warnings banner above is the only signal.

- [x] T016 [US2] Update `apps/frontend/src/pages/Review.tsx`:
  - Add state `const [targetFindingIndex, setTargetFindingIndex] = useState<number | null>(null)`.
  - Replace the Sprint-2 `TabPlaceholder` for `summary` with `<ClientSummary analysis={analysis} />`.
  - Replace the Sprint-2 `TabPlaceholder` for `source` with `<Source analysis={analysis} onJumpToFinding={(i) => { setActiveTab('findings'); setTargetFindingIndex(i); }} />`.
  - Pass `targetFindingIndex` and `onTargetHandled={() => setTargetFindingIndex(null)}` into `<Findings />`.
  - Update Source tab badge: `analysis.source_sections.length || 0` (closes Sprint 2 carry-forward note 8). Keep Chat tab placeholder pointing at Sprint 4.
  - Re-analyze button stays disabled with title="Sprint 5". Sidebar Add document still disabled with title="Sprint 4".

- [x] T017 [US2] Update `apps/frontend/src/tabs/Findings.tsx` to accept `{ targetFindingIndex?: number | null, onTargetHandled?: () => void }` props (additive — when both are absent the component behaves identically to Sprint 2; existing tests stay green). Implementation:
  - Add `cardRefs = useRef<Map<number, HTMLElement | null>>(new Map())`. Each finding card binds `ref={(el) => cardRefs.current.set(originalIndex, el)}`.
  - `useEffect` on `[targetFindingIndex]`: if non-null, look up the card by `originalIndex`, call `el.scrollIntoView({ behavior: 'smooth', block: 'center' })`, set `data-finding-target="true"` on the card via the ref, after 1500ms remove the attribute, then call `onTargetHandled?.()` so Review clears its state.
  - The accept/dismiss/filter logic is untouched.

- [x] T018 [US2] [P] Update `apps/frontend/src/components/TabPlaceholder.tsx` if its sprint-number copy needs adjustment (Chat is now the only remaining placeholder pointing at Sprint 4). Likely no change required — verify by reading the file and only touching if a hardcoded "Sprint 3" string remains.

**Checkpoint**: 3 of 4 tabs functional with real backend data. `just check` and `just test-e2e` green. Constitution IV/III/V/VI/II all pinned by component-level tests.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [x] T019 Run `just check` end-to-end (lint + type + unit). Fix any lint/type/unit failures. Capture timing for the validation file's test counts: target full unit suite ≤ 10s combined per Constitution X.
- [x] T020 Run `just test-e2e` end-to-end (backend pytest+httpx + Playwright). Fix any failures. Capture timings.
- [x] T021 Delegate to `@code-reviewer` for read-only review of the diff vs `main` against:
  - **III no invention**: Source tab only renders highlights derivable from `source_offset` — no client-side fuzzy match, no regex-found "extra" highlights.
  - **IV disclaimers**: App-shell footer still on every page; summary-disclaimer block in `ClientSummary.tsx` cannot be removed (DOM-removal test pins this); no Edit affordance on the disclaimer.
  - **V lawyer in loop**: Summary edits are reachable, savable, cancellable; edits live in component state and never auto-submit anywhere.
  - **VI honesty over polish**: un-located quote warnings surface verbatim in Source's banner; honest-empty client_summary still renders all four fallback strings.
  - **II citation alignment**: Source highlights use the exact-substring offsets produced by `map_finding_offsets`, which uses the same `find()` semantics as the citation validator — there is no second algorithm that could disagree.
  - **I no external URLs**: no new `http(s)://` literals anywhere in the diff.
  - **NFR-005 keyboard reach**: every `<mark>` button has `tabIndex={0}` + visible focus ring; Edit/Save/Cancel buttons in Summary are keyboard reachable.
- [x] T022 Delegate to `@test-engineer` to write `sprints/sprint-3-validation.md` per Constitution X. Sections: Summary of changes, Unit tests added (one bullet per file naming what each test pins), E2E tests added, Numbered manual validation scenarios — start from the 7 scenarios in `sprints/sprint-3-summary-source.md` and add an airplane-mode pass through the new tabs (Constitution I) and a keyboard-only pass through Summary edit + Source highlight click (NFR-005). The verification command is `just verify-sprint-3`. Caveats / notes for Sprint 4: re-uploaded pre-Sprint-3 documents won't have sections rows (T004 only fires on new uploads — document this); summary edits lost on hard refresh; firm letterhead is still placeholder.
- [x] T023 Commit on `main` with message `sprint 3: client summary + source viewer` (single commit per CLAUDE.md sprint convention). Push to `origin/main` only if the human approves after walking the manual scenarios.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: T001 independent.
- **Phase 2**: T002 → T003 (sections schema needs `body`/`char_end` shape from extended Section). T002 → T005 (offset stage walks Section.body). T003 → T004 (insert needs schema). T004 → T008 (e2e tests assert sections persisted on upload). T005 → T006 (router consumes the new stage). T006 → T009 (frontend types mirror backend). T002–T006 → T007/T008.
- **Phase 3 tests** (T010–T013): depend on T009 (types must compile) but NOT on T014–T017 (TDD: write red, then green).
- **Phase 3 implementation**: T014, T015, T018 are independent leaves. T016 ↔ T017 land together (Review wires the targetFindingIndex prop into Findings). T020's E2E pass requires all of T014–T017.
- **Phase 4**: T019 → T020 → T021 → T022 → T023 sequential.

### Parallel Opportunities

- Phase 2: after T002 lands, T003 + T005 in parallel against different files. T009 in parallel against T007 (different language; touches frontend only).
- Phase 3 tests: T010, T011, T012, T013 in parallel (different files).
- Phase 3 implementation: T014 + T015 + T018 in parallel after Phase 2 closes; T016 + T017 paired.
- T021 + T022 in parallel — code-reviewer is read-only, test-engineer writes a different file.

---

## Parallel Example: User Story 2 — tests-first burst

```bash
# Once Phase 2 lands, kick all four test files at once:
Task: "Create tabs/ClientSummary.test.tsx"
Task: "Create tabs/Source.test.tsx"
Task: "Extend pages/Review.test.tsx with US2 tab assertions"
Task: "Create e2e/sprint-3-flow.spec.ts"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 + Phase 2 land the Justfile recipe and the new backend surface + frontend types.
2. Phase 3 tests + implementation deliver US2 end-to-end.
3. Phase 4 polishes, validates, and commits.

### Incremental Delivery

- After T009 the typed surface is in place; either tab can be implemented first.
- After T014 the Summary tab is demoable in isolation (mock analysis fixture).
- After T015 the Source tab is demoable.
- After T016 + T017 the cross-tab jump works.

### Risk Watch

- **R1 — Section detection regression on outline-numbered contracts.** `_SECTION_RE` was tuned for §-style and decimal-numbered headings. A contract using "I., II., A., 1." outlines would lump everything into the synthetic preamble section. Mitigation: T005's offset stage tolerates this (one giant section is a degraded-but-honest output), and T002's preamble fallback ensures `source_sections` always covers the whole document. Sprint 6 polish could revisit the regex with a wider grammar.
- **R2 — Re-uploaded pre-Sprint-3 documents have no sections rows.** T004 only writes sections for documents uploaded *after* Phase 2 lands. Mitigation: document this in `sprint-3-validation.md` carry-forwards; the lawyer's recovery path is to re-upload. A backfill script would be Sprint 5/6 polish if the issue surfaces during demo prep.
- **R3 — `<mark>` inside `<button>` accessibility.** We render the highlight as a `<button>` for keyboard reach; semantic `<mark>` is sacrificed. Mitigation: `aria-label="Jump to finding: {title}"` on every button; SR users still get the source-section heading semantics. Acceptable trade per NFR-005 priority.
- **R4 — Sprint 5 will need the lawyer's edited summary in the export package.** Today edits are React-only ephemeral. When Sprint 5 lands, it needs to either (a) read the latest edits from a parent's lifted state at export time, or (b) introduce a backend round-trip. Document this in `sprint-3-validation.md` Caveats so Sprint 5's plan starts informed.

---

## Notes

- **[P]** = different files, no dependency on an incomplete task.
- **T010 (ClientSummary.test.tsx)** pins Constitution IV in the summary surface — its DOM-removal assertion is the key constitutional gate for this sprint.
- **T011 (Source.test.tsx)** pins Constitutions III + VI — only-located highlights, un-located warnings surfaced verbatim.
- **T005 (map_offsets.py)** is the new pipeline stage; it must use the same exact-substring rule as the citation validator so the two algorithms cannot disagree on a finding.
- **T009 (analyze.ts)** is purely additive — the existing Sprint 2 fields stay byte-identical so Findings keeps working.
- **Sprint-2 carry-forward closure**: note 8 (Source page-count badge "—" placeholder) closed by T016's badge update. Note 2 (Topbar "0 network requests" hardcoded pill) is OUT OF SCOPE — flagged in `sprint-3-validation.md` Caveats for Sprint 5 polish.
- **Commit at sprint close (T023)** is the only commit per CLAUDE.md sprint convention; per-task commits are not generated. The validation file is the human's gate.
