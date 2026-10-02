# Polish adjudication (spine S5.5)

The evaluator proposes, and the operator decides, what happens to the PR's `## Polish` ledger — the
polish findings the resolver's review loop recorded and did not fix. Format, dispositions and ownership live in
[`../../_shared/polish-ledger.md`](../../_shared/polish-ledger.md); this file is the evaluator's
procedure. It runs **after the S5 verdict and before S7's post timing**, because under an `auto` merge
policy an APPROVE posts and merges immediately — a ledger decided after that point could not stop the
merge.

Input: `facts.polish` (prep's scan of the PR body), plus `facts.plans` and `facts.dod` for the scope and
decision checks. Nothing to do when it is absent or carries no `open`, unfixed `apply`, or `file` entry.
A line in `facts.polish.unparsed` is rewritten into grammar by this step's write, keeping its text;
never silently dropped.

## 1. Re-check each entry at head and propose a disposition

First, every entry still marked `apply` — confirmed on an earlier run, but the revision run left it
unfixed (an **Accept current** on its stall card, an abort). Still present at head → propose `apply`
again and put it back in front of the operator at §2, marked `confirmed on a prior run, left unfixed`:
skipping it would silently drop the operator's decision, and forcing it with no card would leave no way
to release it once priorities change — the operator may re-apply, file it instead, or drop it. Gone
at head → `drop` with the note `resolved otherwise at <short-sha>`. Next, every `file` entry — decided on
an earlier run whose verdict sent the PR back, so still unfiled (filing runs only after the merge), and
the revision since may have fixed it: still true at head → keep it, not asked again; gone → `drop` with
`resolved otherwise at <short-sha>`, named in the review. Then the `open` entries:

Read the entry's anchor in the workspace (`facts.workspace.path`, at `pr.headRefOid`) and check the
entry's **claim**, not only that the anchor still exists — the reviewer wrote it against an earlier
diff, and a later phase may have made it false or narrower. False as written → propose `drop` with the
note `premise false at head — <why>`; true only in part → keep the item text and put what is actually
true at head in the note (`narrowed: <what holds>`), so a filed follow-up carries the corrected claim,
not the reviewer's. Then propose one of the following, with a one-line reason as the entry's note:

- **`apply`** — the polish would be **actively bad to merge**: it meets
  [`../../_shared/polish-ledger.md`](../../_shared/polish-ledger.md) "Apply criteria". This bucket is
  meant to be near-empty: the resolver fixes polish matching those criteria in-loop and never ledgers it
  (`review-fix-round.md` "Classification rubric"), so an
  `apply`-criteria entry here is a **resolver miss** — name it as one in the review body. A PR sent back
  for polish costs a whole resolver session; if most entries want `apply`, the resolver's defect/polish
  line is misplaced — say so rather than sending the PR round again and again.
- **re-plan** — the entry sits inside this PR's scope (the plan's `## Changes` / phase `ships` in
  `facts.plans`, or the issue's Definition of done in `facts.dod`) but its fix needs a decision the plan does not make:
  it would make a plan decision bullet **false as written** (reverses a choice, redefines a term the plan
  defines, moves work the plan places elsewhere — a list of required behaviour is a minimum, a
  definition is not), or the plan and the Definition of done leave the intended behaviour open, so two
  fixes fit, each serving a different intent. The note names the bullet, or the two intents. This is a
  proposal, not a disposition: the operator's **Re-plan** answer records `apply` and routes to the
  planner (§4).
- **`file`** — worth doing, not worth holding the merge for. Filed after the merge by the routed
  playbook's residual step, grouped per [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md)
  (polish groups file as `incomplete-feature`). An entry **outside** this PR's scope that also needs an
  intent decided files too — the note states the open question, so the follow-up's planner answers it
  rather than inheriting a guess.
- **`drop`** — taste rather than improvement, a premise false at head, or **no longer applies at head**
  (a later phase removed or rewrote the site). The note says which.

An entry that turns out to be a real defect is not polish: it is a dimension failure in S4 (soft-reject
on the evidence), and the entry is `drop`ped with the note `reclassified: defect — see review`.

## 2. Decide the ledger with the operator

The evaluator **proposes**; the operator decides **every** entry §1 proposed a disposition for — `file`
and `drop` included, on any verdict and under either merge policy, `auto` and epic-integration alike.
The ledger is where the resolver parked what it would not fix, so what happens to it is the operator's
call, not the evaluator's alone — asking only about `apply` left a ledger of `file` / `drop` entries as
one line of the approval question, with no way to re-plan an entry. Ask **before** the S7-gate
`Approve PR` card and before any S7-post, so the gate and the review see the final dispositions.

Group the entries: one group per proposed follow-up (the `file` grouping of
[`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md) — same type, same seam), one
group for each `apply` or re-plan seam, and one group for all the `drop` proposals. Ask one `Polish` card
(`header: "Polish"`) with one question per group — at most 4 questions per card; more groups ask a
second card after the first is answered. Each question lists the group's entries (id, item, the
evaluator's reason, and any `premise false` / `narrowed` correction) and offers four options, the
evaluator's proposal first and marked recommended:

- **File as follow-up**
- **Apply in this PR** — the resolver fixes it before the merge.
- **Re-plan** — the planner revises the plan for it before the resolver continues.
- **Drop**

A re-proposed `apply` says it was `confirmed on a prior run, left unfixed`. The tool's "Other" takes a
split answer by id ("file all but P1.3; re-plan P1.3"); apply it entry by entry.

Answers:

- **File as follow-up** → `file`, the note carrying `group: <the question's group label>` — the residual
  step files one issue per recorded group, as the operator approved it
  ([`../../_shared/polish-ledger.md`](../../_shared/polish-ledger.md) "Rules").
- **Drop** → `drop`.
- **Apply in this PR** → `apply`. On an entry proposed as re-plan because two intents fit, ask one
  follow-up question first — one option per intent the note names — and record the answer as
  `intent: <chosen>` in the note: the resolver implements that intent and never picks one itself.
- **Re-plan** → `apply`, the note prefixed `operator: re-plan —`, which forces the planner route at §4
  whatever its plan-change test says.

When an answer differs from the proposal, the note leads with `operator: <answer>` and keeps the
evaluator's reason after it. With no **Apply in this PR** or **Re-plan** answer, the verdict stands and
S7 proceeds — under `ask` to the `Approve PR` card, which does not carry the ledger. With one, an
APPROVE becomes COMMENT (§4). On a verdict that is **already** COMMENT — the evaluator's own soft-reject
(red health, a failed dimension, an S4-untick) — the answers decide only which items go back with the
PR: the review keeps the evaluator's header and the `COMMENT (soft-reject)` marker, and the route is the
verdict's own, except that a **Re-plan** answer routes to `planner revise` as an S4-untick does. This
card is the **only** limit on how often a PR goes back for polish — deliberately an operator decision,
not a counter; do not add one.

## 3. Write the dispositions once

After the last `Polish` card is answered, and before the review posts, rewrite the `## Polish` section
with the final dispositions — the ledger never records a decision the operator overrode. Stage the whole
PR body with the rewritten section to `<facts.scratch>/pr-body-polish.md` and apply it through the single
write path (`edit-pr-body` — the issue-body op `edit-body` rejects a PR number):

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py edit-pr-body <owner/repo> <PR> \
  "<facts.scratch>/pr-body-polish.md"
```

Entries are never deleted (`polish-ledger.md` "Rules").

## 4. A confirmed `apply` — the soft-reject and its route

The review body gains a `## Polish` section listing each `apply` entry by id with its reason. When the
polish answer is what turned an APPROVE into COMMENT, the body also takes the operator-attribution header
(`**Operator decision: Needs Revision**`, per `review-comment.md`) since the operator made the call; on an
already-COMMENT verdict it keeps the evaluator's own (§2). Post it as S7-post's `comment` and flip the PR back to draft exactly as a
COMMENT verdict does. The handoff's `review:` marker is `COMMENT (operator: needs-revision)` — or
`COMMENT (soft-reject)` on an already-COMMENT verdict.

Route by whether applying the items changes the plan — the same test the resolver's fix plan applies to
a fix that reverses a plan decision:

- **Changes the plan** — the operator answered **Re-plan** on any entry, or applying an item would
  reverse a `## Architecture decisions` / `## UI decisions` bullet, add or reshape a phase's scope, or
  cross an epic's `## Story contracts` → **`/github-pipeline:planner revise #<issue>`**. The planner sees
  the ledger (`facts.revise.open_pr.polish`) and absorbs the `apply` items as a new phase; the resolver
  then builds it in continue mode.
- **Otherwise** → **`/github-pipeline:resolver #<issue>`**. The resolver's revision run treats every
  `apply` entry as Addressable whatever its tier and marks it `applied (commit <sha>)` once fixed.
