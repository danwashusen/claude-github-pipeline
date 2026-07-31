# Revise a plan

Route for `vector.mode: revise` on a standalone issue or an epic (a story under an open epic revises
through `story-jit.md` instead). A prior `<!-- implementation-plan:v1 -->` comment exists
(`facts.plan.present`); this refreshes it against today's reality and reconciles any DoD ticks the
resolver already projected. This is one flow **parameterized by the type facts** — `facts.plan_ref`
(the open PR head when `facts.revise.open_pr`, else the base branch), `facts.revise.phase_tracker`, and
`facts.epic` for an epic revise — never a type branch. **One exception is a re-derivation, not a branch:**
on HARD "Start fresh" the session's starting `facts.plan_ref` stops being valid the moment the PR it was
selected for closes — the HARD sequence below re-runs prep and lets the row table re-select it.

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
- **Off-ramp (spine S4).** Keyed on `facts.vector.type` like the dimension set: `offered` for a
  standalone issue, `not offered` for an epic revise. On "Split as epic" the superseded plan comment
  stays put — the promoted Epic's own re-plan supersedes it via `--delete-marker-id`.
- **Show + confirm (spine S8 variant).** Show the diff-style plan update **and** the proposed body-edit
  diff together, then gate: SOFT → **Apply** / **Cancel**; HARD → **Start fresh (recommended)** /
  **Apply in place anyway** / **Cancel**. **SOFT-Apply** runs the spine's persist immediately as written
  (delete the stale comment via `--delete-marker-id <facts.plan.comment_id>`, repost, then apply the
  reconciled DoD body via `gh_persist.py edit-body`) — the footer stays pinned at the open PR head
  correctly, because a SOFT revise never closes that PR; the next resolver run is a `continue` on the
  same branch, so grounding there stays valid. **HARD-Start-fresh does NOT run the spine's persist
  here** — it defers posting to its own sequence below, because the plan drafted against
  `facts.plan_ref` (the open-PR-head row, selected before this revise even started) is about to be
  grounded on a branch this decision is closing; posting it as-is would leave the footer, and every
  precedent citation in the body, pointing at a branch nothing can read once it's gone.
- **HARD "Start fresh" — close, re-ground, then post (in that order).** Triggered only after the user
  picks **Start fresh** at the gate above — this sequence *executes* that already-gated decision, it
  gates nothing itself:

  1. **Capture what `## Predecessor` and the DoD un-tick need, from the facts already in hand** (the
     closed-PR number and branch from `facts.revise.open_pr`, the old plan's comment id from
     `facts.plan`, the ticked-bullet/phase-tracker state from `facts.revise.phase_tracker`) — before
     step 2 replaces `facts` wholesale, so nothing needed for these two writes depends on a fact only
     the stale envelope carries.
  2. **Close the superseded PR first, with the exact supersession marker text staged.** This is a
     cross-skill contract, not free prose: the resolver's predecessor-PR detection greps the closed
     PR's **close comment** for the literal phrase `Re-plan superseded this PR` (the marker
     `close-pr --comment-file` posts, per `gh pr close --comment`) to find the branch a HARD re-plan
     superseded, for its `-vN` fresh-branch suffixing. Stage that phrase byte-faithful to
     `<facts.scratch>/close-comment.md`:

     ```
     Re-plan superseded this PR. See updated plan at <new-plan-comment-url>. A new branch and PR will
     open at the next `/github-pipeline:resolver #<N>` run.
     ```

     then close through the single write path:

     ```bash
     ${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py close-pr <owner/repo> <closed-PR#> \
       --comment-file "<facts.scratch>/close-comment.md"
     ```

  3. **Re-run `prep_planner.py` in the same clone** (`SKILL.md` §1) — safe to call a second time now:
     the D6 fix moved the `.worktrees/` bootstrap write to `info/exclude`, so a second prep in one
     clone can never trip its own `ROOT_DIRTY`. With the PR now closed, the open-PR-head row no longer
     fires, so `plan_ref` re-selects **deterministically off the row table** — `main` for a standalone
     issue, the parent epic's branch for a story revised here as an epic (never hardcode `main`; let
     the fresh facts decide).
  4. **Re-ground at the fresh `facts.read_workspaces.grounding` workspace** (spine S3) and finalize the
     plan body against **that** ref — re-verify every precedent citation the diff-shown draft made
     still resolves there (a HARD revise already changed a locked decision, so treat this as the
     drafting step's own re-run, not a footer-only patch). Then post through the single write path
     (the spine's persist, run now instead of at the earlier gate): delete the stale comment via
     `--delete-marker-id`, repost with the footer pinned to `<new plan_ref>@<new grounding SHA>` and
     the `## Predecessor` section (built from step 1's captured facts, inserted after `## Approach`),
     and un-tick the DoD bullets to the predecessor annotation form via `edit-body` (from step 1's
     captured tracker state).

  Leave the closed PR's branch in place — the `## Predecessor` reminder is the user's cue to clean it
  up after the new PR lands.

Everything below runs only after the spine returns.

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md):

- **Revise — plan refreshed**: same forward shape as the fresh route, with the **new** comment URL in
  the `Issue:` line (the stale one was deleted). `Next: /github-pipeline:resolver continue #<PR>` when a
  draft PR is open, else `/github-pipeline:resolver #<N>`. `Why:` names what changed (the renamed symbol,
  the resolved OQ) — and, on HARD Start-fresh, that the superseded PR was closed with the supersession
  note.
- **Epic-shaped, planning aborted** (seam gate chose "Split as epic"): `plan: ✗`, no `Grounding:`;
  `Next: /github-pipeline:drafter` revising #N as an Epic per the seam-analysis comment.
