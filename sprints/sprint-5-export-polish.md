# Sprint 5 — Export + Polish

**Duration**: 2 days
**Goal**: Export Word memo and signed PDF with firm letterhead and disclaimers. Hardware detection chooses the right Gemma variant. Status pills are accurate.

## Opening prompt

```
We are starting Sprint 5 of Caveat AI. Sprints 0–4 should be committed.

Read:
1. CLAUDE.md
2. .specify/memory/constitution.md (focus: IV — disclaimers; VIII — model choice)
3. specs/001-caveat-ai/spec.md (User Stories 4 and 5, FR-010, FR-011, FR-013, FR-014)
4. design-tokens.md
5. docs/caveat-prototype-v3.html — Export screen
6. sprints/sprint-5-export-polish.md

Run /speckit.tasks. Delegate. Generate sprint-5-validation.md.
```

## User stories covered

- **US4** — Export package generation
- **US5** — Hardware capability detection and fallback

## In scope

**Backend:**
- `caveat/export/docx_memo.py` — `python-docx` template with letterhead from `firm.json`, sections (Summary, Material Findings with cited quotes), signature block, disclaimer footer
- `caveat/export/pdf_memo.py` — `weasyprint` rendering same template as HTML → PDF
- `caveat/export/redline_docx.py` — annotated original .docx with track-changes-style insertions/deletions for accepted redlines (this is the most complex; if time runs short, ship as P3 stretch)
- `caveat/export/email_blurb.py` — short text version for Outlook/Gmail paste
- `caveat/routers/export.py` — POST /api/export takes formats array + destination path; writes files; returns absolute paths
- `caveat/llm/hardware_detect.py` — detects RAM, GPU VRAM, Apple unified memory; returns "31b" or "e4b"; called once at first launch and cached in `firm.json`
- `firm.json` schema and onboarding flow if missing on first launch (simple form: firm name, lawyer name, bar number)

**Frontend:**
- `pages/Export.tsx` — matches prototype Export screen. Format selection cards. Destination input. Preview pane on the right showing the Word memo as it would render. "Generate" button.
- Status pills updated to reflect detected model (`Local · Gemma 4 31B` or `Local · Gemma 4 E4B`)
- First-launch onboarding modal asking for firm info if `firm.json` missing

## Out of scope

- Anything not in the spec's MVP scope

## Definition of Done

- Export selecting Word + PDF generates both files at the destination path
- Generated Word memo opens in Microsoft Word (or LibreOffice), shows letterhead, sections, citations as block quotes, signature, disclaimer footer
- Generated PDF opens, looks visually consistent with the preview pane
- Disclaimer present in both, cannot be removed via UI
- Hardware detection picks 31B on a 32GB+ RAM machine, E4B on a 16GB machine (testable with mock hardware probe)
- Status pill shows the detected model
- `just check`, `just test-e2e` green

## Validation scenarios required in sprint-5-validation.md

1. Complete a full review (upload, analyze, accept some findings)
2. Click Export → screen renders with format options
3. Select Word + PDF, type a destination, click Generate
4. Verify both files exist at the destination
5. Open the Word memo: letterhead correct, sections present, citations as block quotes, signature, disclaimer footer present
6. Try to remove the disclaimer in Word: confirm it's there as plain text (not protected, but always rendered by the export)
7. Open the PDF: visually matches the Word memo
8. Restart app on a fresh `firm.json`-less state; onboarding asks for firm info
9. On a 32GB+ machine, status pill says "Gemma 4 31B"
10. Mock the hardware probe to return 16GB RAM; restart; status pill says "Gemma 4 E4B"
