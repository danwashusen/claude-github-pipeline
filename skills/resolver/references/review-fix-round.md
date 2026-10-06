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
  polish rename; it is not the retired provenance tagging and never gates the cold read (4.11.0 removed
  that machinery deliberately — the rubric's provenance axis decides fix-or-defer, nothing about the cold
  read).
- **The addressed-items list** — one-line summaries of what you fixed in every prior round this run,
  plus the **defect-fix record**: each round's `Defect fixes:` line (step 8) — its commit SHA and the
  `<path>:<symbol>` site of every **defect** it fixed. The record also carries a prior session's lines on
  this phase, seeded by the resume hint, so a re-entered phase keeps its history. You append to it in
  step 9; the deadlock check in step 3 reads it, and so does the rubric's **loop-induced** test.
- **The refuted-items list** — one line per Plan-settled / Deferred-by-plan / Refuted item with its
  citation or evidence, from every prior round this run and (seeded on iteration 1 — "Resume hint") from
  earlier phases' rounds. Appended in step 9; the deadlock check reads it too, and treats a match
  differently from an addressed match.
- **The plan and the phase list** — the verified plan comment (`facts.plan.url`; its body is the
  `marker_comment_*` entry of `facts.sections`) and `facts.phases`, with the current phase's number
  (the S4 cursor) and its `depends-on`. The plan-anchored settled buckets cite these.
