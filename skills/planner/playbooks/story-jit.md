# Just-in-time story plan

Route for a story under an **open** parent epic (`facts.story.parent_epic_open`). Owns **both** the
fresh and the revise path for such a story (a prior story plan just refreshes in place). Planning the
story now — not up front with its siblings — is what keeps it current: it grounds against the epic
branch HEAD *after* every predecessor has landed. `facts.plan_ref` is the parent epic's
`epic/<N>-<slug>` branch (row `story-under-open-epic`), or the story's own open PR head when one exists
(row `open-pr-head` wins), or `main` when the parent's integration branch hasn't bootstrapped yet (row
`story-parent-epic-bootstrap` — the branch is created only once the resolver implements the first
story; independent of whether the epic *plan* itself already exists, see the next bullet).

**Run the spine first.** Read [`plan-spine.md`](plan-spine.md) and execute it end to end. The deltas
this route supplies:

- **Bootstrap the epic plan when absent (a judgment fill, not a named path).** If
  `facts.story.epic_plan.present` is false, the open parent epic has no plan yet. Author the epic plan
  first (the `epic.md` mechanics, run inline against `facts.story` — grounding stays at `main`, the
  bootstrap ref, since no epic branch exists yet), then continue in this same session to the story plan
  against it. This is a **composite epic+story session**; the emitted handoff is the story's (see below).
- **Reconcile contracts against what shipped (feedback edge).** Compare `facts.story.epic_delivery_log`
  (what predecessors *actually* delivered — the evaluator's record, read-only) against the epic plan's
  `## Story contracts` pinned shapes. On a mismatch the epic plan is stale — **stop and re-route to the
  planner on the epic in revise mode** (don't reshape the story to fit a wrong contract, don't run the
  epic revise inline).
- **Schema sections.** The standard single-issue schema plus the `**Epic:** #<epic-#> — <epic title>`
  backlink as the **first line after** the marker (never above it) and a `## Epic contract` section —
  `Delivers` (matching the epic's `## Story contracts`) and `Consumes` (each already in the delivery
  log), every line `[epic-plan: #<N>]`-cited (see [`../references/plan-schema.md`](../references/plan-schema.md)).
- **Off-ramp (spine S4).** `off-ramp: not offered` — a story that outgrows its slice is an epic-contract
  problem: re-route to the planner on the parent epic in revise mode (the feedback edge above).
- **Reviewer dimensions (spine S7).** `1, 2, 3, 4, 6, 8` — pass the epic plan + delivery-log staged
  paths so Dimension 8 checks the `## Epic contract` against the epic's `## Story contracts` and the
  log. A Dimension-8 BLOCKER tracing to a wrong *epic* contract is the same feedback edge: re-route to
  the epic in revise mode. If this story is itself fully gated by an unresolved OQ, re-route to
  answer-the-question rather than authoring a hollow story plan.

Everything below runs only after the spine returns; on a re-route exit, emit the matching handoff.

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md):

- **Just-in-time story plan posted**: `Story:` line (`plan: ✓ (<url>)`) + parent `Epic:` line (progress
  count) + `Grounding:` (`read at epic/<N>-<slug>@<short-sha>`, or `origin/main` on the bootstrap case)
  + `**Open questions:**` **whenever any plan posted this session carries `## Open questions`** — for a
  composite epic+story session that means the line renders when *either* the epic plan or the story plan
  carries one; drop it never because the shape matched a single-axis example first (bug (b)). `Next:
  /github-pipeline:resolver #<N>`, `Why:`.
- **Re-route → planner (epic revise)** (contract/Dimension-8 mismatch): `Next:
  /github-pipeline:planner revise #<epic> — <pred> shipped <actual> but the contract pinned <pinned>`.
- **Open-question total block**: terminal-style, `plan: ✗`, re-run breadcrumb (drafter first if no
  companion question is filed).
