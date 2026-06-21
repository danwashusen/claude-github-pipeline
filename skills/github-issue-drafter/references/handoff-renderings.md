# Handoff renderings — github-issue-drafter

Every clean run of the drafter ends with a single `## Handoff` block. The schema, omission rules, and closed-set state-marker vocabulary live in [`../../_shared/handoff-format.md`](../../_shared/handoff-format.md); this file holds the drafter's worked rendering shapes. Match the run's outcome to a shape and fill the snapshot from the data Step 8 lists.

### Renderings

**Single issue filed (the common case).** Forward to the planner.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✗

**Next:** plan the implementation in a fresh session.

    /github-pipeline:github-issue-planner #142

**Why:** the planner will research the approach, ground it in docs + codebase precedent, post a verified `<!-- implementation-plan:v1 -->` comment, and lock the decisions the resolver needs.
```

**Epic batch filed.** Forward to the planner on the Epic — the planner's own fan-out plans each child story under its `## Stories` list and sequences them.

```
## Handoff

**Epic:** #150 — Chat & session UX polish · open · epic · plan: ✗
**Stories:** #151, #152, #153, #154, #155 (5 filed, dependency-ordered)

**Next:** plan the Epic in a fresh session — the planner will fan out and plan each child story.

    /github-pipeline:github-issue-planner #150

**Why:** the planner posts the Epic-level plan first, then plans each child story and sequences them. Don't run the resolver on any story until its plan is posted.
```

**Revise mode (single issue or Epic).** What's next depends on whether a plan already exists for this issue and whether the revise materially changed scope, acceptance criteria, or the contracts the plan was built against (Step R6 already flags this — re-use that judgment for the handoff):

- **No plan exists yet** (`plan: ✗`) → forward to the planner to author one. Same shape as the first rendering above.
- **Plan exists and the revise was material** → the plan is now `stale`; forward to the planner in revise mode to refresh it.
- **Plan exists and the revise was cosmetic** (typo fix, link tidy, untouched contracts) → the plan stays current. Either the issue already has a PR in flight (terminal — issue and plan and PR are aligned, nothing for a follow-up skill to do here) or no work has started yet and the user can run the resolver when ready.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: stale

**Next:** refresh the plan in a fresh session — this revision materially changed scope.

    /github-pipeline:github-issue-planner revise #142

**Why:** the revise reshaped the acceptance criteria (added bulk-export and removed PDF). The implementation plan from <date> assumed the previous shape; re-running the planner in revise mode rebuilds the plan against the new body before any code work resumes.
```

For an Epic revise that re-ordered or merged child stories (dimension-5 / dimension-7 surfacing during R-special-case), the `Why:` line cites the specific bullet change so the planner's re-audit can ground in evidence.
