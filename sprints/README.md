# Sprint plan — Caveat AI

Each sprint is a focused chunk delivered in one or two Claude Code sessions, then committed directly to `main`.

**Each sprint must end with `sprint-N-validation.md`** per Constitution Principle X. You (the human) run `just verify-sprint-N` and execute the manual scenarios. If anything fails, the next session starts by fixing those.

## The 7 sprints

| # | File | Days | Goal |
|---|---|---|---|
| 0 | `sprint-0-setup.md` | 1 | Repo + tooling + first commit |
| 1 | `sprint-1-backend-slice.md` | 3 | `/api/analyze` returns real findings with validated citations |
| 2 | `sprint-2-frontend-slice.md` | 3 | Browser flow: upload → processing → findings |
| 3 | `sprint-3-summary-source.md` | 2 | Client summary tab + Source viewer with highlights |
| 4 | `sprint-4-multidoc-chat.md` | 4 | Sidebar, 5 docs simultaneously, streaming chat with citations |
| 5 | `sprint-5-export-polish.md` | 2 | Word/PDF export, hardware fallback, polish |
| 6 | `sprint-6-demo-submission.md` | 1 | Demo video, dev.to post, submission |

Total: 16 days, ending May 24, 2026.

## How a sprint runs

1. Start a fresh Claude Code session in the repo
2. Paste the sprint's "Opening prompt" (top of each sprint file)
3. Claude Code reads CLAUDE.md, constitution, spec, plan, and the sprint file
4. Claude Code runs `/speckit.tasks` to generate `specs/001-caveat-ai/tasks.md` scoped to this sprint
5. Implementation, with delegation to subagents (`backend-python`, `frontend-react`, `test-engineer`)
6. At the end, `code-reviewer` reviews the diff
7. Main agent generates `sprints/sprint-N-validation.md`
8. You run `just verify-sprint-N` and walk through the manual scenarios
9. If everything passes, commit. If not, file issues in the validation doc and continue next session.

## Slip protection

If you reach end of D9 (planned end of Sprint 3) and you're behind:
- Drop Sprint 5 (export + polish). Mention as roadmap in the post.
- Compress Sprint 6 to half a day.

If you reach end of D13 (planned end of Sprint 4) and you're behind:
- Skip Word memo, ship only PDF export
- Skip hardware fallback (use 31B always; demo machine is fine)
