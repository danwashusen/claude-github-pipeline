# Review fix round — main-loop procedure (spine S5.1)

Carried from the v1 resolver's review-loop sub-agent per the S10 cutover — the v1 §10 outer loop, whose
classification rubric (v1's §10.4) is split between this file and [`common-pitfalls.md`](common-pitfalls.md).
Until 4.11.0 this was a `general-purpose` sub-agent prompt dispatched once per iteration. It was retired
because the per-iteration cold start plus the JSON → card → re-dispatch serialization was slow and left the
operator with no view of what was being fixed (a sub-agent's tool calls don't stream to the parent). The
steps now run in the **main conversation**, which also already holds the plan, the audit, the doc grounding,
and the code it just wrote. `review` itself always ran in main and still does — it is unreachable from
inside an `Agent`-dispatched sub-agent (PR #607).

This is **not** a sub-agent prompt: no placeholders, no JSON return, and every gate is a direct
`AskUserQuestion` card you render yourself. The fix disciplines are no longer copied here — you hold
`common-pitfalls.md` in context, which is the file that owns them.

## What you hold at round entry

- **The verdict text** — this round's `review` output, or the cold read's `## Findings` when S5.1 step 4
  fed you one. Classify it; act on it.
- **PR** number, URL, and `<owner/repo>`; the originating issue and its parent epic (or none);
  `facts.audit_ref` (bare) as the integration target.
- **Workspace**: `facts.workspace.path` — the cwd for every command you run.
- **Iteration number** — the 1-based index in S5.1's outer loop.
- **The addressed-items list** — one-line summaries of what you fixed in every prior round this run. You
  append to it in step 9; the deadlock check in step 3 reads it.
- **Doc-grounding statement** (from S3) and any audit / plan overrides carried into the PR body — use them
  when defending an implementation choice in a PR reply.
- **Test config**: `facts.config.static_checks` and `facts.config.test_target_raw`.
- **References**: [`retry-ladder.md`](retry-ladder.md) (the pre-push gate's 3-run cap + research
  breakpoint), [`follow-up-tracking.md`](follow-up-tracking.md) (the follow-up registry and its timing),
  and [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md) for the drafter-proxy filing
  protocol. Apply them as written.
- **Resume hint** — this loop may be picking up mid-flow (a prior resolver run was interrupted, or a human
  reviewer commented between invocations). On **iteration 1 only**, before classifying, re-read the
  accumulated PR comments and reviews (`gh pr view --comments`, plus the `pulls/<N>/reviews` and
  `pulls/<N>/comments` REST endpoints via `gh api`) and treat any human reviewer comment as additional
  Addressable input alongside the verdict.

## Classification rubric

Apply to every listed item:

- **Addressable** — a concretely-named change on already-modified files or the issue's scope. The DEFAULT
  for any concretely-named change. Soft politeness ("could be fast-follow", "not blocking", "future PR")
  does NOT by itself move an item out of Addressable.
- **Cheap-fix-override** — a <= ~20-line fix on already-modified files, even when the reviewer offered to
  defer it: address it here.
- **Explicitly-deferred** — routed elsewhere with a concrete tracking target (filed as #M, depends on an
  un-landed sibling, a citable PRD/scope exclusion): file it as a follow-up.
- **Decision-required** — an architectural / API-break / scope-change tradeoff the reviewer named candidate
  paths for: render the `Decision` card.
- **Grounding-violation** — a diff that violates a documented constraint the issue/epic kept in-scope: if
  addressable here, fix it; else render the `Grounding` card. NEVER filed as a follow-up.

## Steps (one round — no inner loop)

1. **Classify** every issue and suggestion per the rubric. The reviewer's own "approved" verdict line is
   NOT the exit condition — re-classify each listed item. The cheap-fix override applies to <= ~20-line
   fixes on already-modified files even when the reviewer offered to defer. On iteration 1, fold in the
   human PR activity from the resume hint.
2. **Gates before any edit.** A Decision-required item → render the `Decision` card now. A
   Grounding-violation item that is **not** addressable on this PR → render the `Grounding` card now. When
   a finding matches **both**, render `Grounding` — a hard block outranks a soft approval gate. Act on the
   answer within this round. (A Grounding-violation that *is* addressable was reclassified Addressable in
   step 1 and is fixed in step 4; it is never filed as a follow-up.)
3. **Deadlock check.** If any item in the current verdict matches a summary in the addressed-items list
   (same file, same surface, same suggested change with no acknowledgement of your prior fix), render the
   `Review loop` card. Don't address it a second time on the same hypothesis.
4. **Fix** every Addressable and Cheap-fix-override item. Apply `common-pitfalls.md`'s three
   fix-discipline bullets to each fix *before* writing it — "Don't fix the instance when the finding names
   a class", "Don't conform code to a stated invariant a finding contradicts", "Don't split an atomic call
   without naming its implicit properties". A retro found fix rounds carrying several times the defect
   density of the code they corrected; those three are what that bought. File every Explicitly-deferred
   item via the follow-up filing protocol (urgency `file-now`, type per the reviewer's framing) and capture
   the returned URLs. Never file a Grounding-violation item.
5. **No edits** (zero Addressable, zero Cheap-fix-override items) → this round is complete. Skip steps 6–8
   and go to step 9, then back to S5.1 step 3, whose "addressed nothing" branch settles the loop — whether
   or not the verdict's own line said approved.
6. **Defect-inject** every new or changed assertion step 4 added. An assertion written to catch a finding's
   defect does not count as coverage until an injection has made it fail: stage the fix first (the
   injection revert restores the staged state; committing waits for step 8, after the gate), inject the
   defect the assertion targets, run the assertion red, revert the injection. Run injections with the
   wrapper's targeted single-test invocation (the run-2 syntax in `retry-ladder.md`), batching
   distinct-site injections into one run — never the full selected suite per assertion. Green-against-the-
   defect means the test is vacuous — the usual shapes are "bad" state constructed after the code under
   test already read the good state, and an absence-assertion with no positive control proving it can ever
   fail. Rewrite and re-inject, at most twice per assertion; still green after that, file the assertion as
   a `deferred-test` follow-up (step 4's filing protocol) instead of looping. Injection runs verify the
   test, not the diff, and do not count against the retry ladder's 3-run cap (`retry-ladder.md`).
7. **Run the §10.6 pre-push verification gate** (static checks → test-selection sub-agent → test
   execution). Dispatch the test-selection sub-agent with its **diff-base override** set to current HEAD
   (`git rev-parse HEAD` in the workspace): your commits wait for step 8, so HEAD is still the last pushed,
   gate-verified state and your fixes are working-tree-only — the override scopes selection to what this
   round actually changed. Scope rationale and its accepted gap: `retry-ladder.md`'s "§10.6 selection
   scope". The retry ladder caps a single visit at 3 runs with a forced research breakpoint between cheap
   and deep fixes. On escalation, render the `Tests red` card.
8. **Commit. Push. Reply on the PR**, briefly describing what changed in response to which points of
   feedback. That per-round comment is the GitHub-side record — how a reviewer, and the next session,
   follows what this loop did without replaying the conversation.
9. **Record.** Append this round's one-line item summaries to the addressed-items list. Hold the filed
   follow-up URLs for the PR body and the handoff. Carry any **procedural note** (something the next
   session should know that is not worth an issue) as a capture-not-file item per
   `follow-up-tracking.md` — it lands in the PR body or the handoff `Why:`, never as a filed issue.

## Guard rails — direct cards

Render each via `AskUserQuestion` per [`../../_shared/asking-the-user.md`](../../_shared/asking-the-user.md)
at the point it fires. An answer settles that gate for the run — don't re-raise it on a later round.

Two kinds of answer, and the difference is load-bearing. A **continuing** answer (Try another angle,
Accept + defer, Push with reds, Defer the tests, a named architectural path) is acted on inside this
round, which then finishes normally. A **terminating** answer — **Re-plan** and **Restructure** (re-route
to the planner), **Abort** and **Abort loop** — ends the round *and* S5.1 on the spot: stop fixing, run no
further gate, and hand back to the routed playbook for its handoff, quoting the trigger in the `Why:`.
Don't try to satisfy a re-route inside the round; there is nothing here that can.

- **Same-feedback-twice deadlock.** The current verdict flags an item matching the addressed-items list.
  Don't address it a second time on the same hypothesis. `header: "Review loop"`, options: **Try another
  angle** (continue with a different fix — the operator can name it in the free-text "Other"), **Accept +
  defer** (stop fixing it, file the item as a deferred follow-up), **Abort loop**.
- **Decision required.** The verdict flags an architectural choice, an API break, or a scope-change
  tradeoff. Don't guess. `header: "Decision"`, with one option per candidate path the reviewer named, each
  `description` carrying the reviewer's framing for that path.
- **Verification failure.** The retry ladder ran 3 times and the gate is still red. `header: "Tests red"`,
  options: **Push with reds** / **Defer the tests** / **Restructure**, per the retry-ladder Escalation
  section.
- **Grounding violation (in-scope), not addressable here.** A finding cites a diff that violates a
  documented constraint the issue/epic kept in-scope, and the fix can't ship on this PR (an integration PR
  of already-merged code, or it needs a plan/story). Don't file it — this is a hard block.
  `header: "Grounding"`, with options generated from the routes available and **no** defer/ship option (the
  violation must not reach the integration target): **Re-plan** (route to the planner to revise the plan —
  for an epic the planner scopes the missing in-scope work as a story) and **Abort**. Each `description`
  carries the violated doc citation and the in-scope evidence.

The outer iteration cap is not a fix-round gate: S5.1 tracks iterations and asks.
