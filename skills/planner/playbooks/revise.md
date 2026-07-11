# Revise a plan

Route for `vector.mode: revise` on a standalone issue or an epic (a story under an open epic revises
through `story-jit.md` instead). A prior `<!-- implementation-plan:v1 -->` comment exists
(`facts.plan.present`); this refreshes it against today's reality and reconciles any DoD ticks the
resolver already projected. This is one flow **parameterized by the type facts** — `facts.plan_ref`
(the open PR head when `facts.revise.open_pr`, else the base branch), `facts.revise.phase_tracker`, and
`facts.epic` for an epic revise — never a type branch.

**Run the spine first.** Read [`plan-spine.md`](plan-spine.md) and execute it end to end, focused on
**what changed** (re-walk the thread for newer direction, re-`Grep` the workspace for symbols the plan
names that may have drifted, re-check open questions) — don't re-derive untouched sections. The deltas
this route supplies:

- **Re-check open questions.** An OQ the prior plan planned around whose companion `question` is now
  **resolved** (closed, or answered-in-thread via the tiered read in
  [`../../_shared/open-question-links.md`](../../_shared/open-question-links.md)) is no longer deferred —
  fold the now-decided scope into `## Changes` / `## Test plan` and drop its `## Open questions` entry;
  a newly-opened OQ adds a plan-around entry. Never resolve an open OQ yourself.
- **Compute reconciliation** ([`../references/revise-reconciliation.md`](../references/revise-reconciliation.md)).
  Diff old plan vs new plan, classify **SOFT** vs **HARD**, and compute the body-edit diff against
  `facts.revise.phase_tracker`. When no draft PR exists this is a no-op (no projected ticks). An
  evaluator-rejection annotation is preserved verbatim — never auto-cleared.
- **Reviewer dimensions (spine S7).** The same set the issue's fresh route would pass, keyed on
  `facts.vector.type` (a bug adds 9; multi-phase adds 7; an epic uses 1, 2, 3, 5, 6), plus 10 when the
  plan carries `## Open questions`.
- **Show + confirm (spine S8 variant).** Show the diff-style plan update **and** the proposed body-edit
  diff together, then gate: SOFT → **Apply** / **Cancel**; HARD → **Start fresh (recommended)** /
  **Apply in place anyway** / **Cancel**. On Apply, the spine's persist deletes the stale comment via
  `--delete-marker-id <facts.plan.comment_id>` and reposts; SOFT-Apply also applies the reconciled DoD
  body via `gh_persist.py edit-body`.
- **HARD "Start fresh".** Add a `## Predecessor` section to the new plan (after `## Approach`), un-tick
  the body's DoD bullets to the predecessor annotation form (staged + `edit-body`). Then close the
  superseded PR **with the exact supersession marker text staged first** — this is a cross-skill
  contract, not free prose: the resolver's predecessor-PR detection greps the closed PR's **close
  comment** for the literal phrase `Re-plan superseded this PR` (the marker `close-pr --comment-file`
  posts, per `gh pr close --comment`) to find the branch a HARD re-plan superseded, for its `-vN`
  fresh-branch suffixing. Stage that phrase byte-faithful to
  `<facts.scratch>/close-comment.md`, e.g.:

  ```
  Re-plan superseded this PR. See updated plan at <new-plan-comment-url>. A new branch and PR will open
  at the next `/github-pipeline:resolver #<N>` run.
  ```

  then close through the single write path:

  ```bash
  ${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py close-pr <owner/repo> <closed-PR#> \
    --comment-file "<facts.scratch>/close-comment.md"
  ```

  This runs only after the user has already picked **Start fresh** at the gate above — the op executes
  the already-gated decision; it does not itself gate anything. Leave the closed PR's branch in place
  (the `## Predecessor` reminder is the user's cue to clean up after the new PR lands).

Everything below runs only after the spine returns.

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md):

- **Revise — plan refreshed**: same forward shape as the fresh route, with the **new** comment URL in
  the `Issue:` line (the stale one was deleted). `Next: /github-pipeline:resolver continue #<PR>` when a
  draft PR is open, else `/github-pipeline:resolver #<N>`. `Why:` names what changed (the renamed symbol,
  the resolved OQ) — and, on HARD Start-fresh, that the superseded PR was closed with the supersession
  note.
