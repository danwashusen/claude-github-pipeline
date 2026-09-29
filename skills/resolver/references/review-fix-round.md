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
- **PR** number, URL, and `<owner/repo>` in continue mode — in fresh mode the PR does not exist until
  S5.2 and you hold the staged `<facts.scratch>/pr.md` instead; the originating issue and its parent epic (or none);
  `facts.audit_ref` (bare) as the integration target.
- **Workspace**: `facts.workspace.path` — the cwd for every command you run.
- **Iteration number** — the 1-based index in S5.1's outer loop, and the **previous round's defect
  count** (S5.1 step 3 compares this round's against it).
- **Loop-entry SHA** — HEAD recorded at S5.1 entry. `git diff --name-only <loop-entry sha>...HEAD` in the
  workspace is the set of files this loop's own fixes have changed — the **hot seam** step 4's fix-design
  trigger reads. It scopes that dispatch only — the progress rule's **loop-induced** test reads the
  defect-fix commits on the addressed-items list instead, since a file-level set turns hot on a mere
  polish rename; it is not provenance tagging and never gates the cold read (4.11.0 removed that
  machinery deliberately).
- **The addressed-items list** — one-line summaries of what you fixed in every prior round this run,
  each round's entries carrying that round's **commit SHA** and whether it **fixed a defect**. You
  append to it in step 9; the deadlock check in step 3 reads it, and so does the rubric's
  **loop-induced** test.
- **The refuted-items list** — one line per Plan-settled / Deferred-by-plan / Refuted item with its
  citation or evidence, from
  every prior round this run and (seeded on iteration 1, below) from earlier phases' rounds. Appended in
  step 9; the deadlock check reads it too, and treats a match differently from an addressed match.
- **The plan and the phase list** — the verified plan comment (`facts.plan.url`; its body is the
  `marker_comment_*` entry of `facts.sections`) and `facts.phases`, with the current phase's number
  (the S4 cursor) and its `depends-on`. The two settled buckets cite these.
- **The polish ledger** — `facts.polish` ([`../../_shared/polish-ledger.md`](../../_shared/polish-ledger.md)).
  Every entry the evaluator marked `apply` is Addressable on iteration 1 whatever its tier — it has
  been decided; recording it as `open` again would bounce the PR between the two skills.
- **Doc-grounding statement** (from S3) and any audit / plan overrides carried into the PR body — use them
  when defending an implementation choice in a PR reply.
- **Test config**: `facts.config.static_checks` and `facts.config.test_target_raw`.
- **References**: [`retry-ladder.md`](retry-ladder.md) (the pre-push gate's 3-run cap + research
  breakpoint), [`follow-up-tracking.md`](follow-up-tracking.md) (the follow-up registry and its timing),
  and [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md) for the drafter-proxy filing
  protocol. Apply them as written.
- **Resume hint** — this loop may be picking up mid-flow (a prior resolver run was interrupted, or a human
  reviewer commented between invocations). On **iteration 1 only**, when a PR exists, before classifying, re-read the
  accumulated PR comments and reviews (`gh pr view --comments`, plus the `pulls/<N>/reviews` and
  `pulls/<N>/comments` REST endpoints via `gh api`) and treat any reviewer comment or review — the evaluator's soft-reject review included, though a
  pipeline-authored `COMMENTED` review carries no operator header — as additional Addressable input
  alongside the verdict. Seed the refuted-items list from every `Settled (not
  addressed):` block in prior round replies (step 8) — each phase is a fresh session, and that block is
  the only carrier of what earlier phases refuted — **except** a `deferred-by-plan` entry whose phase is
  the current phase or a ticked tracker row: its deferral has come due, and the finding classifies
  fresh. Note any `Cold read: phase <N> @ <sha>` line for the current phase and whether its `<sha>` is
  HEAD or an ancestor of it (S5.1 step 4 reads both).

## Classification rubric

Apply to every listed item:

- **Addressable** — a concretely-named change on already-modified files or the issue's scope. The DEFAULT
  for any concretely-named change. Soft politeness ("could be fast-follow", "not blocking", "future PR")
  does NOT by itself move an item out of Addressable.

Every Addressable item also gets a **tier**, recorded beside it in the round reply so the call can be
audited:

- **defect** — correctness, a broken contract or invariant, data loss or corruption, security, a test
  gap that would let a real bug through, or an unfinished `## Changes` entry of the phase being built
  (the plan requires it; the diff does not deliver it yet). Keeps the loop open (S5.1 step 3 counts
  these). **Tie-break:** when defect-vs-polish is unclear, tier it defect if the finding cites a plan
  decision or shows a test that could not fail, and record the doubt in the round reply — the likely
  mis-tiering is a test gap under-tiered as polish, which settles the loop early.
- **polish** — everything else: naming, structure, comments, a small refactor. Fix it **on merit** —
  cheap (no new spec file, no fix-design dispatch), on code this phase already touches, and clearly
  right rather than taste; otherwise leave it for the `## Polish` ledger, which the evaluator
  adjudicates. A refactor touching a guard, a raise, or any fail-closed path is never cheap — a
  polish refactor that dropped a non-nil assertion turned a raising path fail-open, unnoticed by
  review. **Always fix in-loop, never ledger**, polish matching the evaluator's `apply` criteria — a
  comment, doc or message that states something false; a misleading name on a public or cross-module
  surface; wrong user-visible copy — whatever it costs: parked, it only buys a revision session later.
  Polish never keeps the loop open. (This replaced the Cheap-fix-override bucket, which forced every
  ≤ ~20-line fix and fed an unbounded tail of polish rounds.)

A defect is **loop-induced** when its cited site falls inside `git diff <sha>^..<sha>` of an earlier
round's defect-fix commit (the addressed-items list carries both) — within the hunks its **defect**
fixes changed, since one round commit also carries that round's polish — or when it is the same change
at a sibling site of a class fix already addressed — that fix was incomplete. A file touched only by
polish or comment edits never makes a finding loop-induced. S5.1 step 3 reads this; nothing else does.
- **Explicitly-deferred** — routed elsewhere with a concrete tracking target (filed as #M, depends on an
  un-landed sibling, a citable PRD/scope exclusion): file it as a follow-up.
- **Decision-required** — an architectural / API-break / scope-change tradeoff the reviewer named candidate
  paths for: render the `Decision` card.
- **Grounding-violation** — a diff that violates a documented constraint the issue/epic kept in-scope: if
  addressable here, fix it; else render the `Grounding` card. NEVER filed as a follow-up.
- **Plan-settled** — the finding contests a decision the plan records in `## Architecture decisions`,
  `## UI decisions`, or `## Deviations from project docs`, or repeats an item the refuted-items list
  already carries. Settled, not addressed: no edit, no follow-up; the PR reply quotes the decision bullet
  **verbatim** as the citation. No citation → the item is not plan-settled and stays in its default
  bucket — this bucket exists to stop re-litigation, never to dismiss a finding. A finding that
  *demonstrates* the decision is defective (a reproducible fault, a documented-constraint violation) is
  not plan-settled: it is Decision-required or Grounding-violation.
- **Refuted** — the finding is factually wrong or unreachable, shown by evidence you cite: a code read
  naming the guard or call site that makes it impossible, or a run or reproduction showing the claimed
  failure does not occur. Settled, not addressed: no edit, no follow-up; the PR reply carries the
  evidence. No evidence → not refuted, and the item stays in its default bucket. Disagreeing on taste is
  not refutation — that is polish.
- **Deferred-by-plan** — the finding names a seam, consumer, or wiring that a **later** phase in
  `facts.phases` ships (a phase after the current cursor). Settled: cite the phase number and title in
  the PR reply, file nothing — `Explicitly-deferred` files a follow-up, and an issue for work a planned
  phase already owns is a duplicate. A seam no phase ships is a gap, not deferred: it stays Addressable
  or Decision-required.

## Steps (one round — no inner loop)

1. **Classify** every issue and suggestion per the rubric, reading the plan and `facts.phases` for the two
   settled buckets. The reviewer's own "approved" verdict line is
   NOT the exit condition — re-classify each listed item, then tier every Addressable one. On iteration
   1, fold in the human PR activity from the resume hint and every `apply` entry in `facts.polish`.
2. **Gates before any edit.** A Decision-required item → render the `Decision` card now. A
   Grounding-violation item that is **not** addressable on this PR → render the `Grounding` card now. When
   a finding matches **both**, render `Grounding` — a hard block outranks a soft approval gate. Act on the
   answer within this round. (A Grounding-violation that *is* addressable was reclassified Addressable in
   step 1 and is fixed in step 4; it is never filed as a follow-up.)
3. **Deadlock check.** If any item in the current verdict matches a summary in the addressed-items list
   (same file, same surface, same suggested change with no acknowledgement of your prior fix), render the
   `Review loop` card. Don't address it a second time on the same hypothesis. The same change at a
   **sibling site** of a class fix you already made is not a match — the hypothesis held and the
   coverage fell short: fix it per the class discipline, and it counts as loop-induced. An item matching the
   **refuted-items list** is re-settled silently on its second occurrence: no card, no second reply,
   only the entry's repeat count bumped. On its **third** occurrence in one run render the `Review loop`
   card with the refutation standing in for the prior fix — the reviewer's persistence is evidence the
   citation may not answer it.
4. **Fix plan, then fix.** Before the first edit, list the intended change of every item you will fix
   (each defect-tier Addressable item, each evaluator `apply` item, and each polish item you fix on
   merit) as text in this conversation — not in the PR reply, not in a file (on a hot seam, the
   fix-design dispatch below comes first and supplies those items' lines); one line per item:
   `<item> — <file>:<function> — siblings: <the sites sharing the concept, the class per the first
   fix-discipline bullet> — interacts with: <other items this round: same file, same function, or a fix
   that alters another's premise> — plan: <any `## Architecture decisions` / `## UI decisions` /
   `## Deviations from project docs` bullet it touches, or none>`. Then check the list as a set, and only
   then edit:
   - Two fixes that cannot both hold → one change that satisfies both, or name which premise wins and
     drop the other from this round's edits (it stays listed; the PR reply says why).
   - A fix that reverses a plan decision → that item is not a fix: reclassify it Decision-required and
     render step 2's `Decision` card now, before any edit, its paths the decision as it stands (the item
     settles Plan-settled, citing it) and **Re-plan**.
   An empty list (nothing to fix) needs no plan — step 5 owns that round.

   **Fix design on a hot seam.** Before writing the fix plan, dispatch the fix-design `Explore`
   sub-agent per [`fix-design-prompt.md`](fix-design-prompt.md) when any Addressable or
   polish item you will fix names a file in the hot seam (Loop-entry SHA — a cold-read-fed round
   included); dispatch it after writing the plan when the set check finds two fixes that cannot both
   hold or one that alters another's premise. At most once per round. Stage the scope diff to
   `<facts.scratch>/fix-design-diff.patch` (`git diff <base>...HEAD` in the workspace, `<base>` per
   S5.1's scope rule) and fill `<<loop_files>>` with the hot-seam file list, `<<findings>>` with those
   items verbatim, `<<addressed_items>>` with the addressed-items list's surfaces only (no reasoning),
   `<<plan_decisions>>` with the plan's decision bullets, and `<<phase_context>>` as for the cold read.
   Print its `## Seam` and `## Change set`, then adopt the change set as the plan lines for those items
   (main's own lines stand for the rest, and the set check runs over the union); a `## Plan conflicts`
   entry is Decision-required — render step 2's `Decision` card, as for a fix that reverses a plan
   decision; an `## Out of reach` entry keeps
   your own plan line. `code: AMBIGUOUS` → repair the staging and re-dispatch once, else proceed on your
   own plan and say so. The sub-agent designs; you edit. It exists because a loop's own fixes kept
   creating findings on the seam they touched: each changed a guard, and nobody re-derived the sibling
   properties sharing it.

   Then fix every item the check left standing, applying `common-pitfalls.md`'s three fix-discipline
   bullets to each fix *before* writing it — "Don't fix the instance when the finding names a class",
   "Don't conform code to a stated invariant a finding contradicts", "Don't split an atomic call without
   naming its implicit properties". A retro found fix rounds carrying several times the defect density of
   the code they corrected, and a later run had three of eleven findings introduced by the loop's own
   fixes: the disciplines catch defects inside one fix, the fix plan catches the ones between fixes, and
   the fix design catches the ones between a fix and the seam it lands in. File
   every Explicitly-deferred item via the follow-up filing protocol — related items as one group
   (urgency `file-now`, type per the reviewer's framing) — and capture the returned URLs. Never file a Grounding-violation item.
5. **No edits** (no defect, no `apply` item, no polish fixed on merit — every item Explicitly-deferred,
   settled, or polish left for the ledger) → this round is complete. Skip steps 6–7 and step 8's commit; stage step 8's reply
   only when this round settled a **new** item or was fed by the cold read (the `Settled (not
   addressed):` block and/or the `Cold read:` line alone). Then step 9,
   then back to S5.1 step 3, whose zero-defect branch settles the loop — whether or not the
   verdict's own line said approved.
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
   (`git rev-parse HEAD` in the workspace): your commits wait for step 8, so HEAD is still the last committed,
   gate-verified state and your fixes are working-tree-only — the override scopes selection to what this
   round actually changed. Scope rationale and its accepted gap: `retry-ladder.md`'s "§10.6 selection
   scope". The retry ladder caps a single visit at 3 runs with a forced research breakpoint between cheap
   and deep fixes. On escalation, render the `Tests red` card.
8. **Commit. Stage the reply** — append this round's section to `<facts.scratch>/loop-comment.md`,
   briefly describing what changed in response to which points of feedback, each item carrying its
   tier and the round's defect count on its own line (the stall card's evidence). Hold every polish
   item this round left unfixed for S5.2's `## Polish` ledger write, and every `apply` item it fixed
   for its `applied (commit <sha>)` update. Nothing is pushed or posted
   here: S5.2 pushes once and posts the whole file as the loop comment, because every per-round push
   started CI on code the next round was about to change. That comment is the GitHub-side record — how
   a reviewer, and the next session, follows what this loop did without replaying the conversation. When the round settled anything new,
   the reply ends with this fixed block — the next session's resume re-read seeds its refuted-items list
   from it (each phase is a fresh session; this comment is the only carrier):

   ```
   Settled (not addressed):
   - plan-settled — <one-line item> — cites: <section> "<decision bullet, verbatim>" (×<repeats>)
   - deferred-by-plan — <one-line item> — phase <N> "<title>" (×<repeats>)
   - refuted — <one-line item> — evidence: <what was read or run> (×<repeats>)
   ```

   `(×<repeats>)` is omitted on a first occurrence; carrying it is what lets the count survive a phase
   boundary.

   A round fed by the cold read (S5.1 step 4) also carries the `Cold read: phase <N> @ <sha>` line. A
   round that dispatched the fix design names the seam it re-derived in one line, so a reviewer sees why a
   fix reached past the finding's own site.
9. **Record.** Append this round's one-line item summaries to the addressed-items list, with the
   round's commit SHA and whether it fixed a defect, and its settled items, with citations or
   evidence, to the refuted-items list; keep its defect count for the next round's comparison. Hold the filed
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
further gate, and hand back to S5.2 (it pushes what is committed) and then the routed playbook's
handoff, quoting the trigger in the `Why:`.
Don't try to satisfy a re-route inside the round; there is nothing here that can.

- **Same-feedback-twice deadlock.** The current verdict flags an item matching the addressed-items list.
  Don't address it a second time on the same hypothesis. `header: "Review loop"`, options: **Try another
  angle** (continue with a different fix — the operator can name it in the free-text "Other"), **Accept +
  defer** (stop fixing it, file the item as a deferred follow-up), **Abort loop**.
- **Decision required.** The verdict flags an architectural choice, an API break, or a scope-change
  tradeoff. Don't guess. `header: "Decision"`, with one option per candidate path the reviewer named, each
  `description` carrying the reviewer's framing for that path — or, when step 4's fix plan raised it, the
  plan decision as it stands and **Re-plan**.
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

The stall card and the emergency ceiling are not fix-round gates: S5.1 tracks the defect counts and
asks.