- **The polish ledger** — `facts.polish` ([`../../_shared/polish-ledger.md`](../../_shared/polish-ledger.md)).
  Every entry marked `apply` is Addressable on iteration 1 whatever its tier — it is the operator's
  answer, recorded by the evaluator or at [`finalisation.md`](finalisation.md), so it has been decided;
  recording it as `open` again would bounce the PR between the two skills.
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
  addressed):` block in prior round replies (step 8) — each phase starts fresh (a new session, or an
  in-session continuation after a fresh prep — `phase-continuation.md`), and that block is the only
  carrier of what earlier phases refuted — **except** a `deferred-by-plan` entry whose phase is the
  current phase or a ticked tracker row: its deferral has come due, and the finding classifies
  fresh. Seed the defect-fix record from every `Defect fixes: phase <N>` line for the current phase. Note
  any `Cold read: phase <N> @ <sha>` line for the current phase and whether its `<sha>` is
  HEAD or an ancestor of it (S5.1 step 4 reads both).

## Classification rubric

Classify every listed item on three axes, in order: its **provenance**, its **bucket**, and — for an
Addressable item — its **tier**. Provenance comes first because it predicts the right call best: an
audit of one repo's review-loop follow-ups found the findings a PR introduced the ones most often
wrongly deferred (fixable in the PR, or a plan gap), and the ones it did not introduce correctly deferred
four times in five. Record provenance and tier beside each item in the round reply, so the call can be
audited.

**Provenance** — whose problem it is:

- **introduced** — the finding's site is in lines this PR adds or changes, or this PR's change is what
  makes it reachable or untrue: a path the PR opens, a comment or doc its change made false, a test or
  control it wrote that cannot fail.
- **adjacent** — not in this PR's lines, but the same change this PR made applies at a **sibling site** —
  the same invariant, guard, helper, contract row or ruling, in the same file or seam — or it is a
  one-site correction to a file or doc this PR already edits.
- **pre-existing** — neither: found while reading code this PR does not change.

**Buckets:**

- **Addressable** — a concretely-named change that is **introduced** or **adjacent**, or within the
  plan's `## Changes` / phase `ships` or the issue's Definition of done — the same scope test fix
  design applies (`fix-design-prompt.md` step 5), so the two never disagree. The DEFAULT for any
  concretely-named change with that provenance. Soft politeness ("could be fast-follow", "not blocking",
  "future PR") does NOT by itself move an item out of Addressable. A **pre-existing** item is never
  Addressable: it takes the **Pre-existing** bucket.

  Every Addressable item also gets a **tier**:

  - **defect** — correctness, a broken contract or invariant, data loss or corruption, security, a test
    gap that would let a real bug through (a test or control this PR wrote that cannot fail included), or
    an unfinished `## Changes` entry of the phase being built (the plan requires it; the diff does not
    deliver it yet). Keeps the loop open (S5.1 step 3 counts these). **Tie-break:** when defect-vs-polish
    is unclear, tier it defect if the finding cites a plan decision or shows a test that could not fail,
    and record the doubt in the round reply — the likely mis-tiering is a test gap under-tiered as polish,
    which settles the loop early. An **introduced** defect is fixed in this PR: it leaves only through an
    operator answer — a `Decision` card's **Re-plan**, **Accept + defer** on the `Review loop` card,
    **Accept current** on the stall card — never through a filing of your own, and the follow-up it
    becomes states why it was not fixed.
  - **polish** — everything else: naming, structure, comments, a small refactor. On **introduced** or
    **adjacent** code, fix it this round — Fix it **on merit**, where the merit is the polish being right,
    not cheap: a follow-up costs an issue, a plan and a session, more than the edit, and the audit found
    polish parked for its cost should have been fixed more often than not. Size alone never parks it.
    Five exceptions:
    - it needs a decision the plan does not make → **Decision-required**;
    - it is a refactor touching a guard, a raise, or any fail-closed path, which is not fixed as polish
      — a polish refactor that dropped a non-nil assertion turned a raising path fail-open, unnoticed by
      review — so record it for the ledger;
    - it reaches beyond this PR's seam (an extraction across modules, a convention changed in files this
      PR does not touch) → record it for the ledger;
    - it is a doc the repo routes through a named command or process this session may not run → the
      **docs lane** (Explicitly-deferred);
    - it is taste — two reasonable forms, and the reviewer prefers the other → record it for the ledger
      with the note `no shown cost: taste`.

    **Always fix in-loop, never ledger**, polish matching the evaluator's `apply` criteria
    ([`../../_shared/polish-ledger.md`](../../_shared/polish-ledger.md) "Apply criteria"), whatever it
    costs: parked, it only buys a revision session later. Polish never keeps the loop open. (This
    replaced the Cheap-fix-override bucket, which forced every ≤ ~20-line fix and fed an unbounded tail
    of polish rounds — and then a cost gate, which parked the PR's own small fixes as follow-ups.)
    "Record it for the ledger" means hold it for S5.2's `## Polish` write (step 8); the final pass's
    finalisation puts it to the operator ([`finalisation.md`](finalisation.md)) and the evaluator
    backstops.

  A defect is **loop-induced** when its cited site is a `<path>:<symbol>` an earlier round's defect fix
  changed — a site in the defect-fix record, this session's or a prior session's on this phase — or when
  it is the same change at a sibling site of a class fix already addressed (that fix was incomplete). The
  record names defect-fix sites only, because one round commit also carries that round's polish. A file
  touched only by polish or comment edits never makes a finding loop-induced. S5.1 step 3 reads this;
  nothing else does.

- **Pre-existing** — what the reviewer found in code this PR does not change:
  - a defect or latent risk → **Explicitly-deferred**. A **security or privacy** defect (exposed personal
    data, an authorisation gap, a secret in a log) is its own follow-up group, never grouped with
    lower-severity items, and leads the handoff's "Follow-ups filed" bullet. When its fix is one site in a
    file this PR edits, it is **adjacent**: fix it.
  - polish → record it for the ledger, unfixed; finalisation puts it to the operator.
- **No shown cost** — a claim with no reachable path or demonstrated cost: a speculative performance or
  memoisation win, a bypass with no instance, hardening code the plan is removing, a dev-only tool with no
  failure. Record it for the ledger with the note `no shown cost: <why>`, which finalisation proposes as
  `drop`; never file it. It is not Refuted: Refuted needs evidence the claim is false, and this one may be
  true and still not worth doing.
- **Explicitly-deferred** — routed elsewhere with a concrete tracking target (filed as #M, depends on an
  un-landed sibling, a citable PRD/scope exclusion). Record it in the follow-up registry for the
  end-of-loop checkpoint ([`follow-up-tracking.md`](follow-up-tracking.md)) — filed mid-round only when
  this round's commit needs its number. Four rules before it is recorded:
  - **Verify the owner.** A target named as "owned by #M" or "a later story" must carry the item: read its
    body or Definition of done. When it doesn't, the item is a gap — Addressable when introduced or
    adjacent, else Decision-required, **Re-plan** recommended.
  - **File the class, not the instance.** Items sharing a root cause are one entry naming the class and
    every known site. Before it files, search open issues for that root cause
    ([`follow-up-tracking.md`](follow-up-tracking.md) "Before filing"): a match is cited, never re-filed,
    and a site it does not name goes on it as one comment.
  - **Latent until X ships.** A risk that becomes live when a named issue X ships is recorded with X; once
    filed, X is marked blocked by it.
  - **The docs lane.** Drift in docs the repo routes through a named command or process is one entry per
    owning process per PR, one item per claim — never one issue per claim.
- **Decision-required** — an architectural / API-break / scope-change tradeoff the reviewer named candidate
  paths for: render the `Decision` card. For an **introduced** item the card offers no deferral path, and
  **Re-plan** is recommended when the plan leaves the behaviour open: a follow-up for a PR's own unfinished
  design ships the gap (in the audit, 32 of 49 deferred introduced defects left as "needs a design
  decision", and 25 of those were plan gaps).
- **Grounding-violation** — a diff that violates a documented constraint the issue/epic kept in-scope: if
  addressable here, fix it; else render the `Grounding` card. NEVER filed as a follow-up.
- **Plan-settled** — the finding contests a decision the plan records in `## Architecture decisions`,
  `## UI decisions`, or `## Deviations from project docs`. (A verbatim repeat of a refuted-items entry
  keeps the bucket that entry records — step 3 — so a repeated Refuted item stays Refuted.) Settled, not
  addressed: no edit, no follow-up; the PR reply quotes
  the decision bullet **verbatim** as the citation. No citation → the item is not plan-settled and stays
  in its default bucket — this bucket exists to stop re-litigation, never to dismiss a finding. A finding
  that *demonstrates* the decision is defective (a reproducible fault, a documented-constraint violation)
  is not plan-settled: it is Decision-required or Grounding-violation.

  **The still-true test** decides "contests". Imagine the fix done and re-read each decision bullet the
  finding touches, as written. **Now false** → the finding contests it: the fix reverses a choice the plan
  made, redefines a term the plan defines, or moves work the plan puts elsewhere. **Still true** → it does
  not, and the item is Addressable (a defect when it is correctness) — it adds a case the plan never
  named, and fixing it stays inside the plan. A list of **required behaviour** ("must refuse …", "checks
  …") is a **minimum**: a refusal it did not name leaves it true, unless the plan says "only" / "exactly"
  or records the omission as a choice. A **definition** ("X means …") is not: adding a case to what X
  means makes it false. So a "must refuse" list gaining a refusal is not settled; an "unanswered means …"
  definition gaining a case is; work "owned by #M" done here is. Settling a still-true finding hides a
  defect behind the plan it was meant to complete.

  **A plan defect is not settled.** Run the test the other way too: applied as written, does the decision
  produce the wrong behaviour the finding shows — a misleading message, a dead end, a double charge, lost
  input? Then the plan is wrong, not the finding: Decision-required, **Re-plan** recommended — never
  settled, never filed.
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

1. **Classify** every issue and suggestion per the rubric — provenance, bucket, then tier — reading the
   plan and `facts.phases` for the plan-anchored settled buckets. The reviewer's own "approved" verdict
   line is NOT the exit condition — re-classify each listed item, then tier every Addressable one. On iteration
   1, fold in the human PR activity from the resume hint and every `apply` entry in `facts.polish`.
2. **Gates before any edit.** A Decision-required item → render the `Decision` card now. A
   Grounding-violation item that is **not** addressable on this PR → render the `Grounding` card now. When
   a finding matches **both**, render `Grounding` — a hard block outranks a soft approval gate. Act on the
   answer within this round. (A Grounding-violation that *is* addressable was reclassified Addressable in
   step 1 and is fixed in step 4; it is never filed as a follow-up.)
3. **Deadlock check.** If any item in the current verdict matches a summary in the addressed-items list
   (same file, same surface, same suggested change with no acknowledgement of your prior fix), render the
   `Review loop` card. Don't address it a second time on the same hypothesis. The same change at a
   **sibling site** of a class fix you already made is not a match — the hypothesis held and the coverage
   fell short: fix it per the class discipline, and it counts as loop-induced. The `Review loop` card is
   for these addressed-item deadlocks only. An item matching the **refuted-items list** verbatim — the
   same claim, carrying no reproduction, instance, or case the settled entry did not answer — is
   re-settled silently on its second occurrence: no card, no second reply, only the entry's repeat count
   bumped — in the bucket the entry records, never re-bucketed. An entry marked `kept` (the operator
   answered **Keep settled**, this session or an earlier one) is re-settled silently on **every**
   verbatim occurrence: that question is answered. A repeat that **brings new evidence** is classified
   fresh on the merits — a `kept` one included, its mark dropped: the prior settlement, and the
   operator's answer to it, are not a citation for evidence they never saw. A **recurrence that stays
   settled** — the third occurrence in one run, or a fresh classification that lands on Plan-settled
   again — bumps the count and takes step 4's **settled-item pre-check** this same round (never waiting
   for another occurrence, so a reviewer widening the finding cannot cycle it), then the `Settled item`
   card only if that check leaves it standing — the reviewer's persistence is evidence the citation may
   not answer it. An item already recorded for the ledger — held this pass, or on the PR's `## Polish`
   ledger — is not recorded again.
4. **Fix plan, then fix.** Before the first edit, list the intended change of every item you will fix
   (each defect-tier Addressable item, each `apply` item — built to its note's `intent:` when
   it carries one — and each polish item the polish rule fixes) as text in this conversation — not in the
   PR reply, not in a file (on a hot seam, the fix-design dispatch — "Fix design on a hot seam" — comes
   first and supplies those items' lines); one line per item:
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

   **Fix design on a hot seam.** Before writing the fix plan, dispatch the fix-design `Explore` sub-agent
   per [`fix-design-prompt.md`](fix-design-prompt.md) when any Addressable or polish item you will fix
   names a file in the hot seam (Loop-entry SHA — a cold-read-fed round included); dispatch it after
   writing the plan when the set check finds two fixes that cannot both hold or one that alters another's
   premise. At most once per round — except that a round whose dispatch the settled-item pre-check forced
   before the plan may dispatch once more when its set check then fails, so the pre-check never spends
   the set check's design. Stage the scope diff to `<facts.scratch>/fix-design-diff.patch` (`git diff
   <base>...HEAD` in the workspace, `<base>` per S5.1's scope rule) and fill `<<loop_files>>` with the
   hot-seam file list, `<<findings>>` with those items verbatim, `<<addressed_items>>` with the
   addressed-items list's surfaces only (no reasoning), `<<plan_decisions>>` with the plan's decision
   bullets, `<<phase_context>>` as for the cold read, and the scope from `facts.distiller_bundle`:
   `<<plan_path>>` ← `plan_marker_path`, `<<plan_shipped_path>>` ← `plan_shipped_path` (or `(absent)`),
   `<<issue_body_path>>` ← `issue_body_path`. Print its `## Seam` and `## Change set`, then adopt the
   change set as the plan lines for those items (main's own lines stand for the rest, and the set check
   runs over the union); a `## Plan conflicts` entry is Decision-required — render step 2's `Decision`
   card, as for a fix that reverses a plan decision; a `## Needs a plan decision` entry is
   Decision-required too, never adopted as a fix — the `Decision` card with its candidate designs as
   options plus **Re-plan** and, when the entry is **out of scope** (outside the diff, the plan, and the
   Definition of done), **File as follow-up**, recommended (scope creep is follow-up work —
   Explicitly-deferred, filed grouped; a re-plan would widen the issue); when the plan leaves the
   **intent open**, **Re-plan** is recommended. An `## Out of reach` entry (it could not read far enough)
   keeps your own plan line. `code: AMBIGUOUS` → repair the staging and re-dispatch once, else proceed on
   your own plan and say so. The sub-agent designs; you edit. It exists because a loop's own fixes kept
   creating findings on the seam they touched: each changed a guard, and nobody re-derived the sibling
   properties sharing it.

   **Settled-item pre-check** (step 3's recurring settled item), by the bucket it stands in. A
   **Plan-settled** item joins this round's fix-design dispatch — dispatch one when the round had none,
   still at most once per round — as a finding to design. Its `## Change set` has an entry and `## Plan
   conflicts` does not name it → it was never settled: reclassify it Addressable, tier it, and fix it
   this round with **no card**, the round reply noting "recurring settled item re-examined: fix design
   found no plan conflict". Named in `## Plan conflicts`, or in `## Needs a plan decision` with an open
   intent → the `Settled item` card, **Re-plan** recommended; in `## Needs a plan decision` as out of
   scope → the card, **Keep settled** recommended (the plan put that work elsewhere). Named in `## Out of
   reach` → the card, **Fix it here** recommended (it could not read far enough — the design failed, not
   the plan). A recurring **Deferred-by-plan** item skips the dispatch — a later phase already owns that
   seam, so the plan has placed the work and there is no design to decide: re-check its phase citation —
   no unshipped later phase ships it any more → classify fresh (a gap: Addressable or Decision-required);
   still owned → the card, **Keep settled** recommended. A recurring **Refuted** item skips the dispatch
   too: re-check its cited evidence — gone → classify fresh; still holds → the card, **Keep settled**
   recommended.

   Then fix every item the check left standing, applying `common-pitfalls.md`'s three fix-discipline
   bullets to each fix *before* writing it — "Don't fix the instance when the finding names a class",
   "Don't conform code to a stated invariant a finding contradicts", "Don't split an atomic call without
   naming its implicit properties". A retro found fix rounds carrying several times the defect density of
   the code they corrected, and a later run had three of eleven findings introduced by the loop's own
   fixes: the disciplines catch defects inside one fix, the fix plan catches the ones between fixes, and
   the fix design catches the ones between a fix and the seam it lands in. Record every Explicitly-deferred
   item in the follow-up registry per the rubric's four rules — urgency `file-at-checkpoint`, type per the
   reviewer's framing; `file-now` only when this round's commit needs its number (a `// TODO(#NNN)`
   marker, a skip annotation), filed via the follow-up filing protocol with its URL captured. Never file a
   Grounding-violation item.
5. **No edits** (no defect, no `apply` item, no polish fixed — every item Explicitly-deferred, settled,
   or recorded for the ledger) → this round is complete. Skip steps 6–7 and step 8's commit; stage step 8's reply
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
   provenance and tier and the round's defect count on its own line (the stall card's evidence). Hold
   every item this round recorded for the ledger — polish it did not fix, pre-existing polish, and
   no-shown-cost items with their note — for S5.2's `## Polish` ledger write, and every `apply` item it
   fixed for its `applied (commit <sha>)` update. Nothing is pushed or posted
   here: S5.2 pushes once and posts the whole file as the loop comment, because every per-round push
   started CI on code the next round was about to change. That comment is the GitHub-side record — how
   a reviewer, and the next session, follows what this loop did without replaying the conversation. When the round settled anything new,
   the reply ends with this fixed block — the next session's resume re-read seeds its refuted-items list
   from it (each phase starts fresh, in a new session or an in-session continuation; this comment is the
   only carrier):

   ```
   Settled (not addressed):
   - plan-settled — <one-line item> — cites: <section> "<decision bullet, verbatim>" (×<repeats>)
   - deferred-by-plan — <one-line item> — phase <N> "<title>" (×<repeats>)
   - refuted — <one-line item> — evidence: <what was read or run> (×<repeats>)
   ```

   `(×<repeats>)` is omitted on a first occurrence; carrying it is what lets the count survive a phase
   boundary. An entry the operator answered **Keep settled** on carries `kept` in the same parenthetical
   (`(×3, kept)`), so the next session's seed never asks the question again.

   A round that fixed a defect also carries one `Defect fixes: phase <N> @ <sha> — <path>:<symbol>;
   <path>:<symbol>` line: the round's commit and every defect fix's site, never a polish site. `<N>` is
   the phase number (in a revision run, the last code phase's — the ledger id rule), so the next
   session's resume re-read finds it.

   A round fed by the cold read (S5.1 step 4) also carries the `Cold read: phase <N> @ <sha>` line. A
   round that dispatched the fix design names the seam it re-derived in one line, so a reviewer sees why a
   fix reached past the finding's own site.
9. **Record.** Append this round's one-line item summaries to the addressed-items list, and its
   `Defect fixes:` line to the defect-fix record, and its settled items, with citations or
   evidence, to the refuted-items list; keep its defect count for the next round's comparison. Hold the filed
   follow-up URLs for the PR body and the handoff. Carry any **procedural note** (something the next
   session should know that is not worth an issue) as a capture-not-file item per
   `follow-up-tracking.md` — it lands in the PR body or the handoff `Why:`, never as a filed issue.

## Guard rails — direct cards

Render each via `AskUserQuestion` per [`../../_shared/asking-the-user.md`](../../_shared/asking-the-user.md)
at the point it fires. An answer settles that gate for the phase — don't re-raise it on a later round.

Two kinds of answer, and the difference is load-bearing. A **continuing** answer (Try another angle,
Accept + defer, Fix it here, Keep settled, File as follow-up, Push with reds, Defer the tests, a named
architectural path)
is acted on inside this round, which then finishes normally. A **terminating** answer — **Re-plan** (from
the `Decision`, `Grounding` or `Settled item` card, or the stall card's churn option) and
**Restructure** (re-route to the planner), **Abort** and **Abort loop** — ends the round *and* S5.1 on
the spot, except "The Re-plan independent-defect pass": stop fixing, run no further gate, and hand
back to S5.2 (it pushes what is committed) and then the routed playbook's handoff, quoting the trigger in
the `Why:`. Don't try to satisfy a re-route inside the round; there is nothing here that can.

**The Re-plan independent-defect pass.** A Re-plan leaves the round's other defects behind, and some are
unrelated to what the re-plan will reshape — a run once handed the planner two such defects it could have
fixed. Before S5.2, fix each still-unfixed defect-tier item of this round that is **independent** of the
re-planned finding; both must hold:
- its fix site shares no `<path>:<symbol>` with the re-planned finding's site or the fix-design seam
  drawn for it — when no seam was drawn (a Re-plan from `Decision` or `Grounding`), sharing a **file**
  with the re-planned finding's site stands in for sharing its seam;
- its fix would be the same whichever way the re-plan goes — it neither reads nor changes what the
  re-planned decision governs.

When in doubt, it is **coupled**: fixing code the re-plan is about to reshape is wasted or conflicting.
Where the answer arrives decides what is left to do:
- **A `Decision` or `Grounding` card raised in step 2** (from the verdict, before any fix plan) → run
  **steps 4 and 6–8 for the independent subset**: fix plan with its set check, defect injection, the
  §10.6 gate, one commit.
- **A card raised in step 4** — the `Settled item` card, or a `Decision` card from fix design's
  `## Plan conflicts` / `## Needs a plan decision` or the fix plan's plan-reversal check (after this
  round's fix design and fix plan) → keep the existing plan lines for the independent subset and drop
  the rest — no second fix-design dispatch — then steps 6–8.
- **Stall card** (S5.1 step 3) → **no pass**: the round's fixes are already committed, and the churn that
  offered Re-plan says its defects are coupled to the loop's own sites.

Either way **no further `review`**: the next session's final-scope review re-reads them. A gate that
escalates past
the retry ladder → revert those fixes and record them, with no `Tests red` card. Coupled defects are
recorded in the round reply, the PR body, and the handoff `Why:`. **Restructure** (the gate is already
red) and **Abort** / **Abort loop** (the operator asked to stop) take no pass.

- **Same-feedback-twice deadlock.** The current verdict flags an item matching the addressed-items list.
  Don't address it a second time on the same hypothesis. `header: "Review loop"`, options: **Try another
  angle** (continue with a different fix — the operator can name it in the free-text "Other"), **Accept +
  defer** (stop fixing it, file the item as a deferred follow-up), **Abort loop**.
- **Settled item recurring.** Step 3's recurring settled item that step 4's pre-check left standing.
  `header: "Settled item"`, options with the recommended one first (step 4 says which): **Re-plan**
  (terminating; offered only for a plan-anchored item — Plan-settled or Deferred-by-plan — since the
  question is whether the plan is wrong), **Fix it here** (reclassify Addressable, fix this round),
  **Keep settled** (recorded as `kept` on the entry, step 8 — never re-raised, this session or later).
  Each `description` quotes the
  settlement's citation or evidence and, when fix design ran, its conflict or out-of-reach entry. Never
  **Accept + defer**: a plan question is not a follow-up.
- **Decision required.** The verdict flags an architectural choice, an API break, or a scope-change
  tradeoff. Don't guess. `header: "Decision"`, with one option per candidate path the reviewer named, each
  `description` carrying the reviewer's framing for that path — or, when step 4's fix plan raised it, the
  plan decision as it stands and **Re-plan** — or, when fix design returned `## Needs a plan decision`,
  its candidate designs (each `description` naming the intent it serves) plus **Re-plan**, and
  **File as follow-up** for an out-of-scope entry, with step 4's recommendation first. For an
  **introduced** item no deferral path is offered — no **File as follow-up**, no reviewer-named "defer
  it" — and **Re-plan** is recommended when the plan leaves the behaviour open (the rubric's
  Decision-required bucket).
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
asks. Its **Accept current** description names each still-open defect with its provenance, introduced
ones first: an introduced defect leaving this PR as a follow-up is the operator's call, made with that
list in view.
