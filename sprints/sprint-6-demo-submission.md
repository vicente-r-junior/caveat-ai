# Sprint 6 — Demo + Submission

**Duration**: 1 day
**Goal**: Record the 2-minute demo video, write the dev.to post, submit to the Gemma 4 challenge.

## Opening prompt

```
We are starting Sprint 6 of Caveat AI. Sprints 0–5 should all be committed
and verified. The product works end-to-end.

Read:
1. CLAUDE.md
2. .specify/memory/constitution.md
3. specs/001-caveat-ai/plan.md (section 8 — demo script)
4. sprints/sprint-6-demo-submission.md

This sprint is mostly about packaging and presentation. Run /speckit.tasks
for the smaller technical bits. The video and the post happen outside
Claude Code (record on your machine, write the post in the dev.to editor).
Generate sprint-6-validation.md at the end.
```

## In scope

- `just demo` command: starts backend with seed data already loaded (3 fixture contracts pre-analyzed), opens browser to localhost:8787
- README updated with quickstart + screenshots + license + disclaimer
- LICENSE file (MIT)
- Demo video recorded per the plan's section 8 script (2 minutes, voiceover or captions)
- dev.to post draft (markdown) covering: the problem, the solution, the local-first justification, why Gemma 4 specifically (128K context for multi-doc), honest performance numbers, what's not in the MVP and why, link to repo, link to video
- Final repo polish: any obvious dead code removed, README readable, screenshots placed in `docs/screenshots/`
- Submission checklist: dev.to post published, repo public, video uploaded, contest tags applied

## Out of scope

- New features
- Refactoring not driven by the demo script
- Anything that doesn't help the submission

## Definition of Done

- Demo video uploaded somewhere durable (YouTube unlisted, Loom, etc.)
- dev.to post published with `#gemma4challenge` tag and the video embedded
- Repo public on GitHub with README that lets a stranger run `just demo`
- `sprints/sprint-6-validation.md` exists with the submission checklist

## Validation scenarios required in sprint-6-validation.md

1. Fresh clone on a different machine; `just install` then `just demo` works
2. Watch the demo video end-to-end; every step in plan section 8 is shown
3. The video shows the airplane-mode test (Wi-Fi toggle off, analysis still works)
4. The video shows tcpdump or equivalent confirming zero non-localhost traffic
5. Read the dev.to post; the local-first justification is clear and the Gemma 4 model choice is justified
6. Link to the contest tag works
7. Submission confirmed (you can see the post in the contest feed)
