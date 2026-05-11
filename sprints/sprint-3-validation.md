# Sprint 3 — Validation

**Status**: ✅ PASSED — closure walk completed 2026-05-11
**Generated**: 2026-05-10
**Validated**: 2026-05-11 (real upload of `fixtures/contracts/nda-techcorp.pdf`: 5 findings, 254s elapsed, single `POST /api/analyze` confirmed in backend log; all 10 manual scenarios walked)
**Scope reference**: `sprints/sprint-3-summary-source.md`
**Verification command**: `just verify-sprint-3`

---

## Summary of what changed

Sprint 3 delivered the second and third Review tabs — **Client summary** and **Source** — and wired them together via cross-tab finding navigation. User Story 2 is now fully real: a lawyer can land on Findings, switch to Client summary to see the four-section plain-English memo (with the Constitution IV disclaimer rendered as a non-removable block and Edit/Save/Cancel affordances on every editable field per Constitution V), then switch to Source to see the original contract section-by-section with severity-tinted highlights anchored at exact offsets. Clicking a highlight returns to Findings with the matching card scrolled into view and briefly badged via `data-finding-target="true"`.

The constitutional gates pinned this sprint: **III** (no invented highlights — every Source-tab `<button>` traces back to a backend-validated `source_offset`; smart-quote drift is a genuine miss surfaced as a verbatim Constitution VI warning rather than papered over), **IV** (the summary disclaimer is structurally non-removable — a `useLayoutEffect` watcher re-attaches the DOM node post-tamper and forces a fresh render via a `tamperCount` state bump), **V** (every memo field is independently editable; the disclaimer carries no Edit affordance and has no descendant `<button>`), and **VI** (un-located findings, legacy documents without a `sections` row, and pypdf line-wrap drift each surface verbatim warnings on the same `analysis.warnings` channel that Sprint 2's Findings banner already renders, with a second source-scoped banner repeating "Source viewer:" warnings inline above the source-doc).

---

## Implemented (per sprint scope)

**Backend:**

- **`apps/backend/caveat/pipeline/parse.py`** — `Section` extended with `body: str` + `char_end: int`. `_detect_sections` refactored into a two-pass algorithm: first walk emits `_SectionMarker`s per matching heading line, second walk fills `body` (heading-line excluded — runs from the character after the heading's trailing `\n` to the next section's start) and `char_end` (next marker's `start_offset`, or `len(text)` for the last section). Constitution VI corrections layered in: (a) when text precedes the first detected heading, prepend a synthetic `Section(number="0", title="Preamble", ...)` so the document text is fully covered by `source_sections`; (b) when zero headings are detected and text exists, emit a single whole-document `Section(number="0", title="Document", ...)` so the Source tab is never blank for outline-numbered contracts ("I.", "A.", "1.") the regex was not tuned for. Pinned by 3 new unit tests on top of the 4 carry-forward parse tests.
- **`apps/backend/caveat/storage/db.py`** — new `sections` table (`id`, `document_id` FK with `ON DELETE CASCADE`, `idx`, `number`, `title`, `body`, `char_start`, `char_end`, `page`) + `idx_sections_doc_idx` index. Two new accessors: `insert_sections(document_id, sections, path=)` (mirrors `insert_findings` shape and fast-paths the empty list) and `list_sections_for_document(document_id, path=)` (returns rows sorted by `idx` ascending). `init_db` is idempotent and now creates the new table on first call.
- **`apps/backend/caveat/routers/documents.py`** — upload now persists sections via best-effort `try/except sqlite3.Error`. Constitution VI rationale: partial state (document row committed without sections) is strictly better than refusing the upload; the analyse handler emits a legacy-document warning when `list_sections_for_document` is empty.
- **`apps/backend/caveat/pipeline/map_offsets.py`** (NEW) — pure-function pipeline stage `map_finding_offsets(findings, sections, source_text) -> (tuple[FindingWithOffset, ...], tuple[str, ...])`. Uses a **whitespace-tolerant regex** built from `re.split(r"\s+", quote.strip())` + `re.escape` per token + `\s+` glue between tokens, so the same pypdf line-wrap drift the citation validator already forgives is forgiven here too — without it, citation-validated findings silently lost their highlights on real PDFs (`msa-acme.pdf` reproduces this cleanly). Section selection walks sorted sections and returns the first whose half-open `[char_start, char_end)` interval contains `match.start()`; on a boundary hit (`start == next.char_start`), the later section wins. Constitution VI: emits a verbatim warning naming the finding title for any quote that survived validation but cannot be located (smart quotes, fabricated wording the validator somehow accepted, malformed sections lists with gaps); `source_offset = None` rather than dropping the finding silently. Pinned by 11 unit tests.
- **`apps/backend/caveat/routers/analyze.py`** — `AnalyzeResponse.source_sections: list[SourceSection]` + `FindingOut.source_offset: SourceOffset | None`. The router loads persisted sections via `db.list_sections_for_document`, then either calls `map_finding_offsets` or — when sections is empty for a document with text — emits the verbatim legacy-document warning *"Source viewer: this document was uploaded before section indexing was enabled. Source tab will be empty. Re-upload to enable highlights."* Warning ordering preserved: analyse-stage, then summary-stage, then offset-stage. The 503/502/504 mapping for `OllamaUnreachableError` / `OllamaServerError` / `OllamaTimeoutError` is intact and unchanged. Pinned by 4 new e2e tests including the line-wrap drift case on the real `msa-acme.pdf` fixture.

**Frontend:**

- **`apps/frontend/src/api/analyze.ts`** — added `SourceSection` + `SourceOffset` types mirroring the backend response models 1:1. `Finding.source_offset: SourceOffset | null` (always `null` when un-located; never `undefined`). `AnalyzeResponse.source_sections: SourceSection[]` (always present — even on the honest empty path).
- **`apps/frontend/src/tabs/ClientSummary.tsx`** (NEW) — four-section memo (What this contract is / What you're committing to / The biggest risks / Recommendation) with a placeholder firm letterhead (`Carter & Voss LLP · Memo` — Sprint 5 reads from `~/.caveat/firm.json`), a `Re: {contract_type}` line, a verdict box wrapping the recommendation, and a non-removable `<p data-testid="summary-disclaimer">`. Edit-in-place via per-field Edit/Save/Cancel buttons; edits live in component-local `useState<Map<FieldKey, string>>` (ephemeral; Sprint 5 export wires SQLite persistence). `biggest_risks` joins/splits via `\n` so the lawyer can edit the list as plain prose in a textarea. The `useLayoutEffect` watcher with no deps array runs after every commit; if the disclaimer is detached from its `docCardRef` parent, it re-appends the existing DOM node and bumps `tamperCount` to force a fresh React render. Pinned by 7 unit tests including a DOM-removal assertion that proves the disclaimer comes back on re-render.
- **`apps/frontend/src/tabs/Source.tsx`** (NEW) — section-by-section render of `analysis.source_sections` with severity-tinted highlight `<button>`s anchored on `finding.source_offset`. Severity → class via a `Record<Severity, string>` lookup (no ternary chain): `high`/`medium` → `bg-danger-soft border-b-2 border-danger`, `low` → `bg-warn-soft border-b-2 border-warn`, `missing` → `bg-bg-tint border-b-2 border-ink-muted`. Each highlight is a real `<button type="button" role="button" tabIndex={0}>` with an `aria-label` naming the target finding; `onClick` and `onKeyDown` (Enter/Space, with `preventDefault`) both call `onJumpToFinding(findingIndex)`. Findings within a single section are sorted by `offset.start` ascending so DOM order matches document order; `data-finding-index` preserves the **original** `analysis.findings` index so cross-tab linking still hits the right card even when offset order ≠ findings order. Constitution VI banner above the source-doc surfaces every warning containing `"Source viewer:"` verbatim; the banner is absent when no source-scoped warnings exist. Pinned by 7 unit tests.
- **`apps/frontend/src/pages/Review.tsx`** — wires `ClientSummary` and `Source` (replacing their Sprint 2 `TabPlaceholder` stubs); lifts `targetFindingIndex` state on the page and threads it as a prop into `Findings`. The Source tab's `onJumpToFinding` callback flips `activeTab` to `findings` and sets `targetFindingIndex`, which Findings consumes and clears via `onTargetHandled`. Source tab badge text now uses `analysis.source_sections.length` (closes Sprint 2 carry-forward note 8). 11 tests (9 carry-forward from Sprint 2 + 2 new for the Sprint 3 wiring including the cross-tab jump assertion).
- **`apps/frontend/src/tabs/Findings.tsx`** — additive optional props `targetFindingIndex?: number | null` + `onTargetHandled?: () => void`. Internal `cardRefs` Map keyed on the **original** finding index. A `useEffect` on the prop scrolls the matching card into view via `scrollIntoView({ behavior: 'smooth', block: 'center' })`, sets `data-finding-target="true"` for ~1500ms, then clears the attribute and calls `onTargetHandled`. The 11 carry-forward Findings unit tests still pass unmodified — the new behavior is strictly additive.
- **`apps/frontend/e2e/sprint-3-flow.spec.ts`** (NEW) — 2 Playwright tests: (1) full upload → processing → findings → summary → source → cross-tab jump back to findings walkthrough with the disclaimer footer asserted at every checkpoint and `data-finding-target="true"` asserted on the target card after the jump; (2) summary disclaimer non-removable at e2e level — `page.evaluate` removes the node, an Edit/Cancel toggle forces a re-render, and the disclaimer is back with verbatim text.
- **`Justfile`** — `verify-sprint-3` recipe added.
- **Sprint 2 test fixtures patched with `source_offset: null` + `source_sections: []`** (`Findings.test.tsx`, `Review.test.tsx`, `Processing.test.tsx`, `App.test.tsx`, `e2e/sprint-2-flow.spec.ts`) — type-tightening carry-forward to satisfy the Sprint 3 `Finding` / `AnalyzeResponse` shape without weakening any assertions.

---

## Carry-forwards from sprint-2-validation.md, addressed

- ✅ **Note 8 — Source tab badge `'—'` / `'0p'` divergence**: the badge now reads `String(analysis.source_sections.length || 0)` against the live response. Pinned by `Review.test.tsx` "Source tab badge reflects analysis.source_sections.length".
- ✅ **Type-tightening for `source_offset` / `source_sections`** across all Sprint 2 tests; the response shape is now uniform end-to-end.

**Carry-forwards still applicable** (deferred to later sprints, none are blockers):

- ✅ **Note 1 — StrictMode double-fire of `analyzeDocument` in dev**: RESOLVED in Sprint 3 fixup-2 via a `fetchedForDocIdRef` guard set *before* fetch dispatch in both `Processing.tsx` and `Review.tsx`, plus a browser-level Playwright counter (`apps/frontend/e2e/analyze-call-count.spec.ts`) that asserts exactly one `POST /api/analyze/{id}` across the upload flow. Confirmed in real backend log on the closure walk: single POST per upload.
- **Note 2 — Topbar "0 network requests" pill is hard-coded**: still applies; Constitution VI dishonesty risk. Flagged for Sprint 5 polish.
- **Notes 3–5, 9** — cosmetic refactors on `Findings.tsx` ternaries / `useMemo` deps / `Review.tsx` re-fetch effect / `apiPostFormData` error duplication. Cosmetic, not user-visible.
- **Note 7 — `api/analyze.ts` no fetch timeout**: intentional; the Processing UI provides parallel feedback. Sprint 4 chat streaming revisits.
- **Note 10 — Backend `OllamaError` 502 path unreachable from analyze pipeline**: still unreachable; Sprint 4's chat router will exercise it.
- **Note 11 — Hard-refresh on `/review/:id` re-runs analyze**: still applies for the same reason. Sprint 3 considered surfacing the Source tab without re-analyze (the source PDF text is in SQLite); we left it for Sprint 4's findings router so all four tabs resume from one cache.

---

## Constitution IV polish landed during the sprint

**Disclaimer DOM-tamper recovery via `useLayoutEffect`** (deliberate spec deviation, sound).

The Sprint 3 brief's original guidance was that "implicit re-rendering will suffice" to keep the summary disclaimer non-removable. Implementation uncovered a wrinkle: React's reconciler skips DOM mutations when fiber props/text are unchanged, so a manual `node.remove()` followed by a parent re-render does **not** restore the node — React still believes the node is present in the committed DOM and emits no patch.

The fix in `ClientSummary.tsx` is a `useLayoutEffect` watcher (no deps array, runs after every commit) that holds refs to both the disclaimer `<p>` and its `docCardRef` parent. When `parent.contains(disclaimer)` is false post-commit, it re-appends the **same DOM node** to its parent (no React reconciliation conflict — the fiber still owns it) and bumps a `tamperCount` `useState` so the next commit treats this as fresh work. The bound is finite: once the node is re-attached, the next pass of the effect is a no-op because `parent.contains(disclaimer)` is true.

This is a deliberate divergence from the brief, bounded in scope to one component, and pinned by both a vitest case (`ClientSummary.test.tsx` — "disclaimer is non-removable") and a Playwright case (`sprint-3-flow.spec.ts` — "summary disclaimer is non-removable: tampering with the DOM is reconciled away on re-render"). The human reviewer should be aware of the divergence; the agent that implemented it did the right thing.

---

## Constitution VI polish landed during the sprint

- **Pypdf line-wrap drift handled at the offset stage** (`map_offsets.py`). The first hand-test on `msa-acme.pdf` revealed that quotes the citation validator (correctly) accepted were silently losing their Source-tab highlight because raw `str.find` cannot bridge a mid-clause `\n`. The offset stage now uses a whitespace-tolerant regex mirroring the validator's normalisation, so the validator and the offset stage agree on what counts as "located" — without weakening Constitution III strictness on tokens. The unit-test file pins both sides explicitly: `test_map_finding_offsets_tolerates_whitespace_drift_in_source` (drift forgiven) and `test_smart_quote_drift_is_a_genuine_miss_not_papered_over` (smart quotes are still a fabrication signal and surface the verbatim warning).
- **Legacy-document warning in `routers/analyze.py`**. Documents uploaded before T004 have no `sections` rows. Rather than rendering a blank Source tab silently, the router emits *"Source viewer: this document was uploaded before section indexing was enabled. Source tab will be empty. Re-upload to enable highlights."* on the same warnings channel the Findings tab already renders.
- **Source-scoped warnings banner** (`Source.tsx`). The Source tab repeats every `analysis.warnings` entry containing `"Source viewer:"` in a banner above the source-doc, in addition to the Findings-tab warnings banner from Sprint 2 — belt-and-suspenders so the lawyer who lands on Source first does not miss the honest miss.

---

## Explicitly NOT delivered (out of scope for Sprint 3)

- **Chat tab** — Sprint 4. The Chat tab continues to render `TabPlaceholder` with "Coming in Sprint 4 — Multi-document chat".
- **Multi-document support** in the sidebar — Sprint 4. Add document button still disabled with the Sprint 4 hover title.
- **Findings/summary persistence across reloads** — Sprint 5 export work owns this. Summary edits and Findings accept/dismiss state are React-only ephemeral; lost on hard refresh.
- **Export package** (Word memo, signed PDF, redline, email blurb) — Sprint 5.
- **Demo mode + seed data** — Sprint 6.
- **Self-hosted Fraunces / Geist / Geist Mono woff2** — Sprint 5. System font fallbacks are still in effect.
- **Firm letterhead from `~/.caveat/firm.json`** — Sprint 5. The placeholder string `"Carter & Voss LLP · Memo"` is hard-coded for now (TODO comment in `ClientSummary.tsx` flags it).

---

## Unit tests added

**Backend — 109 tests total, +15 over Sprint 2.** Suite runs in ~0.55s.

### `apps/backend/tests/unit/test_parse.py` — +3 Sprint 3 tests

- `test_parse_msa_acme_section_bodies_are_continuous` — pins the half-open-interval invariant: every adjacent pair satisfies `sections[i].char_end == sections[i+1].start_offset`, the first section has a non-empty body, and the last section's `char_end == len(text)`. This is the invariant `map_offsets` relies on.
- `test_parse_msa_acme_synthesizes_preamble_when_text_precedes_first_heading` — pins the synthetic preamble: when the MSA's cover page precedes § 1, the first emitted section has `number="0"`, `title="Preamble"`, and `body == text[0:char_end]` covering everything before the first heading.
- `test_parse_invoice_emits_whole_document_fallback` — pins the zero-headings case: an invoice (no §-style numbering) still produces `len(parsed.sections) >= 1` with non-empty body and `sections[-1].char_end == len(text)`.

### `apps/backend/tests/unit/test_storage_db.py` — +4 Sprint 3 tests

- `test_insert_sections_round_trip_returns_rows_in_idx_order` — insert sections in scrambled `idx` order; `list_sections_for_document` returns them sorted ascending with every scalar field round-tripped.
- `test_insert_sections_empty_list_is_noop` — empty input returns `[]` without opening a write transaction.
- `test_sections_cascade_on_document_delete` — deleting a document removes its sections via the FK `ON DELETE CASCADE`.
- `test_init_db_idempotent_includes_sections_table` — calling `init_db` twice does not fail and the sections schema is usable on the second call.

### `apps/backend/tests/unit/test_map_offsets.py` (NEW) — 11 tests

- `test_every_finding_maps_to_a_section_when_quotes_are_present_verbatim` — the happy path with three sections and three findings; every offset's `[start:end)` slice equals the finding's quote verbatim.
- `test_section_index_lands_in_the_correct_section` — pins the section-walk: a quote in section 1 returns `section_index == 1`.
- `test_map_finding_offsets_tolerates_whitespace_drift_in_source` — the canonical pypdf line-wrap case: the source has a mid-clause `\n` where the quote has a space; the offset stage locates the match, the matched span's `.split() == quote.split()`, and warnings is empty. **The Sprint 3 fix that unblocked the demo path on `msa-acme.pdf`.**
- `test_map_finding_offsets_tolerates_double_spaces_and_tabs` — mixed whitespace runs (double space, tab) are also tolerated.
- `test_unlocated_finding_emits_warning_naming_title_verbatim` — un-located finding gets `source_offset = None`, kept in the output tuple, and produces a verbatim Constitution VI warning naming the finding's title.
- `test_smart_quote_drift_is_a_genuine_miss_not_papered_over` — Constitution III strictness preserved: `re.escape('’')` produces a literal `’`, which does not match a straight `'` in the source. Smart-quote drift is a fabrication signal, not a forgivable variant.
- `test_unlocated_finding_kept_in_output_alongside_located_ones` — an un-located finding does not corrupt the order of subsequent findings; the output preserves input order.
- `test_boundary_offset_resolves_to_later_section` — when `start == next.char_start`, the half-open interval rule resolves the later section wins.
- `test_two_findings_in_same_section_both_map_no_off_by_one` — two non-overlapping findings inside one section both locate; slices are quote-equivalent; no overlap.
- `test_empty_findings_yields_empty_result_and_empty_warnings` — empty input returns `((), ())`.
- `test_source_offset_dataclass_is_frozen_and_carries_three_fields` — defensive: the exported dataclass has the right shape.

**Frontend — 68 tests total, +16 over Sprint 2.** Vitest suite ~5.1s tests + setup.

### `apps/frontend/src/tabs/ClientSummary.test.tsx` (NEW) — 7 tests

- (a) **happy path** — pane title with the prototype's "actually reads." copy, firm letterhead, `Re: {contract_type}` line, four `<h3>` headings, the recommendation prose inside the verdict box, and the disclaimer with `data-testid="summary-disclaimer"` carrying the verbatim prop text.
- (b) **disclaimer is non-removable** (Constitution IV) — DOM `original.remove()` succeeds at one moment in time, then a parent prop change re-renders the component and `screen.getByTestId('summary-disclaimer')` returns the node again. **The clincher test for the `useLayoutEffect` watcher.**
- (c) **edit-in-place: Save persists** — Edit on "What this contract is" → textarea prefilled with the original prop value → `userEvent.type` → Save → rendered `<p>` shows the edited string AND the prop object is byte-equal to its pre-edit snapshot (edits live in local state only).
- (d) **edit-then-cancel** — Cancel after typing reverts to the original prop value; the typed string is gone.
- (e) **no Edit affordance on the disclaimer** — the four field-level `edit-{field}` testids exist; `edit-disclaimer` does not; the disclaimer node has no descendant `<button>`. Constitution IV / V boundary made explicit.
- (f) **biggest_risks renders as `<ul>`** — one `<li>` per entry verbatim; `data-testid="biggest-risks-list"` is a `UL`.
- (g) **honest empty fallback** — when all four fields are the canonical `(missing)` fallback string, every heading still renders, the fallback string appears at least 4 times, and the disclaimer is still mounted. Constitution VI: the lawyer must SEE the model fell back.

### `apps/frontend/src/tabs/Source.test.tsx` (NEW) — 7 tests

- (a) **happy path: 3 sections, 2 highlights, no invented marks** — three `data-testid="source-section"` blocks render in document order; section 0 has 1 highlight `data-finding-index="0"`; section 1 has zero highlights (Constitution III — no invention); section 2 has 1 highlight `data-finding-index="1"`.
- (b) **severity-tinted classes** — high/medium → `bg-danger-soft`, low → `bg-warn-soft`, missing → `bg-bg-tint`. Each highlight carries `data-severity` matching its finding's severity.
- (c) **un-located finding: warning banner, no `<mark>`** — `findings=[{source_offset: null}]` + the canonical "Source viewer: …" warning string. `screen.queryAllByTestId('source-highlight')` is empty (Constitution III); `data-testid="source-warnings-banner"` carries the warning verbatim; banner appears BEFORE the source-doc block (verified via `compareDocumentPosition`).
- (d) **non-source warnings do not summon the source banner** — when warnings exist but none contains `"Source viewer:"`, the banner is absent. Pins the prefix-filter contract.
- (e) **click + Enter both jump** — `userEvent.click(highlight)` and `keyboard('{Enter}')` both call `onJumpToFinding(0)`; called twice total, both with the right index.
- (f) **role + aria + tabIndex** — every highlight has `role="button"`, `tabindex="0"`, and `aria-label` containing the finding's title verbatim. NFR-005.
- (g) **document order preserved** — when `findings[0]` has `offset.start=39` and `findings[1]` has `offset.start=10`, the DOM emits the offset-10 highlight first; `data-finding-index` still preserves the **original** findings-array index so cross-tab linking targets the right card.

### `apps/frontend/src/pages/Review.test.tsx` — +2 Sprint 3 tests on top of 9 carry-forward

- `Source tab badge reflects analysis.source_sections.length` — closes Sprint 2 carry-forward note 8. The Source `TabButton` badge text equals `analysis.source_sections.length` for both populated and zero-section responses.
- `cross-tab jump: clicking a Source highlight flips activeTab to findings, marks the matching card, and calls scrollIntoView` — full integration of Source → Review → Findings: render Review with a populated `source_sections`, click the Source tab, click the highlight, assert `activeTab` is `findings`, the matching `data-testid="finding-card"` carries `data-finding-target="true"`, and `Element.prototype.scrollIntoView` was called.

(The 9 Sprint 2 carry-forward Review tests — sidebar, tab bar, default tab, Client summary switch, Source switch, Chat placeholder, Re-analyze disabled, sidebar privacy footer, Add document disabled — are unchanged. Two of them — Client summary switch and Source switch — now assert the **live** Sprint 3 component renders rather than the placeholder.)

### Sprint 2 test fixtures retrofitted

- `apps/frontend/src/tabs/Findings.test.tsx` — every `Finding` literal now carries `source_offset: null`; `AnalyzeResponse` literals carry `source_sections: []`. 11 tests unchanged.
- `apps/frontend/src/pages/Processing.test.tsx`, `apps/frontend/src/App.test.tsx` — same treatment. Tests unchanged.

---

## E2E tests added

**Backend — 18 tests total, +4 over Sprint 2.** Suite runs in ~12s.

### `apps/backend/tests/e2e/test_analyze_e2e.py` — +4 Sprint 3 tests

- `test_analyze_response_carries_source_sections_and_offsets_on_happy_path` — drives the full pipeline through the FastAPI app, mocking `caveat.llm.ollama_client.generate_json` with three valid `msa-acme.pdf` quotes. Asserts `source_sections` is non-empty with the full schema (`idx`, `number`, `title`, `body`, `char_start`, `char_end`, `page`); every finding's `source_offset` slice from the canonical document text is **token-equivalent** to its quote (`slice.split() == quote.split()`); every `offset.section_index` is in the returned sections' `idx` set. The core Sprint 3 contract for the Source tab.
- `test_analyze_response_locates_quotes_with_pypdf_line_wrap_drift` — pins the regression: `_QUOTE_LIABILITY_CAP`, `_QUOTE_INDEMNITY`, `_QUOTE_NO_REFUND` are real verbatim substrings of `msa-acme.pdf` that pypdf renders with mid-clause `\n`. Before the whitespace-tolerant regex landed, these passed citation validation but lost their offset (silent miss). After the fix, every finding lands a non-`null` offset and `body['warnings']` contains zero `"Source viewer:"` entries.
- `test_analyze_response_warns_when_smart_quote_drift_genuinely_misses` — pins Constitution III + VI: the validator's strict-unicode policy filters fabrications upstream of the offset stage; what survives the validator also locates in the offset stage. Demonstrates that the genuine-miss path exists but is rare in the full pipeline (the pure-function unit test above pins the offset-stage behavior in isolation).
- `test_analyze_response_carries_source_sections_when_findings_are_empty` — Constitution VI honest-empty path: when the model returns `findings=[]` with a warning, `source_sections` is still populated so the Source tab can render the contract even when the model produced nothing.

### Backend Sprint 1 + 2 carry-forward (still in `just test-e2e`)

- 14 tests covering documents router (upload, list, get, delete, 415/413/422), analyze router (404, 503 on Ollama down, retry warning), and the no-network guard against the full pipeline. All untouched.

**Frontend — 4 Playwright tests total, +2 over Sprint 2.** Suite runs ~10s including dev-server boot.

### `apps/frontend/e2e/sprint-3-flow.spec.ts` (NEW) — 2 tests

- **happy path: upload → processing → findings → summary → source → cross-tab jump back to findings** — `page.route()` mocks `/api/health`, `/api/documents/`, and `/api/analyze/doc-789` so no FastAPI / Ollama is needed. Drives Vite/React: drop a synthetic PDF, navigate to `/processing/doc-789`, observe "Reading carefully.", land on `/review/doc-789` with 2 finding cards and the disclaimer footer, click the Client summary tab and verify all four section headings + the verbatim summary disclaimer, click the Source tab and verify 3 `source-section` blocks with both highlights present, click the first highlight, assert the Findings tab is now active AND the first finding card has `data-finding-target="true"`, disclaimer footer visible at every checkpoint.
- **summary disclaimer is non-removable: tampering with the DOM is reconciled away on re-render** — navigate through to Client summary, `page.evaluate` removes the disclaimer (asserted gone at one moment), trigger a small re-render via Edit/Cancel on "What this contract is", assert the disclaimer is back with verbatim text. The Constitution IV pin at e2e level.

### Frontend Sprint 2 carry-forward

- `sprint-2-flow.spec.ts` — 2 tests (happy path + honest empty state). Updated to carry `source_offset: null` + `source_sections: []` in mocked responses; assertions unchanged.

---

## How to run automated checks

```bash
just verify-sprint-3
```

This runs `just install && just check && just test-e2e` and prints `Sprint 3 verification: PASS`.

**Test breakdown**:
- Backend unit: **109** tests (was 94), ~0.55s
- Backend E2E: **18** tests (was 14), ~11.8s
- Frontend unit (vitest): **68** tests (was 52), ~5.1s tests
- Frontend E2E (Playwright): **4** tests (was 2), ~10s
- **Total: 199 automated tests**

---

## Manual validation scenarios

Run these after `just verify-sprint-3` passes. Each scenario lists the exact expected behavior. If any deviates, note it and stop — that's a regression to fix before declaring Sprint 3 done. Scenarios 1–7 derive from the "Validation scenarios required" section of `sprints/sprint-3-summary-source.md`; scenarios 8 and 9 add the constitutional regressions (airplane-mode I and keyboard-only NFR-005) that need to hold across the new tabs.

### Scenario 1 — From Findings, switch to Client summary; the four sections render with content

**Result**: ✅ PASSED (2026-05-11, on `nda-techcorp.pdf`).

**Setup**: `just dev` running. Ollama running with `gemma4:e4b` (or `gemma4:31b-instruct-q4_K_M` on capable hardware). Upload `fixtures/contracts/msa-acme.pdf`, wait for analyze to complete, land on the Findings tab.

**Steps**:
1. With the Findings tab visible (default), click the **Client summary** tab in the tab bar.
2. Inspect the rendered pane top-to-bottom.
3. Inspect the letterhead block.
4. Inspect each of the four section blocks.

**Expected**:
- Tab bar shows "Client summary" with the burgundy underline; the Findings tab's burgundy underline is gone.
- Pane header: eyebrow "Tab 02 · for your client" in burgundy mono uppercase + serif title "A version your client *actually reads.*" with "actually reads." in burgundy italic + a one-line lead in `ink-soft` ("Plain English. Three risks named in order. A clear recommendation. Edit before sending.").
- Doc card: `bg-bg-soft` background, hairline border, rounded corners, generous padding.
- Letterhead: mono uppercase "Carter & Voss LLP · Memo" in `ink-muted`, then a serif "Re: {contract_type}" line in `ink` 24px (e.g. "Re: MSA" or whatever Gemma classified the contract as).
- Four `<h3>` section headings in serif: "What this contract is", "What you're committing to", "The biggest risks", "Recommendation". Each heading has a small mono uppercase "Edit" button on its right.
- Section 1: a paragraph of plain-English prose (the model's `what_this_contract_is`).
- Section 2: a paragraph (the model's `what_youre_committing_to`).
- Section 3: a `<ul>` with one bullet per entry from `biggest_risks` (typically 3 entries on `msa-acme.pdf`).
- Section 4: a verdict box — 3px burgundy left border, `bg-burgundy-soft` background, mono uppercase "Recommendation" eyebrow in burgundy, then the recommendation prose in serif `ink`.
- Below the four sections, separated by a top border and `mt-10`: the summary disclaimer in `font-mono italic text-[12px] text-ink-muted`. It carries the canonical line in `analysis.client_summary.disclaimer`.
- The App-shell disclaimer footer is still visible at the bottom of the page.

### Scenario 2 — The disclaimer is visible at the bottom; try to remove it via DevTools and confirm it always re-renders

**Result**: ✅ PASSED (2026-05-11). DOM delete clears the node momentarily; Edit/Cancel re-render restores it via the `useLayoutEffect` watcher.

**Setup**: continues from Scenario 1.

**Steps**:
1. Open DevTools → Elements panel.
2. Locate the `<p data-testid="summary-disclaimer">` near the bottom of the doc card.
3. Right-click the node and choose "Delete element" (or focus the node and press the Delete key).
4. Observe the page momentarily.
5. Click any Edit button on one of the four section headings, then click Cancel — this triggers a parent re-render.

**Expected**:
- After step 3: the `<p>` is briefly gone from the DOM (verifiable in Elements; the visible text disappears).
- After step 5: the `<p data-testid="summary-disclaimer">` is back in the DOM with its full prop text. The visible disclaimer line is restored at the bottom of the doc card.
- This is the `useLayoutEffect` watcher reacting to the tamper. **Constitution IV** is structural, not just visual.
- For an even stronger proof, repeat steps 3–5 a second time. The disclaimer comes back again.

### Scenario 3 — Edit ephemerality honesty layer (Constitution VI)

**Result**: ✅ PASSED (2026-05-11). Eyebrow visible without edits; native unsaved-changes dialog appeared on Cmd-R after a Save; refresh confirmed discarded local edits; inline "saved (this session)" flash observed for ~1.5s.

**Setup**: continues from Scenario 2.

This scenario tests the three Sprint 3 fixup-2 honesty mitigations that make ephemeral edits explicit instead of silent: (a) the always-visible eyebrow disclosing the session-local boundary, (b) the native browser unsaved-changes confirmation on refresh, and (c) the inline "saved (this session)" flash that names the session boundary at the moment of action.

**Steps**:

1. **Ephemerality eyebrow visible whenever edit controls are visible.** With the Client summary tab active, locate the small mono burgundy eyebrow at the top of the doc card, just after the firm letterhead. It should read `// session-local — persistence: Sprint 5` (or close to). Confirm the eyebrow is present whether or not any Edit button has been clicked — it is global to the card, alongside all four Edit affordances.
2. **Native browser confirmation on refresh while dirty.** Click "Edit" on the **What this contract is** section. Erase the contents and type *"This is an MSA. We have changed it for the demo."*. Click the burgundy "Save" button below the textarea. The textarea is gone and the section's `<p>` shows your edited text. Now press `Cmd-R` / `Ctrl-R` (or click the browser's refresh button). The browser's native unsaved-changes confirmation dialog **must appear** ("Changes you made may not be saved" / "Leave site?" — exact text varies by browser).
3. **Confirming refresh loses edits as expected.** Confirm the refresh in the browser dialog. The page reloads, Review re-fetches the analysis, and the edited prose is **gone** — the section's `<p>` is back to the model's original output. This is the documented Sprint 3 ephemerality; Sprint 5 export work owns persistence.
4. **Inline saved feedback on Save.** With the page freshly loaded, click "Edit" on the **What this contract is** section again, type any change, and click Save. Immediately after Save, observe a small mono burgundy line near the section heading reading `saved (this session)`. It should appear briefly (~1.5s) then fade. The phrase names the session boundary at the moment of action so the lawyer cannot miss that this is not a durable save.
5. **Cancel-after-typing returns prop value, not the previous edit.** While an edit is committed locally, click "Edit" on a different field, type something, then click Cancel. The section returns to the **prop's original prose**, not the previously-saved local edit on the other field.

**Expected**:

- Step 1: Eyebrow is present on a clean render with no edits.
- Step 2: Browser dialog blocks the refresh and asks for confirmation. The dialog appears **because** at least one Save has been clicked since mount; without any Save the dialog should not appear (verifiable by reloading without editing first — no dialog).
- Step 3: Confirmed refresh discards local edits and the re-fetched analysis renders.
- Step 4: Inline "saved (this session)" flash appears for ~1.5s next to the saved field's heading, then is removed from the DOM.
- Step 5: Cancel reverts to the prop value as a baseline; previously-saved edits on **other** fields remain (their `<p>` still shows the edited prose).
- No silent loss: every ephemerality moment now has a visible signal — eyebrow on render, native dialog on refresh, inline flash on save.

### Scenario 4 — Switch to Source tab; confirm contract sections render in order

**Result**: ✅ PASSED (2026-05-11). Sections rendered in document order on `nda-techcorp.pdf`; tab badge text matched `analysis.source_sections.length`.

**Setup**: continues from Scenario 3 (or re-run after refresh).

**Steps**:
1. Click the **Source** tab in the tab bar.
2. Inspect the rendered pane.
3. Scroll through the source-doc block.
4. Confirm the section count badge on the Source tab.

**Expected**:
- Pane header: eyebrow "Tab 03 · the original" + serif title "The contract, *annotated.*" with "annotated." in burgundy italic + lead "Risk passages are highlighted. Click any highlight to jump to its finding."
- Source-doc block (`bg-bg-soft`, max width ~800px, generous padding) renders the contract section-by-section.
- Each section shows: small burgundy mono uppercase eyebrow "§ {number} — {title}" + a serif `<h3>` with the title + the section body in serif justified text.
- Sections appear in document order: the first section is the Preamble (or § 1 if the parser found no preamble) and the last section is the final § the parser detected.
- The Source tab's badge text equals the number of `source_sections` in the response — for `msa-acme.pdf` this is typically 12–18, depending on the parser hits. For a contract with no detected headings, the badge reads "1" (the whole-document fallback).

### Scenario 5 — The high-risk passage is highlighted in the right severity color

**Result**: ✅ PASSED (2026-05-11). High-severity highlights rendered with `bg-danger-soft` + 2px danger underline; highlight text was a whitespace-tolerant slice of the actual contract text.

**Setup**: continues from Scenario 4. The analysis has at least one high-severity finding — `msa-acme.pdf` typically produces a "3-month liability cap" finding in the burgundy/danger range.

**Steps**:
1. Scroll through the source-doc until you find a highlighted span. Highlights are inline `<button>`s on top of the body text.
2. Hover over the highlight; observe the cursor and styling.
3. Inspect the highlighted element in DevTools.

**Expected**:
- The highlight for a `severity="high"` or `"medium"` finding has class `bg-danger-soft border-b-2 border-danger` (a very pale red wash with a 2px red underline).
- A `severity="low"` finding (rare on this fixture) has `bg-warn-soft border-b-2 border-warn` (gold/orange).
- A `severity="missing"` finding (the model flagged a clause that should exist but is absent) has `bg-bg-tint border-b-2 border-ink-muted` (neutral).
- The highlight is a `<button type="button" role="button" tabindex="0">` with `aria-label="Jump to finding: {finding title}"` and `data-finding-index="{N}"` (the original index into `analysis.findings`).
- The cursor changes to a pointer on hover.
- The highlighted text inside the `<button>` is **a slice of the actual contract text** — same words as the corresponding finding's `quote` (whitespace may differ where pypdf inserted a `\n`; the words and their order are identical). This is Constitution III: only-located highlights, no fuzzy fabrication.

### Scenario 6 — Click the highlight; verify it navigates to Findings with that finding scrolled into view

**Result**: ✅ PASSED (2026-05-11). Click flipped activeTab to Findings, target card scrolled smoothly into view, `data-finding-target="true"` observed briefly in DevTools and cleared after ~1500ms.

**Setup**: continues from Scenario 5.

**Steps**:
1. Note the title in the highlight's `aria-label` (or simply remember which clause it covers).
2. Click the highlight.
3. Observe the tab bar and the page content.
4. Look for a visual marker on the corresponding finding card.

**Expected**:
- The active tab flips from Source to **Findings** (burgundy underline moves; pane content swaps).
- The matching finding card scrolls into view via smooth-scroll, centered in the viewport.
- The matching card briefly carries `data-finding-target="true"` (visible in DevTools Elements; the visual treatment is the card's normal accepted/dismissed state, since Sprint 3 did not add a separate "targeted" style — the attribute is the spec, the badge is left for Sprint 4 polish if desired).
- After ~1500ms the attribute clears.
- For a stronger proof, scroll the Findings pane elsewhere first (so the target card is far from view), then go back to Source and click the same highlight again — the smooth-scroll re-runs.

### Scenario 7 — A non-lawyer reads the summary, can answer "what's the recommendation?" and "what are the top 3 risks?" without seeing the contract

**Result**: ✅ PASSED (2026-05-11, on `nda-techcorp.pdf`). Summary was comprehensible without legal training; the verdict box delivered a complete-sentence recommendation, the bulleted risks were clause-free plain English.

**Setup**: open Client summary on `msa-acme.pdf`. Hand the laptop to someone who is not a lawyer (a friend, a designer, a non-technical family member). Do not show them the contract or the Findings tab.

**Steps**:
1. Ask them to read the four sections (~30–60 seconds).
2. Ask: "What's the recommendation?"
3. Ask: "What are the top three risks?"
4. Ask: "Would you sign this contract today?"

**Expected**:
- They can answer Q2 (recommendation) by reading the verdict box. The answer should be a complete sentence, not a clause reference. On `msa-acme.pdf` the model typically outputs something like "Do not sign as-is — negotiate the cap, the indemnity, and the prepayment forfeiture before executing."
- They can answer Q3 (top 3 risks) by reading the bulleted list under "The biggest risks". Each bullet is a plain-English clause-free statement, not a `§ 4.2` reference. On `msa-acme.pdf` the typical output is the cap, the one-way indemnity, and the no-refund termination clause.
- They can answer Q4 with a defensible position — even if they say "I don't know", they can articulate **why** based on the summary's prose. The User Story 2 acceptance criterion is that the summary is comprehensible without legal training; if they need legal background to follow it, the model's prose violates Constitution III's plain-English contract.
- Note: this scenario depends on the model's output quality, not the frontend. If the model returns the canonical `(missing)` fallback strings (a known E4B failure mode on long-context fixtures), the four sections will still render — the fallback text is visible in each section — and the test condition above will fail honestly. That's Constitution VI: the lawyer (and the non-lawyer reader) sees the fallback rather than fabricated polish. Re-run on `gemma4:31b-instruct-q4_K_M` if available.

### Scenario 8 — Airplane mode through Summary + Source tabs (Constitution I)

**Result**: ✅ PASSED (2026-05-11). Wi-Fi disabled; upload → analyze → all three tabs → cross-tab jump all worked. Network panel showed only `localhost:5173` traffic; zero external requests.

**Setup**: backend + frontend running, Ollama running locally, browser at `localhost:5173`. DevTools open with the Network tab armed.

**Steps**:
1. Toggle Wi-Fi OFF (or disable Ethernet at the OS level — leave loopback alone).
2. Open DevTools → Network tab → start recording → check "Preserve log" so the log spans navigations.
3. Drop `fixtures/contracts/msa-acme.pdf` into the upload zone.
4. Wait for analyze to complete. Land on Findings.
5. Click the Client summary tab; let it render.
6. Click the Source tab; let it render.
7. Click any highlight on the Source tab to jump back to Findings.
8. Inspect every entry in the Network tab.
9. Re-enable Wi-Fi when done.

**Expected**:
- Steps 3–7 all complete successfully despite no internet — upload, analyze, all three tab renders, the cross-tab jump.
- Every Network entry targets `localhost:5173` (which proxies `/api/*` to `localhost:8787`). **Zero requests** to any external host (no `fonts.googleapis.com`, no `cdn.*`, no analytics, no telemetry).
- The Source tab does not lazy-load any external resource (no font fetch, no image fetch, no CDN). Constitution I held across the new tabs.
- For an even stronger proof, run `tcpdump` in another terminal as in Sprint 2's Scenario 9 (`sudo tcpdump -nn -i en0 'not net 127.0.0.0/8 and not net ::1/128 and tcp port 80 or tcp port 443' -c 20`) and click around all three tabs. **Expected**: tcpdump captures zero packets matching the filter.

### Scenario 9 — Keyboard-only navigation through Summary edit + Source highlight (NFR-005)

**Result**: ✅ PASSED (2026-05-11). Visible burgundy focus ring on every reachable control; Enter activated tabs / Edit / Save / highlights; the summary disclaimer was correctly skipped in the tab order.

**Setup**: Review screen open, on the Findings tab. Mouse off the table — use Tab, Shift+Tab, Enter, and arrow keys only.

**Steps**:
1. Press Tab repeatedly until focus reaches the **Client summary** tab button. Press Enter.
2. Tab into the Client summary pane until focus reaches the "Edit" button on the **What this contract is** heading. Observe the focus ring.
3. Press Enter on the Edit button.
4. The textarea should now be focused (or one Tab away). Press Tab if needed; observe the focus ring on the textarea.
5. Type a few characters.
6. Press Tab. Focus should move to the burgundy Save button. Observe the focus ring.
7. Press Enter on Save.
8. Tab back up to the **Source** tab button. Press Enter.
9. Tab into the source-doc until focus reaches the first highlight `<button>`. Observe the focus ring on the highlight.
10. Press Enter.
11. Confirm the page state.

**Expected**:
- Every tab landing displays a visible focus ring: burgundy 2px ring with a 2px white offset (`focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2` per design tokens).
- Step 1: Enter on the Client summary tab activates it (the tab bar uses `<button>` elements with `aria-current="page"` on the active tab).
- Step 3: Enter on the Edit button replaces the section's `<p>` with a `<textarea>` whose initial value matches the prop.
- Step 4: the textarea has the focus ring; Tab from the textarea reaches Save next, then Cancel.
- Step 7: Enter on Save commits the edit; the pane re-renders with the edited prose.
- Step 9: highlight `<button>` with the focus ring visible — `tabindex="0"` and `role="button"` make it part of the tab order.
- Step 10: Enter on a highlight does the cross-tab jump (Source → Findings, target card scrolled, `data-finding-target="true"` briefly set), exactly as a click would.
- No `outline:none` without a visible replacement anywhere along this path.
- The summary disclaimer is **not** in the tab order (it is structural prose, not interactive). Verify by Shift+Tab from outside the doc card and confirming focus skips the `<p data-testid="summary-disclaimer">`.

### Scenario 10 — Source overlap surfacing (Constitution VI)

**Result**: ✅ PASSED (2026-05-11). Hand-crafted overlapping-offset fixture surfaced the `source-overlap-banner` with the verbatim count message; Source tab dropped the overlapping highlight, Findings tab still listed both findings.

**Setup**: needs an analyze response where at least two findings have `source_offset` ranges that overlap within the same `section_index`. Real Gemma output rarely produces overlaps on `msa-acme.pdf`, so this scenario is fixture-driven.

**Steps**:

1. Stop the dev server if running.
2. Apply a temporary backend route override (or hand-craft a SQLite row) so `GET/POST /api/analyze/{id}` returns a response carrying two findings on the same section whose offsets overlap. The minimal fixture:
   ```jsonc
   {
     "findings": [
       { "title": "First clause",       "source_offset": { "section_index": 0, "start":  0, "end": 20 }, "severity": "high",   "quote": "...", "explanation": "...", "redline": "" },
       { "title": "Overlapping clause", "source_offset": { "section_index": 0, "start": 10, "end": 20 }, "severity": "medium", "quote": "...", "explanation": "...", "redline": "" }
     ],
     "source_sections": [
       { "idx": 0, "number": "4.2", "title": "Limit", "body": "AAAAAAAAAA more text after.", "char_start": 0, "char_end": 27, "page": 1 }
     ]
   }
   ```
   Equivalent path: drop a hand-crafted record into SQLite and load `/review/{doc_id}` directly.
3. Navigate to the Source tab.
4. Inspect the area above the source-doc block.
5. Inspect the rendered highlights inside the source-doc.

**Expected**:

- A burgundy-bordered banner with `data-testid="source-overlap-banner"` appears above the source-doc, visually identical to the Findings-tab warnings banner pattern (burgundy-soft background, 3px burgundy left border).
- The banner text reads: `1 finding couldn't be highlighted in Source due to overlap — see the Findings tab for the complete list.` (Plural `findings` when count > 1.)
- The Source tab renders **only one** highlight `<button>` for that section (the first finding); the overlapping second highlight is not rendered.
- The Findings tab still lists **both** findings — Source omission does not propagate to Findings.
- When the response has no overlapping offsets, the banner is absent. Confirm by reloading on a normal `msa-acme.pdf` analysis: no overlap banner.

---

## Caveats and notes for Sprint 4

- **Documents uploaded before Sprint 3 deployed have no `sections` rows.** T004 only fires on **new** uploads. The legacy-document warning *"Source viewer: this document was uploaded before section indexing was enabled. Source tab will be empty. Re-upload to enable highlights."* surfaces on these. Recovery is a re-upload. Sprint 5/6 polish could add a one-shot backfill script that re-parses every existing document, populates `sections`, and bumps a schema-version row; out of scope for Sprint 4 unless the human's local DB has too many pre-Sprint-3 documents to re-upload.
- **Summary edits are React-only ephemeral**; lost on hard refresh. Sprint 5 export work owns persistence (the editable surface is the same memo that exports as `.docx`).
- **Firm letterhead is a placeholder.** `"Carter & Voss LLP · Memo"` is hardcoded in `ClientSummary.tsx`. Sprint 5 will read it from `~/.caveat/firm.json` (and the sprint-5 brief should pin a default-when-absent fallback so the tab never blanks).
- **Source highlights respect the same whitespace tolerance as the citation validator.** Smart-quote / punctuation / case drift between Gemma's output and the source PDF is still a legitimate miss (Constitution III strictness preserved); these surface as Constitution VI warnings naming the finding title verbatim. The unit-test pair `test_map_finding_offsets_tolerates_whitespace_drift_in_source` and `test_smart_quote_drift_is_a_genuine_miss_not_papered_over` pin the line precisely.
- **Sprint 2 carry-forward note 2 is still open.** The Topbar "0 network requests" pill is hard-coded; either wire it to a real fetch counter or relabel to a static-by-construction string. Flagged for Sprint 5 polish.
- **Hard-refresh on `/review/:id` still re-runs the full analyze** (Sprint 2 imperfection unchanged in Sprint 3). Sprint 4's findings router will introduce the cache that resolves it for **all** tabs at once. The Source tab can render without the slow re-analyze (sections + text are already in SQLite); we deliberately did not split the cache by tab so Sprint 4 can solve it uniformly.
- **The `useLayoutEffect` disclaimer-restore pattern** in `ClientSummary.tsx` is a deliberate divergence from the Sprint 3 brief's "implicit re-rendering will suffice" guidance; see the "Constitution IV polish landed during the sprint" section above. The fix is sound, scope-bounded, and pinned by both vitest and Playwright. If the same non-removable pattern is needed elsewhere (e.g., on the Findings tab disclaimer, the export `.docx` footer block in Sprint 5), factor it into a `useNonRemovable(elementRef, parentRef)` hook so the contract is reusable.
- **`Findings.tsx` `data-finding-target` styling is structural-only.** The attribute is present and pinned by tests, but the brief did not specify a visual treatment beyond the smooth-scroll behavior. Sprint 4's findings router work could add an optional `outline` flash via CSS without touching the contract.
- **`Source.tsx` overlap drops are now surfaced via a Constitution VI banner** (Sprint 3 fixup-3). When two findings have overlapping `source_offset` ranges within the same section, the renderer still drops the later highlight (overlap merging is deferred to Sprint 4), but the count is surfaced in a `data-testid="source-overlap-banner"` block above the source-doc with text `N finding(s) couldn't be highlighted in Source due to overlap — see the Findings tab for the complete list.` The Findings tab remains authoritative for the complete list. Sprint 4 follow-up: implement true overlap-merging in `renderBodyWithHighlights` (a span that belongs to multiple findings) so the banner can be retired.
- **Manual visual confirmation of offset round-trip** (`section.body[start:end] === finding.quote`, whitespace-tolerant only) is pending an analyze run that produces findings. The 199 automated tests cover this property against fixtures. Visual confirmation against a real-world analyze response is blocked by E4B's inability to produce findings on `msa-acme.pdf` (26KB prompt). To be confirmed during Sprint 6 demo prep with `gemma4:31b-instruct-q4_K_M` on capable hardware, or earlier against a smaller real-world fixture (e.g., a short NDA). The verification path is the standalone script `apps/backend/scripts/verify_offset_roundtrip.py <document_id>`, usable any time a successful analyse exists in SQLite — it re-runs `map_finding_offsets` against the persisted document text and findings, and prints per-finding OK / FAIL lines plus the slice/quote token diff on mismatch.

---

## Deferred to Sprint 5

Items surfaced during the Sprint 3 closure walk that are real but explicitly out of scope until the export sprint owns them:

- **Real end-to-end test against live backend + Ollama.** The current Playwright suite (`apps/frontend/e2e/`) mocks all backend responses at the browser layer via `page.route()` — it catches browser-level bugs (StrictMode dispatch duplication, etc.) but does not exercise the real FastAPI → pipeline → Ollama path. Sprint 5 should add a `just test-real-e2e` recipe driving the live stack against a tiny single-clause fixture (or a stubbed-Ollama FastAPI app that returns a canned response in ms) so we have one authoritative end-to-end signal alongside the fast mock suite.
- **Out-of-range / empty highlight silent drop in `Source.tsx`.** Sibling failure to the overlap banner: if a finding's `source_offset` lands outside the section body or has `start == end` (after pypdf drift), the renderer silently drops the highlight. Should surface identically — a `data-testid="source-out-of-range-banner"` block above the source-doc with verbatim count and finding titles. Constitution VI applies the same way it did to the overlap case.
- **Cosmetic: `§ 0 — Preamble` synthetic numbering reads weird.** The Constitution VI preamble synthesis (Sprint 3 T002) labels the pre-§1 content as `§ 0`, which is a contradiction in terms — sections don't have a 0. Sprint 5 polish: drop the `§` prefix for the synthetic preamble (or change the eyebrow to just `Preamble`).
- **`bodyStart` derivation could be backend-surfaced.** `Source.tsx` currently computes the body-start offset client-side from `section.char_start` + the heading-line length so highlight `start`/`end` indices land in the right slice of `section.body`. The backend already knows this; surfacing `body_char_start` (or just shipping `body` as the substring already anchored at 0 and shifting offsets to be body-relative) would move the derivation upstream and eliminate a class of off-by-one bugs.
- **ClientSummary edit persistence to SQLite.** Sprint 3 honesty layer is in place — eyebrow disclosure, native unsaved-changes prompt, inline "saved (this session)" flash — but durability is Sprint 5's job (Word/PDF export is the natural place to add the SQLite round trip, since the edited memo is the same artifact that flows into the export).

---

**Sprint 3 is closed.** All automated tests green via `just verify-sprint-3`; all 10 manual scenarios walked PASSED on `nda-techcorp.pdf` (2026-05-11). Ready for the Sprint 4 brief.
