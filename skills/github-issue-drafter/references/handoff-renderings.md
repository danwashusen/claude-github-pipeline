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

**Single issue filed with open questions (drafted from a source with unresolved OQs).** Same forward-to-planner shape, plus a free-form `**Open questions:**` line (per handoff-format.md — not a state marker) listing the companion `question` issues and how the OQs were disposed. The `Why:` notes the planner will plan only the decided scope and surface the OQs in its plan.

```
## Handoff

**Issue:** #142 — Build patient dashboard · open · feature · plan: ✗
**Open questions:** #211 (audience:business), #212 (audience:clinical) — 3 scoped out, 1 blocked-by; see the issue's ## Open questions

**Next:** plan the implementation in a fresh session.

    /github-pipeline:github-issue-planner #142

**Why:** three surfaces are scoped out pending #211/#212 and one is natively blocked-by #212; the planner plans the decided dashboard scope and records the open questions in its plan. Answer the companion questions in their threads to unblock the deferred work.
```

Each companion `question` filed in the same run emits its own paste-ready snippet + terminal handoff (the question renderings below) — they are separate issues, so they appear as their own `#NN`, not folded into the build issue's handoff beyond the `Open questions:` line.

**Epic batch filed.** Forward to the planner on the Epic — the planner posts the high-level epic plan (cross-story contracts + sequencing); each child story is then planned just-in-time as it's built.

```
## Handoff

**Epic:** #150 — Chat & session UX polish · open · epic · plan: ✗
**Stories:** #151, #152, #153, #154, #155 (5 filed, dependency-ordered)

**Next:** plan the Epic in a fresh session — the planner posts the epic plan; stories are planned just-in-time.

    /github-pipeline:github-issue-planner #150

**Why:** the planner posts the epic-level plan (pinning cross-story contracts and sequencing), then each child story is planned just-in-time against current epic HEAD as it's built. Don't run the resolver on any story until its plan is posted.
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

**Question filed or revised (terminal).** A `question` is answered by a human in the issue thread, not by a downstream skill, so its handoff is **terminal**: drop the fenced command block (per [`../../_shared/handoff-format.md`](../../_shared/handoff-format.md) "Terminal endings"), omit the `research:`/`plan:` markers (they don't apply), and add a question-only `**Audience:**` line listing the `audience:*` labels (comma-separated for multiple). The paste-ready doc snippet is part of the post-file output *before* this block — nothing follows the handoff.

```
## Handoff

**Issue:** #210 — PRD-OQ-06b — Which billing model for v1? · open · question
**Audience:** business

**Next:** (terminal — no follow-up skill)

**Why:** open question for the business stakeholder — answered by a person in the issue thread, not by the pipeline. Once it's answered, revise the doc that tracks it (snippet above) and file any resulting work as its own issue.
```

Revise-mode on a `question` is terminal too — same shape, with `state`/title reflecting the edit.
