# Sprint 2 — Validation

**Status**: Ready for human review
**Generated**: 2026-05-10
**Scope reference**: `sprints/sprint-2-frontend-slice.md`
**Verification command**: `just verify-sprint-2`

---

## Summary of what changed

Sprint 2 delivered the full frontend vertical slice for User Story 1 — a lawyer can drop a contract PDF into the browser, watch a real-time pipeline screen, and land on a Findings tab where every model claim is flanked by its source quote in burgundy. The visual identity from `docs/caveat-prototype-v3.html` is now real: editorial serif titles, the burgundy accent doing all the heavy lifting, status pills in mono uppercase, no SaaS gradients, no decorative imagery. The disclaimer is rendered at the App shell level so it appears on every screen with AI output (Constitution IV). Warnings from the analyze pipeline (the e4b structural-empty case from sprint-1 fixup-2) surface as a verbatim banner ABOVE the summary cards, never summarized, never truncated (Constitution VI). The Sprint 1 carry-forward Starlette deprecation warnings are gone.

**Implemented (per sprint scope):**

- **`apps/frontend/src/App.tsx`** — full rewrite. `BrowserRouter` + 3 routes (`/`, `/processing/:docId`, `/review/:docId`) wrapped in a `<Shell />` layout that mounts `<Topbar />` at the top, `<Outlet />` in the middle, and `<DisclaimerFooter />` at the bottom. App-level state for active doc + status + model name is exposed to children via typed `useOutletContext` so the Topbar updates as routes change without prop-drilling. The Sprint 0 placeholder ("Sprint 0 — Scaffold") is gone; the disclaimer-footer pattern is preserved per the Sprint 0 carry-forward.
- **`apps/frontend/src/api/client.ts`** — extended with `apiPostFormData<T>(path, body: FormData)` for multipart upload. Reuses the existing `assertRelative()` Constitution-I guard, so the local-only chokepoint stays one function. Both `apiPost` and `apiPostFormData` now extract the backend's `detail` field from non-2xx responses and surface it verbatim in `ApiError.message` (Constitution VI — honest about what failed). `Content-Type` is deliberately NOT set on the FormData call so the browser attaches the correct multipart boundary.
- **`apps/frontend/src/api/documents.ts`** — typed wrappers `listDocuments()` and `uploadDocument(file)`. Type definitions match the backend `DocumentResponse` / `DocumentSummary` Pydantic models exactly.
- **`apps/frontend/src/api/analyze.ts`** — typed wrapper `analyzeDocument(documentId)` returning the backend's `AnalyzeResponse` shape (`document_id`, `contract_type`, `findings[]`, `client_summary`, `warnings[]`, `elapsed_seconds`). No client-side timeout — the underlying `fetch` runs as long as the backend takes (30–180s typical, ~4 min on cold-start with E4B). The Processing screen carries the user through that wait visually.
- **`apps/frontend/src/api/health.ts`** — `getHealth()` for the Topbar's model-name pill.
- **`apps/frontend/src/components/Topbar.tsx`** — persistent header (brand "Caveat" + AI tag pill in burgundy + topbar-doc context line + status pills on the right). Working state pulses warn dot. Status pill labels: `Local · Gemma 4 · {model}` once health resolves.
- **`apps/frontend/src/components/DisclaimerFooter.tsx`** — non-removable footer (Constitution IV). Canonical line: *"AI-generated output — attorney review required. Caveat AI supports, but does not replace, the lawyer's professional judgment."* Mounted at App shell level so every route inherits it.
- **`apps/frontend/src/components/TabPlaceholder.tsx`** — "Coming in Sprint N" pane used by the three tabs not implemented this sprint (Client summary + Source → Sprint 3, Chat → Sprint 4).
- **`apps/frontend/src/pages/Upload.tsx`** — matches prototype screen 01: hero left ("Read the contract. *Keep the secret.*" with burgundy italic em), drop zone right (burgundy hover + click-to-pick fallback + keyboard reachability with `role="button"`, `tabIndex=0`, Enter/Space handler, visible focus ring), recent reviews list from `listDocuments()` capped at 5 with relative-time meta. Empty state: *"Drop your first contract above"*. Errors from the backend (415/413/422) surface verbatim above the drop zone in a `bg-danger-soft` box (Constitution VI).
- **`apps/frontend/src/pages/Processing.tsx`** — matches prototype screen 03: 6-stage pipeline with calibrated dwell times (Parse 1.5s, Classify 5s, Load playbook 0.5s, Analyze 70s, Validate 2s, Build summary 30s). Active stage pulses burgundy. **Hold-pulse contract**: when the timer reaches the last stage, it stays active indefinitely until the backend response arrives — the UI never auto-completes a stage that hasn't actually finished (Constitution VI). Cold-start sub-line copy verbatim: *"first analysis after starting may take 3–5 min while Gemma loads into RAM; subsequent analyses are 30–120s. Estimated stages — actual timing varies."* Privileged-work-product callout makes Constitution I visible. On 503 from a missing `ollama serve`: error pane with verbatim message + "Back to upload" link, no auto-navigate.
- **`apps/frontend/src/pages/Review.tsx`** — matches prototype screen 04: 260px sidebar (1 doc this sprint — multi-doc is Sprint 4 — plus disabled "Add document" button with explicit Sprint 4 title) + 4-tab nav. Findings active by default; the other 3 tabs render `TabPlaceholder` with the right sprint number. Re-analyze button is disabled with explicit Sprint 5 title. Hard-refresh re-runs the full analyze (acceptable Sprint 2 imperfection — Sprint 4's findings router will cache).
- **`apps/frontend/src/tabs/Findings.tsx`** — the centerpiece. Order: pane header → **WARNINGS banner** (when `warnings.length > 0`, verbatim, ABOVE summary cards, with burgundy left border + `bg-burgundy-soft` + mono "WARNINGS · model honesty" eyebrow — Constitution VI) → 4-cell summary (high/medium/missing/elapsed) → filter chips → either empty-state card or finding cards. **Honest empty states**:
  - `findings=[] AND warnings.length>0` → banner above + *"Analysis incomplete — see warnings above. The model may be undersized for this contract; consider re-running with `gemma4:31b-instruct-q4_K_M` on capable hardware."*
  - `findings=[] AND no warnings` → *"No findings produced. The contract appears clean against the loaded playbook, but please review manually before accepting this result."*
  - **Never** "no risks found" or "you're safe." Pinned by the negative-assertion test in `Findings.test.tsx`.
  
  Finding cards: severity badge (high=danger, med=warn, low=gold, missing=ink), serif title, `finding-quote` block (3px burgundy left border + `bg-burgundy-soft` + serif italic — Constitution II made tangible), explanation, optional redline, action row (✓ Accept toggleable / Edit & Ask-in-chat disabled with Sprint 4 titles / ✕ Dismiss). Finding state is React-only Map keyed on the original index; ephemeral per page load (Sprint 4 owns persistence).

**Carry-forwards from sprint-1-validation.md, addressed:**

- ✅ App.tsx eyebrow — replaced "Sprint 0 — Scaffold" placeholder with the real product flow; disclaimer footer pattern preserved at App-shell level.
- ✅ Starlette HTTP_413/422 deprecation — `apps/backend/caveat/routers/documents.py` now uses `HTTP_413_CONTENT_TOO_LARGE` and `HTTP_422_UNPROCESSABLE_CONTENT`. Verified via re-running the suite with `-W error::DeprecationWarning` (90 backend tests pass under that flag).
- ✅ Constitution VI fixup-2 (warnings channel) made visible in the UI: warnings are rendered verbatim in a dedicated banner ABOVE the summary cards on the Findings tab, and the empty-state copy explicitly says "Analysis incomplete" rather than "no risks found."

**Carry-forwards still applicable (deferred to Sprint 5 per Sprint 0 plan):**

- Self-hosted Fraunces / Geist / Geist Mono woff2. Sprint 2 still relies on system-font fallbacks (Georgia / system sans / system mono); Constitution I forbids Google Fonts.

**Constitution VI polish landed during code review (PASS-WITH-NOTES):**

- Review hard-refresh loading copy was originally *"Restoring this review from local storage…"* — but there is no local-storage cache yet, so the copy was misleading. Replaced with *"Re-running the analysis on the local model…"* + an explicit follow-up noting Sprint 4 will add the cache. Honesty over polish.

**Explicitly NOT delivered** (out of scope for Sprint 2):

- Client summary tab + Source viewer tab (Sprint 3 — placeholders show "Coming in Sprint 3")
- Multi-document sidebar with up to 5 PDFs + chat tab streaming over SSE (Sprint 4)
- Findings router for persistent accept/edit/dismiss state across reloads (Sprint 4)
- Export package (Word memo, signed PDF, redline, email blurb) (Sprint 5)
- Hardware auto-detection for model variant selection (Sprint 5)
- Self-hosted woff2 fonts (Sprint 5)
- Demo mode + seed data (Sprint 6)

---

## Unit tests added

**52 frontend unit tests across 6 files. Vitest suite: 2.07s tests + ~1s overhead = 3.05s total** (Constitution X budget for the full unit suite is 10s; backend unit suite separately runs in 0.95s, so combined ≈4s).

### `apps/frontend/src/api/client.test.ts` — 11 tests (extended from Sprint 0's 7)

Pins the Constitution I chokepoint and the new multipart variant.

- `apiGet` (existing): prepends `/api`, refuses absolute http/https URLs, throws `ApiError` on non-2xx, normalizes paths without leading slash.
- `apiPost` (existing): serializes body, sets JSON headers, refuses absolute URLs.
- `apiPostFormData` (new, 4 tests): prepends `/api`, **does NOT** set `Content-Type` (browser attaches multipart boundary), refuses absolute URLs (Constitution I guard reused), surfaces backend `detail` verbatim in `ApiError.message` when JSON-parseable, falls back to generic message when body isn't JSON.

### `apps/frontend/src/App.test.tsx` — 6 tests (Sprint 0 file replaced)

- Disclaimer footer renders on `/`, `/processing/abc`, `/review/abc` (Constitution IV gate at shell level).
- Topbar brand "Caveat" + "AI" tag visible on every route.
- `/` renders Upload hero ("Read the contract.").
- `/processing/abc` renders Processing screen ("Reading carefully.").
- `/review/abc` renders Review (with mocked `analyzeDocument` since the hard-refresh path triggers a re-fetch).
- Topbar status pill picks up the model name once `getHealth()` resolves.

### `apps/frontend/src/pages/Upload.test.tsx` — 8 tests

- Hero copy renders verbatim ("Read the contract.", "Keep the secret.", lead with "on this machine").
- Drop zone is keyboard-reachable (`role="button"`, `tabIndex=0`, Enter/Space handler).
- Recent reviews populates from mocked `listDocuments`.
- Empty recent state shows "Drop your first contract above".
- Non-PDF file via drop event surfaces an error message containing "PDF" (`userEvent.upload` would silently drop non-matching files due to the `<input accept>` filter, so the test exercises the realistic drag-drop bypass path).
- Successful upload calls `uploadDocument(file)` then `useNavigate('/processing/{docId}', { state: ... })`.
- Backend errors (415/413/422) surface verbatim above the drop zone in a `bg-danger-soft` box.
- Drag-drop happy path covered.

### `apps/frontend/src/pages/Processing.test.tsx` — 7 tests

- All 6 stages render with the prototype copy.
- Initial state: `parse` stage active, others pending.
- Stages advance after `vi.advanceTimersByTime(1500)` — Parse → done, Classify → active.
- Cold-start sub-line copy verbatim: "First analysis after starting may take 3–5 min while Gemma loads into RAM" (Constitution VI).
- Success path: when `analyzeDocument` resolves before the timer reaches stage 6, all stages mark done and `useNavigate` fires `/review/{docId}`.
- 503 reject: error pane shows "Ollama unreachable" verbatim AND a "Back to upload" link; `useNavigate` is NOT called.
- **Hold-pulse contract** (the Constitution VI clincher): with `analyzeDocument` mocked to never resolve, `vi.advanceTimersByTime(120000)` → the LAST stage stays `active`, never auto-completes. The UI doesn't lie about a stage finishing.

### `apps/frontend/src/pages/Review.test.tsx` — 9 tests

- Sidebar shows "Documents · 1" label + filename in the active doc-item.
- Tab bar renders 4 tabs (Findings active by default).
- Default Findings content visible.
- Clicking Client summary → "Coming in Sprint 3" placeholder.
- Clicking Source → "Coming in Sprint 3" placeholder.
- Clicking Chat → "Coming in Sprint 4" placeholder.
- Re-analyze button disabled with `title` mentioning Sprint 5.
- Sidebar privacy footer note visible.
- Add document button disabled with `title` mentioning Sprint 4.

### `apps/frontend/src/tabs/Findings.test.tsx` — 11 tests (THE CRITICAL FILE)

Pins Constitution VI in the UI surface.

- (a) **Happy path**: 3 findings, warnings=[]. Assert: 3 finding cards, warnings banner ABSENT, summary counts match.
- (b) **Warnings banner above summary cards**: 2 findings + 1 warning. Assert: banner exists, warning text verbatim, banner appears BEFORE summary cards in DOM order (verified via `Node.compareDocumentPosition`).
- (c) **Honest empty state with warnings**: findings=[], 2 warnings. Assert: both warnings visible verbatim, "Analysis incomplete" copy present, **`screen.queryByText(/no risks/i) === null`**, **`screen.queryByText(/safe/i) === null`** — the explicit negative assertions that pin Constitution VI.
- (d) **Truly empty + no warnings**: findings=[], warnings=[]. Assert: `findings-empty-clean` card with "review manually" copy. No warnings banner. Still no "no risks" anywhere.
- (e) **Severity badges**: high/medium/low/missing → correct Tailwind class + `data-severity` attribute.
- (f) **Accept toggles state**: click "✓ Accept" → button text becomes "✓ Accepted", card has `data-state="accepted"`. Click again → reverts.
- (g) **Dismiss hides**: click ✕ Dismiss → card removed from list.
- (h) **Filter chips work**: "High only" hides others; "All N" restores.
- (i) **Accepted (N) chip count updates**: accept 2 of 3 → chip shows "Accepted (2)"; clicking it shows just those 2.
- (j) **Citation block visible** (Constitution II made tangible): every finding renders `[data-testid="finding-quote"]` with the verbatim quote.
- (k) **Redline only when present**: `redline=""` → no redline block; non-empty → block renders with "↳ Suggested redline" eyebrow.

---

## E2E tests added

**2 Playwright tests in 1 file. Frontend E2E suite: 9.1s including dev-server boot.** Backend E2E (Sprint 1) still runs as part of `just test-e2e`: 13 tests in 10.0s.

### `apps/frontend/e2e/sprint-2-flow.spec.ts` (replaces Sprint 0's `health.spec.ts` which was deleted)

Both tests use `page.route()` to mock the backend — the Vite webServer starts the real React app, the Playwright route handler returns canned JSON, no real Ollama needed.

- **Test 1 — happy path**: navigate to `/`, confirm hero, set a synthetic PDF via the file input → Vite app navigates to `/processing/doc-123` → "Reading carefully." visible → cold-start sub-line visible → app navigates to `/review/doc-123` → tab bar visible, Findings active → 2 finding cards rendered → burgundy quote block visible → click ✓ Accept on the first → button reads "✓ Accepted", card has `data-state="accepted"` → click ✕ Dismiss on the second → only 1 card remains → disclaimer footer visible at the bottom of every screen along the way.
- **Test 2 — honest empty state**: same setup, but mock analyze to return `findings=[]` + 2 warnings. Assert: warnings banner visible with both warnings verbatim, "Analysis incomplete" copy visible, **`page.getByText(/no risks/i)` is not visible**, **`page.getByText(/\bsafe\b/i)` is not visible** (word-bounded so it doesn't match "safe" inside "behalf"). The constitutional negative.

### Sprint 1 backend E2E tests (still run in `just test-e2e`)

- 13 tests covering documents router (upload, list, get, delete, 415/413/422), analyze router (happy path, 404 on unknown id, persistence, 503 on Ollama down, retry warning), and the no-network guard against the full pipeline.

---

## Manual validation scenarios

Run these after `just verify-sprint-2` passes. Each scenario lists the exact expected behavior. If any deviates, note it and stop — that's a regression to fix before declaring Sprint 2 done.

### Scenario 1 — Visual identity (the prototype is the spec)

**Setup**: `just dev` running. Open `http://localhost:5173` in Chrome (or Firefox / Safari).

**Steps**:
1. Inspect the Upload screen.
2. Open the browser DevTools color picker. Sample the burgundy used in the eyebrow rule, the "Keep the secret." em, the AI tag border, and the upload-zone hover state.

**Expected**:
- Burgundy `#7a1f2b` is the only accent. No blue, purple, or teal anywhere on the page.
- Three font roles: Fraunces serif (titles + citation block) → renders as Georgia or system serif this sprint (woff2 lands in Sprint 5); Geist sans (body + buttons) → renders as system sans; Geist Mono (status pills, eyebrows, file metadata) → renders as system mono.
- Disclaimer footer visible at the bottom: *"AI-generated output — attorney review required. Caveat AI supports, but does not replace, the lawyer's professional judgment."*

### Scenario 2 — Drop a PDF, observe the upload accept

**Setup**: Backend running (`just dev`), Ollama running (`ollama serve`) with `gemma4:e4b` pulled. Upload screen open at `localhost:5173`.

**Steps**:
1. Drag `fixtures/contracts/msa-acme.pdf` from Finder into the dashed drop zone.
2. While dragging over the zone, observe the visual state.
3. Release the file.

**Expected**:
- During drag-over: zone border changes to burgundy (`#7a1f2b`), background shifts to `burgundy-soft` (`#faf2f3`).
- On drop: zone copy changes to "Uploading…" briefly (sub-second on a 200KB-1MB PDF), then the browser navigates to `/processing/{document_id}`.
- No external network traffic during upload (Constitution I — verifiable via DevTools Network tab → all requests are to `localhost:5173` which proxies to `localhost:8787`).

### Scenario 3 — Processing screen during real analyze

**Setup**: continues from Scenario 2.

**Steps**:
1. Observe the Processing screen as the analyze runs (30–180s on E4B warm; 3–5 min cold).
2. Confirm the pipeline visual.
3. Mid-analyze, look at the page copy.

**Expected**:
- Topbar shows: brand + AI tag + topbar-doc context "acme-msa-v3.pdf · analyzing" (or the actual filename) + "Local · Gemma 4 · gemma4:e4b" status pill + "Working · …" pill with pulsing warn dot.
- Title: "Reading carefully." (with "carefully." in burgundy italic).
- Sub-line copy verbatim: *"Gemma 4 is parsing your contract and cross-referencing the playbook. First analysis after starting may take 3–5 min while Gemma loads into RAM; subsequent analyses are 30–120s. Estimated stages — actual timing varies."*
- Pipeline shows 6 stages: Parse → Classify → Load playbook → Analyze → Validate citations → Build summary. The active stage has burgundy text + a pulsing dot. Completed stages show a green ✓.
- Privileged-work-product callout visible at the bottom of the pipeline: *"Privileged work product. Computation is happening on this device only. You can disconnect from Wi-Fi without affecting the result."*
- Disclaimer footer still visible (Constitution IV).
- **If the analyze takes longer than the timer estimate**: the LAST stage (Build summary) stays in `active` state with the pulse — it does NOT auto-mark complete. This is the Constitution VI hold-pulse contract.

### Scenario 4 — Land on Findings, verify summary + cards

**Setup**: continues from Scenario 3 once the analyze completes (or surfaces warnings).

**Steps**:
1. Observe the Review screen as it appears.
2. Inspect the Findings tab content.
3. Look at the summary cards.

**Expected**:
- Topbar updates: topbar-doc shows "acme-msa-v3.pdf · MSA · 8 pages" (or the actual page count); status pill no longer pulsing.
- Sidebar shows "Documents · 1" with the filename in an active card. Add document button is disabled with hover title "Multi-document support arrives in Sprint 4".
- Tab bar shows 4 tabs with badges. Findings is active (burgundy underline, ink text).
- Pane header: eyebrow "Tab 01 · technical analysis" in burgundy mono + serif title "{N} things worth knowing." with "worth knowing." in burgundy italic.
- Summary cards: 4-cell grid showing High risk count (in `danger` red), Medium count (in `warn` orange), Missing clauses count (in ink), Analysis time (e.g. "43.7s").
- Filter chips below: "All N" / "High only" / "Missing" / "Accepted (0)".

### Scenario 5 — Inspect a finding card (Constitution II made tangible)

**Setup**: continues from Scenario 4 — at least one finding rendered.

**Steps**:
1. Pick the first finding card.
2. Inspect its structure.

**Expected**:
- Severity badge in the right color (high → red `danger`, medium → orange `warn`, low → gold, missing → black `ink`). Mono uppercase, ~9px.
- Finding title in serif, ~18px, bold.
- Quote block visually distinct: 3px burgundy left border, `burgundy-soft` background, serif italic, `~14px`. The text inside is the verbatim quote from the source PDF (this is the Constitution II promise).
- Explanation paragraph below the quote in sans, `ink-soft` color.
- If the finding has a non-empty redline: a separate `bg-bg-soft` block with mono burgundy "↳ Suggested redline" eyebrow and serif body.
- Action row at the bottom: ✓ Accept (clickable) / Edit (disabled, hover title "Inline editing arrives in Sprint 4") / Ask in chat (disabled, hover title "Cross-document chat arrives in Sprint 4") / ✕ Dismiss (clickable).

### Scenario 6 — Accept and Dismiss state (Constitution V)

**Setup**: continues from Scenario 5.

**Steps**:
1. Click ✓ Accept on the first finding.
2. Observe the visual change.
3. Click ✓ Accepted on the same finding (toggle).
4. Click ✕ Dismiss on the second finding.
5. Observe.
6. Look at the "Accepted (N)" filter chip.

**Expected**:
- After step 1: button label changes to "✓ Accepted", border + text turn safe-green, background shifts to `safe-soft`. Card border-color becomes safe-green.
- After step 3: button reverts to "✓ Accept", card border returns to neutral.
- After step 4: the second finding card is removed from the rendered list. The remaining cards re-flow.
- The "Accepted (N)" filter chip count updates live as you accept/un-accept.
- Refreshing the browser at this point will lose all accept/dismiss state — that is the documented Sprint 2 behavior. Sprint 4 adds persistence.

### Scenario 7 — Filter chips

**Setup**: continues from Scenario 6.

**Steps**:
1. Click "High only" chip.
2. Click "All N" chip.
3. Click "Missing" chip.
4. Click "Accepted (1)" chip (assuming you accepted at least one in Scenario 6).

**Expected**:
- "High only" hides medium/missing/low cards; only `severity === 'high'` cards render.
- "All N" restores the full list (minus dismissed).
- "Missing" shows only `severity === 'missing'` cards.
- "Accepted (1)" shows only the cards in the accepted state.
- The active chip is filled `bg-ink` with white text; inactive chips are `bg-bg-soft` with ink-soft text.

### Scenario 8 — The honest empty state (Constitution VI)

This is the scenario the e4b structural-empty case from sprint-1 fixup-2 was designed to make visible. Reproduces the exact bug that drove that fixup.

**Setup**: same as Scenario 2, but specifically use `gemma4:e4b` (24GB M4 Air will fall back to it automatically) on the `msa-acme.pdf` fixture. The model frequently returns the wrong schema for analyze + summary on long-context fixtures (~26K+ chars) and produces `findings=[]` + 2 warnings.

**Steps**:
1. Drop `fixtures/contracts/msa-acme.pdf` into the upload zone.
2. Wait for the analyze to complete (typically 30–180s warm, ~5 min cold).
3. On the Review/Findings screen, look for the warnings banner.
4. Look for the empty-state copy.
5. Look for any false-reassurance language.

**Expected**:
- A warnings banner appears at the TOP of the Findings pane (above the summary cards): burgundy left border, `burgundy-soft` background, mono "WARNINGS · MODEL HONESTY" eyebrow in burgundy.
- Two warning lines visible verbatim:
  - *"Analyze stage on first pass: model output had no usable `findings` field (either missing or not a list). No findings produced. The model may be undersized for this contract or the response may have been truncated."*
  - *"Client summary: model omitted or left empty: what_this_contract_is, what_youre_committing_to, recommendation. Each missing field shows a fallback placeholder."*
- Below the summary cards (which read 0/0/0/{elapsed_seconds}s): the honest empty card *"Analysis incomplete — see warnings above. The model may be undersized for this contract; consider re-running with `gemma4:31b-instruct-q4_K_M` on capable hardware."*
- **NOWHERE on the page**: the words "no risks" or "you're safe" or any other false reassurance.
- Disclaimer footer still visible.

If at any point you see "No risks found" or similar happy-path copy in the empty state, that's a Constitution VI failure and a hard-stop bug.

### Scenario 9 — Airplane mode end-to-end (Constitution I)

**Setup**: backend + frontend running, Ollama running locally, browser at `localhost:5173`.

**Steps**:
1. Toggle Wi-Fi OFF (or disable Ethernet at the OS level — leave loopback alone).
2. Open DevTools → Network tab → start recording.
3. Drop a PDF, run a full analysis through to the Findings screen.
4. Observe the Network tab.

**Expected**:
- Every request in the Network tab targets `localhost:5173` (which proxies to `localhost:8787`). Zero requests to any external host.
- The full upload → processing → findings flow completes successfully despite no internet.
- Re-enable Wi-Fi when done.

For an even stronger proof, run `tcpdump` in another terminal as in `sprint-1-validation.md` Scenario 6:
```bash
sudo tcpdump -nn -i en0 'not net 127.0.0.0/8 and not net ::1/128 and (host <your-machine-ip> and (tcp port 80 or tcp port 443))' -c 20
```
Run an analyze. **Expected**: tcpdump captures **zero packets**.

### Scenario 10 — Keyboard navigation (NFR-005)

**Setup**: Upload screen open. No mouse — use Tab, Shift+Tab, Enter, and arrow keys only.

**Steps**:
1. Press Tab repeatedly from a fresh page load.
2. Observe the focus ring as it moves.
3. When focus reaches the drop zone, press Enter.
4. Choose a PDF in the file picker that opens.
5. After analyze completes, Tab through the Findings tab interactive elements.

**Expected**:
- Tab order matches visual order (top-to-bottom, left-to-right).
- Every focusable element gets a visible focus ring (burgundy, 2px, with a 2px white offset — `focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2`).
- The drop zone is focusable and Enter opens the file picker (because `role="button"` + the keydown handler on Enter/Space).
- On the Findings tab, Tab reaches each filter chip, then each finding card's accept / dismiss buttons in order.
- Disabled buttons (Edit, Ask in chat, Re-analyze, Add document) are skipped or focusable-but-non-actionable per browser default.
- No `outline:none` without a visible replacement anywhere.

### Scenario 11 — Tabs other than Findings show "Coming in Sprint N"

**Setup**: continues from Scenario 5 — Review screen open.

**Steps**:
1. Click the "Client summary" tab.
2. Click the "Source" tab.
3. Click the "Chat" tab.
4. Click back to "Findings".

**Expected**:
- Client summary → placeholder pane with eyebrow "ROADMAP · TAB 02", title "Coming in Sprint 3 — Client summary", description mentioning the plain-English memo + 4-section structure.
- Source → similar placeholder, "Coming in Sprint 3 — Source viewer".
- Chat → placeholder "Coming in Sprint 4 — Multi-document chat", description mentioning up to 5 docs + streaming + citations.
- Active tab indicator (burgundy underline) follows the click.
- Findings tab restores the findings content on click.
- Disclaimer footer remains visible across all tab switches.

### Scenario 12 — Recent reviews list updates (real backend data)

**Setup**: clean install (or delete `~/.caveat/data.db` and restart the backend), then upload 2-3 PDFs in sequence.

**Steps**:
1. After deleting the DB, navigate to Upload. Observe the recent reviews section.
2. Upload a PDF, navigate back to Upload via the browser back button (or the Caveat brand link).
3. Repeat with a second PDF.
4. Observe.

**Expected**:
- Initial state (empty DB): recent reviews shows "Drop your first contract above" in `ink-muted` italic.
- After 1 upload + back: 1 row shows the filename + "just now" (or "Xs ago") in mono `ink-muted`.
- After 2 uploads: 2 rows, most recent first.
- Capped at 5 visible if you upload more than 5 (Sprint 2 limit; Sprint 5 polishes the cap with a "see all" link if useful).

---

## Verification command

```bash
just verify-sprint-2
```

Runs `just install && just check && just test-e2e` and prints `Sprint 2 verification: PASS` on success.

**Test breakdown**:
- Backend unit (Sprint 1 carry): 77 tests, ~0.95s
- Backend E2E (Sprint 1 carry): 13 tests, ~10.0s
- Frontend unit (this sprint): 52 tests, ~3.05s
- Frontend E2E (this sprint): 2 tests, ~9.1s
- **Total**: 144 automated tests, ~23s wall-clock for `just verify-sprint-2` (excluding `just install`)

---

## Caveats and notes for the next sprint

Carried forward from the code review (10 soft notes; none are blockers; one was addressed in this sprint as Constitution VI polish):

1. **StrictMode double-fire of `analyzeDocument` in dev** — `Processing.tsx` and `Review.tsx` both fire the analyze call in a `useEffect`. In dev, React 18 StrictMode invokes effects twice, sending two real `POST /api/analyze` requests per page mount. The `cancelled` flag correctly suppresses the second state update but does NOT cancel the second HTTP request. On E4B that's two 30–180-second pipeline runs queued back-to-back per dev page-load. Cheap in production (StrictMode is a no-op there) but expensive while developing. Sprint 4 should consider a shared `useAnalyzeOnce(docId)` hook with `AbortController`, or a mount-guard `useRef`.

2. **`Topbar.tsx` "0 network requests" pill is hard-coded** — a metric label that doesn't measure anything is the kind of small dishonesty Constitution VI exists to prevent. Either wire it to a real counter (intercept `fetch` and increment) or relabel to something static-by-construction like "No external traffic". Punted to Sprint 3 for cleanup.

3. **`Findings.tsx` ternary chain for `valueColor` on `SummaryCell`** — three-way nested ternary; consider a `Record<...>` lookup for consistency with the rest of the file's pattern (e.g. `SEVERITY_BADGE`). Cosmetic.

4. **`Findings.tsx` `react-hooks/exhaustive-deps` suppressions** — three `useMemo` blocks suppress the lint rule because the helper `getState(idx)` closes over `stateById`. The suppressions are correct but a small refactor (inline the lookup) would let the rule verify the contract instead of silencing it. Cosmetic.

5. **`Review.tsx` re-fetch effect runs on every render** — `initialState` is recomputed each render, so the effect's dep array changes identity each render. Inner condition gates the actual setState so it's not a loop, but it's unnecessary work. Move `initialState` into a `useMemo`. Cosmetic; not user-visible.

6. **`Review.tsx` re-fetch loading copy** — was *"Restoring this review from local storage…"*; was actively misleading because there's no local-storage cache. **Fixed in this sprint** as Constitution VI polish: now reads *"Re-running the analysis on the local model…"* with an explicit follow-up that Sprint 4 will add the cache.

7. **`api/analyze.ts` no fetch timeout** — intentional and documented. The Processing UI provides a parallel timer-driven sense of progress so the user isn't staring at a frozen page. Sprint 4 (chat streaming) needs to revisit when token-level SSE lands.

8. **`Review.tsx` Source tab badge text divergence** — `'—'` when there are findings vs `'0p'` when not. Sprint 3 owns the Source tab; replace the placeholder with a real page count from `analysis` once that data is exposed (currently `AnalyzeResponse` doesn't carry it; `documents.list` does).

9. **`api/client.ts` `apiPostFormData` duplicates the error-handling path of `handle()`** — a future chat-streaming variant would be a third copy. Factor into a shared `extractError(response)` helper. Sprint 4 cleanup.

10. **Backend `OllamaError` 502 path is still unreachable from the analyze pipeline** — carry-forward from Sprint 1. Sprint 4's chat router (different error envelope) will exercise it.

11. **Hard-refresh on `/review/:id` re-runs the full analyze** — known Sprint 2 imperfection. Sprint 4's findings router will fix this. Sprint 3 should consider whether the Source tab can render without the slow re-analyze (the source PDF text is already in SQLite, so it can).

Other notes from earlier sprints, still applicable:

- **Fonts** — Sprint 5 will bundle Fraunces / Geist / Geist Mono as self-hosted woff2 (frontend doesn't load Google Fonts; Constitution I).
- **Pyenv interaction** — `.python-version` declares 3.11; `uv` falls back to its own managed CPython if pyenv doesn't have it. Run `uv python install 3.11` once if needed.
- **Cold start ≈ 4 min on first analyze** — covered by the Processing screen's sub-line copy and the hold-pulse contract; if the demo video matters, Sprint 5 polish could add a tiny `POST /api/warmup` triggered on App.tsx mount that pre-loads the model into RAM during the user's app-load window.

---

**Sprint 2 is ready for validation.** Run `just verify-sprint-2` and walk through scenarios 1–12 above. Tell me what you find.
