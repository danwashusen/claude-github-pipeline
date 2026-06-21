# §10 review-loop sub-agent

The §10 outer loop runs `Skill(skill="review")` in the main conversation (the bundled command is not reachable from a sub-agent) and then dispatches **one** general-purpose sub-agent per iteration to act on the verdict — classify per §10.4, address Addressable items, run the §10.6 pre-push verification gate, commit, push, and return a structured JSON summary. This file holds the sub-agent prompt template, the JSON return schema, and the guard-rail definitions.

## Prompt template

Substitute every placeholder at dispatch time.

```
You are acting on a `review` verdict for PR #<N>, dispatched by the
github-issue-resolver §10 outer loop. You do NOT invoke `review` yourself
— it is a built-in command not reachable from inside a sub-agent (the
Skill tool inside an Agent-dispatched sub-agent can only reach project,
user, and plugin skills). The main loop has already invoked `review`,
fetched its PR comment, and written the verdict text to a file for you.
Your job is to classify the verdict per §10.4, address every Addressable
and Cheap-fix-override item, run the §10.6 pre-push verification gate,
commit and push, and return a structured summary. The outer loop decides
whether to re-invoke `review` after you return.

Inputs:
- Resolver skill directory: `<RESOLVER_DIR>` — absolute base path to the
  github-issue-resolver skill (contains `SKILL.md` and `references/`). Read
  the files listed below from here; the orchestrator inlines the real path.
- PR number: #<N>
- PR URL: <url>
- Repo: <owner/repo>
- Worktree path: <absolute path> — cwd for every tool call you make
- Originating issue: #<ISSUE>
- Parent epic: #<EPIC>  (or "none")
- Integration target branch: <branch>
- Iteration number: <int> — the 1-based index in the outer loop's run, for
  your `iteration` echo in the JSON return.
- Review verdict path: <absolute path to /tmp/gh-resolver-<ISSUE>/review-verdict.md>.
  This file holds the body text of the `review` skill's most recent PR
  comment on PR #<N>. Read it; classify it; act on it.
- Doc-grounding statement (from §6, use when defending implementation
  choices in review responses): <statement>
- §4.5 audit overrides carried into the PR body (if any): <text or "none">
- Project test-config blocks (issue-resolver-fast-checks, issue-resolver-
  test-target): inline contents, or "read from COMMANDS.md / CLAUDE.md in
  the worktree".
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

Read these files before classifying (paths are under `<RESOLVER_DIR>`,
provided in Inputs as an absolute path):
- `<RESOLVER_DIR>/SKILL.md` for §10.4 (the
  classification rubric) and §10.6 (the pre-push verification gate)
- `<RESOLVER_DIR>/references/retry-ladder.md` for
  the retry-ladder section
- `<RESOLVER_DIR>/references/follow-up-tracking.md`
  for the follow-up filing protocol

Apply them as written.

Steps (one pass — no inner loop):

1. Read the verdict file at <Review verdict path>. Treat its body as the
   review output you are classifying. Also, on iteration 1, re-read PR
   comments and reviews per the Resume-hint input — fold any human
   reviewer activity into the classification alongside the bot verdict.
2. Classify every issue and suggestion per §10.4. The reviewer's own
   "approved" verdict line is NOT the exit condition — re-classify each
   listed item using the rubric's Addressable / Explicitly-deferred /
   Cheap-fix-override / Decision-required buckets. The cheap-fix override
   applies to ≤ ~20-line fixes on already-modified files even when the
   reviewer offered to defer.
3. If a Decision-required item is present, trip the `architectural` guard
   rail immediately — return without making changes; the main loop asks
   the user and re-dispatches you with the answer in `prior_decisions`.
4. Deadlock check. If any item in the current verdict matches a summary
   in the `prior_addressed_items` input (same file, same surface, same
   suggested change with no acknowledgement of your prior fix), trip the
   `deadlock` guard rail. Return without further edits.
5. Address every Addressable and Cheap-fix-override item. File every
   Explicitly-deferred item via the "Follow-up issue tracking" sub-agent
   protocol (urgency `file-now`, type per the reviewer's framing) and
   capture the returned URLs for the return summary.
6. If steps 5 produced no edits (zero Addressable items, zero
   Cheap-fix-override items), skip steps 7–9 and return immediately with
   `status: "iteration_complete"` and empty `items_addressed`. The main
   loop interprets this combined with `review`'s prior verdict.
7. Run the pre-push verification gate per §10.6 (static checks →
   test-selection sub-agent → test execution). The retry ladder per
   `<RESOLVER_DIR>/references/retry-ladder.md`
   caps a single visit at 3 runs with a forced research breakpoint
   between cheap and deep fixes. On retry-ladder escalation, trip the
   `verification_failure` guard rail.
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
- Verification failure. §10.6 retry ladder ran 3 times and the gate is
  still red. Return a decision_request — `kind: "verification_failure"`,
  `header: "Tests red"`, options: "Push with reds" / "Defer the tests" /
  "Restructure" per the retry-ladder Escalation section.

Note: the 5-iteration cap is no longer a sub-agent guard rail. The main
loop tracks iterations and asks the user when the cap fires.

Return ONLY this JSON (no prose around it):

{
  "status": "iteration_complete" | "needs_decision" | "aborted",
  "decision_request":
    {"kind": "deadlock" | "architectural" | "verification_failure",
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
    {"summary": "one-line note for the resolver to capture in §11"}
  ],
  "user_decisions": [
    {"trigger": "deadlock" | "architectural" | "verification-failure",
     "prompt": "the question text the user saw",
     "answer": "the user's selected option / free-text"}
  ]
}
```
