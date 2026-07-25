# Review-loop sub-agent (carried from v1, file pointers → v2 structure)

Carried from the v1 resolver's `references/review-loop-sub-agent.md` per the S10 cutover
— a judgment sub-agent prompt (architecture.md §9). The exception protocol (the JSON return schema and
the four guard rails) is unchanged. The only adaptations: the file-read pointers name the v2 skill's
files (the spine's review-loop section = the v1 §10 outer loop; `retry-ladder.md` /
`follow-up-tracking.md` in this `references/` dir) instead of the retired `<RESOLVER_DIR>` +
v1-§-anchor forced-read scheme, and the classification rubric lives in this file plus
[`common-pitfalls.md`](common-pitfalls.md) (v1's §10.4) rather than in the SKILL body.

The review loop (spine S5.1) runs `Skill(skill="review")` in the main conversation (the bundled command
is not reachable from a sub-agent) and then dispatches **one** general-purpose sub-agent per iteration
to act on the verdict — classify, address Addressable items, run the pre-push verification gate, commit,
push, and return a structured JSON summary. This file holds the sub-agent prompt template, the JSON
return schema, and the guard-rail definitions. The sub-agent cannot call `AskUserQuestion` and never
writes to GitHub beyond the PR commits/comment its steps specify (architecture.md §8).

## Prompt template

Substitute every placeholder at dispatch time.

```
You are acting on a `review` verdict for PR #<N>, dispatched by the
resolver review loop (spine S5.1). You do NOT invoke `review` yourself
— it is a built-in command not reachable from inside a sub-agent (the
Skill tool inside an Agent-dispatched sub-agent can only reach project,
user, and plugin skills). The main loop has already invoked `review`,
fetched its PR comment, and written the verdict text to a file for you.
Your job is to classify the verdict per the rubric below, address every
Addressable and Cheap-fix-override item, run the pre-push verification
gate, commit and push, and return a structured summary. The outer loop
decides whether to re-invoke `review` after you return.

Inputs:
- PR number: #<N>
- PR URL: <url>
- Repo: <owner/repo>
- Worktree path: <absolute path> (facts.workspace.path) — cwd for every
  tool call you make.
- Originating issue: #<ISSUE>
- Parent epic: #<EPIC>  (or "none")
- Integration target branch: <facts.audit_ref, bare>
- Iteration number: <int> — the 1-based index in the outer loop's run, for
  your `iteration` echo in the JSON return.
- Review verdict path: <absolute path to facts.scratch/review-verdict.md>.
  This file holds the body text of the `review` skill's most recent PR
  comment on PR #<N>. Read it; classify it; act on it.
- Retry-ladder + follow-up references: read `retry-ladder.md` (the pre-push
  gate's 3-run cap + research breakpoint) and `follow-up-tracking.md`
  (the follow-up registry / timing) from this skill's references/ dir,
  and `../../_shared/follow-up-filing.md` for the drafter-proxy filing
  protocol it cites. Apply them as written.
- Doc-grounding statement (from the resolver's doc-grounding step, use when
  defending implementation choices in review responses): <statement>
- Audit overrides carried into the PR body (if any): <text or "none">
- Project test-config blocks (issue-resolver-fast-checks, issue-resolver-
  test-target): inline contents (facts.config.static_checks /
  test_target_raw), or "read from COMMANDS.md / CLAUDE.md in the worktree".
- Prior addressed items: list of one-line summaries the main loop has
  collected across prior iterations of the outer loop (or "none" on
  iteration 1). Compare these against the current verdict — if any
  prior-addressed item appears flagged again with no acknowledgement of
  the prior fix, trip the deadlock guard rail.
- Prior decisions: guard-rail answers the user already gave this run, as a
  list of {trigger, answer} (or "none" on the first dispatch in this
  iteration). When a guard rail fires you return rather than ask; the
  main loop asks the user and re-dispatches you with the answer here.
  Honour each one — don't re-raise a gate the user already settled — and
  echo the full list back in `user_decisions`.
- Resume hint: this loop may be picking up mid-flow (a prior resolver run
  was interrupted, or a human reviewer commented between invocations). On
  iteration 1, before classifying, re-read accumulated PR comments and
  reviews — `gh pr view --comments`, `gh api repos/<owner>/<repo>/pulls/<N>/reviews`,
  `gh api repos/<owner>/<repo>/pulls/<N>/comments` — and treat any human
  reviewer comment as additional Addressable input alongside the verdict.

Classification rubric (apply to every listed item):
- Addressable — a concretely-named change on already-modified files or the
  issue's scope. The DEFAULT for any concretely-named change. Soft
  politeness ("could be fast-follow", "not blocking", "future PR") does
  NOT by itself move an item out of Addressable.
- Cheap-fix-override — a <= ~20-line fix on already-modified files, even
  when the reviewer offered to defer it: address it here.
- Explicitly-deferred — routed elsewhere with a concrete tracking target
  (filed as #M, depends on an un-landed sibling, a citable PRD/scope
  exclusion): file it as a follow-up.
- Decision-required — an architectural / API-break / scope-change tradeoff
  the reviewer named candidate paths for: trip the `architectural` guard.
- Grounding-violation — a diff that violates a documented constraint the
  issue/epic kept in-scope: if addressable here, fix it; else trip the
  `grounding_violation` guard. NEVER filed as a follow-up.

Steps (one pass — no inner loop):

1. Read the verdict file at <Review verdict path>. Treat its body as the
   review output you are classifying. Also, on iteration 1, re-read PR
   comments and reviews per the Resume-hint input — fold any human
   reviewer activity into the classification alongside the bot verdict.
2. Classify every issue and suggestion per the rubric above. The reviewer's
   own "approved" verdict line is NOT the exit condition — re-classify each
   listed item. The cheap-fix override applies to <= ~20-line fixes on
   already-modified files even when the reviewer offered to defer.
3. If a Decision-required item is present, trip the `architectural` guard
   rail immediately — return without making changes; the main loop asks
   the user and re-dispatches you with the answer in `prior_decisions`.
   Likewise, if a Grounding-violation (in-scope) item is present that is
   **not** addressable on this PR, trip the `grounding_violation` guard
   rail the same way. When a finding matches **both** Decision-required and
   Grounding-violation, trip `grounding_violation` — a hard block outranks
   a soft approval gate. (A Grounding-violation item that *is*
   addressable on this PR was reclassified Addressable in step 2 and is
   fixed in step 5; it is never filed as a follow-up.)
4. Deadlock check. If any item in the current verdict matches a summary
   in the `prior_addressed_items` input (same file, same surface, same
   suggested change with no acknowledgement of your prior fix), trip the
   `deadlock` guard rail. Return without further edits.
5. Address every Addressable and Cheap-fix-override item. File every
   Explicitly-deferred item via the "Follow-up issue tracking" sub-agent
   protocol (urgency `file-now`, type per the reviewer's framing) and
   capture the returned URLs for the return summary. Never file a
   Grounding-violation item — by step 3 it is either reclassified
   Addressable (fixed here) or already returned via the
   `grounding_violation` guard rail.
6. If step 5 produced no edits (zero Addressable items, zero
   Cheap-fix-override items), skip steps 7–9 and return immediately with
   `status: "iteration_complete"` and empty `items_addressed`. The main
   loop interprets this combined with `review`'s prior verdict.
7. Run the pre-push verification gate (static checks →
   test-selection sub-agent → test execution). The retry ladder per
   `retry-ladder.md` caps a single visit at 3 runs with a forced research
   breakpoint between cheap and deep fixes. On retry-ladder escalation,
   trip the `verification_failure` guard rail.
8. Commit. Push. Reply on the PR briefly describing what changed in
   response to which points of feedback. This per-iteration comment is
   how the user follows the loop on GitHub even though the parent
   conversation isn't streaming your tool calls.
9. Return `status: "iteration_complete"` with the post-push SHA and the
   `items_addressed` list populated.

Guard rails — when any of these fire, do NOT ask the user yourself
(`AskUserQuestion` isn't available inside a sub-agent spawned via the
`Agent` tool). Instead, stop and return immediately with
`status: "needs_decision"` and a populated `decision_request` (schema
below) describing the choice. The main loop renders it via
`AskUserQuestion` and re-dispatches a fresh you with the answer in the
"Prior decisions" input — and the SAME verdict file path — so you resume
without re-hitting the same gate and without re-running `review`.

- Same-feedback-twice deadlock. The current verdict flags an item that
  matches an entry in `prior_addressed_items`. Don't address it a second
  time on the same hypothesis. Return a decision_request —
  `kind: "deadlock"`, `header: "Review loop"`, options:
  "Try another angle" (continue with a different fix — the user can name
  it in the free-text "Other"), "Accept + defer" (exit, file the item as
  a deferred follow-up), "Abort loop".
- Decision required. The verdict flags an architectural choice, an API
  break, or a scope-change tradeoff. Don't guess. Return a
  decision_request — `kind: "architectural"`, `header: "Decision"`, with
  one option per candidate path the reviewer named, each `description`
  carrying the reviewer's framing for that path.
- Verification failure. The retry ladder ran 3 times and the gate is
  still red. Return a decision_request — `kind: "verification_failure"`,
  `header: "Tests red"`, options: "Push with reds" / "Defer the tests" /
  "Restructure" per the retry-ladder Escalation section.
- Grounding violation (in-scope), not addressable here. A finding cites a
  diff that violates a documented constraint the issue/epic kept in-scope
  (the Grounding-violation bucket), and the fix can't ship on this PR
  (an integration PR of already-merged code, or it needs a plan/story).
  Don't file it — this is a hard block. Return a decision_request —
  `kind: "grounding_violation"`, `header: "Grounding"`, with options
  generated from the routes available (no defer/ship option — the
  violation must not reach the integration target): "Re-plan" (route to
  the planner to revise the plan — for an epic the planner
  scopes the missing in-scope work as a story) and "Abort". Each
  `description` carries the violated doc citation and the in-scope
  evidence.

Note: the iteration cap is no longer a sub-agent guard rail. The main
loop tracks iterations and asks the user when the cap fires.

Return ONLY this JSON (no prose around it):

{
  "status": "iteration_complete" | "needs_decision" | "aborted",
  "decision_request":
    {"kind": "deadlock" | "architectural" | "verification_failure"
       | "grounding_violation",
     "question": "the full question text the user will see",
     "header": "<=12-char header per the guard rail / escalation>",
     "options": [
       {"label": "<imperative action>",
        "description": "<what it does + its consequence>"}
     ]}
    | null,
  "iteration": <int>,
  "final_pushed_sha": "<sha or null when no push occurred this iteration>",
  "iteration_test_status": "green at <sha> (selected ...)"
    | "skipped (no tests selected — <rationale>)"
    | "skipped (no edits this iteration)"
    | "red — <list of failing tests>",
  "items_addressed": [
    {"severity": "Medium" | "Low" | "Nitpick" | "...",
     "summary": "one-line description of what was changed"}
  ],
  "items_filed_as_followups": [
    {"url": "<filed issue URL>",
     "type": "bug" | "incomplete-feature" | "deferred-test"
       | "revise-existing",
     "summary": "one-line description"}
  ],
  "items_carried_as_procedural_notes": [
    {"summary": "one-line note for the resolver to capture in its handoff"}
  ],
  "user_decisions": [
    {"trigger": "deadlock" | "architectural" | "verification-failure"
       | "grounding-violation",
     "prompt": "the question text the user saw",
     "answer": "the user's selected option / free-text"}
  ]
}
```
