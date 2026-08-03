# Epic-integration PR

Route for `vector.type == epic-integration` (head matches `epic/<N>-<slug>`, base `main`). One PR that
lands the accumulated diff of every child story onto `main` in a single merge — a qualitatively larger
risk surface than a single-issue PR.

**Run the spine first.** Read [`evaluate-spine.md`](evaluate-spine.md) and execute it end to end.
Three facts shape how the spine behaves on this route — all already in the facts block, so they need
no branch in any body:

- **Full-suite health gate.** The test-selection sub-agent escalates to the full canonical suite for
  `pr_type == epic-integration` (its escalation rule) — the accumulated diff *is* the union of every
  child story, exactly the integration risk this gate exists to verify, so targeting there would miss
  cross-story interactions. This is the sub-agent's own rule fed `facts.pr_type`; don't override it.
- **Epic-DoD historical walk.** The closing issue is the **epic** (via `Fixes #<epic>` in the PR
  body), so `facts.dod[<epic>]` carries the epic body's `## Definition of done`. An epic body's DoD
  has no per-phase projection annotations (per-phase projection lives on the child **story** issues,
  already ticked there), so the spine's DoD dimension takes its **historical-walk** fallback naturally:
  walk every epic-level bullet and judge it against the **accumulated diff**. The evaluator's job here
  is to verify the accumulated diff satisfies those epic-level bullets — not to re-verify per-phase
  projections. Read the epic's story set (its sub-issues, or a legacy epic's `## Stories` checklist —
  [`../../_shared/epic-story-hierarchy.md`](../../_shared/epic-story-hierarchy.md)), `## Definition of done`, and `## Goal` for grounding;
  verify `Fixes #<epic>` is present and every story PR is listed in the body.
- **Always-gated merge.** `facts.config.merge_policy` reports `epic-integration → ask` unconditionally
  (prep forces it; a stray `epic-integration:` line in the config block is ignored). So the spine's
  S7-gate **always** runs for this route even on a clean APPROVE — an epic-integration merge is never
  hands-free. The gate's **Approve** splits into **Approve (merge commit)** / **Approve (squash)** to
  capture the strategy (merge commit when `commit_count > 1`, preserving per-story squash commits in
  `main`'s history; squash on the rare single-commit epic).

**Load-bearing `## Follow-ups` re-adjudication.** Integration is the final accumulation point, where
the resolver may have hand-classified review findings as follow-ups. The spine's dimension-4 re-adjudication
is decisive here: a deferral that maps to an in-scope grounding invariant **or** an epic-level
`## Definition of done` bullet blocks the integration → soft-reject, naming the violated doc section /
epic DoD bullet plus the deferred-to issue. The epic is not integration-ready until that work lands on
the epic branch.

Everything below runs **only after S7-merge actually merged**; on any no-merge exit, skip to the
handoff. Epic integration files no story bookkeeping (no story to close, no epic checkbox to tick,
no delivery-log line — those are the child-story route's actions); the epic closes via `Fixes #<epic>`
on the merge into `main`.

## After the merge — residual follow-ups + cleanup

File residual non-blocking follow-ups (shared with the other routes): de-dup against the PR body's
`## Follow-ups` *Filed* entries, file each via
[`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md) (parent reference = this PR +
the epic issue), post the URLs as a brief PR comment. Then purge the scratch dir only
(`rm -rf "<facts.scratch>"`) — the worktree is **deliberately retained** (this session runs inside
it); the terminal handoff's fence hands the operator
`/github-pipeline:workspace-close <facts.workspace.branch>` for the teardown + gated removal.

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md) and emit the **Epic
integration PR clean merged — terminal** shape: Epic line, PR line (`merge: merge → main@<sha>` for a
merge commit, or `squash → main@<sha>`), Cleanup line, `Next: (terminal — no follow-up skill)`, and a
`Why:`. `review:` is `APPROVE (operator)` (epic is always gated). The epic closes via `Fixes #<epic>`;
the pipeline ends here.

On a **no-merge** exit, emit the matching rubric shape — **soft-reject → re-route** to
`/github-pipeline:resolver continue #<PR>`, or **APPROVE-but-skipped** with the manual `gh pr merge`
command.
