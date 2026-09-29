# Polish adjudication (spine S5.5)

The evaluator decides what happens to the PR's `## Polish` ledger — the polish findings the resolver's
review loop recorded and did not fix. Format, dispositions and ownership live in
[`../../_shared/polish-ledger.md`](../../_shared/polish-ledger.md); this file is the evaluator's
procedure. It runs **after the S5 verdict and before S7's post timing**, because under an `auto` merge
policy an APPROVE posts and merges immediately — a ledger decided after that point could not stop the
merge.

Input: `facts.polish` (prep's scan of the PR body). Nothing to do when it is absent or carries neither an
`open` entry nor an unfixed `apply` entry. A line in `facts.polish.unparsed` is rewritten into grammar by this step's write, keeping its
text; never silently dropped.

## 1. Re-check each `open` entry at head

First, every entry still marked `apply` — confirmed on an earlier run, but the revision run left it
unfixed (an **Accept current** on its stall card, an abort). Still present at head → propose `apply`
again and put it back in front of the operator at §2, marked `confirmed on a prior run, left unfixed`:
skipping it would silently drop the operator's decision, and forcing it with no card would leave no way
to release it once priorities change — the operator may re-apply, file it instead, or merge anyway. Gone
at head → `drop` with the note `resolved otherwise at <short-sha>`. Then the `open` entries:

Read the entry's anchor in the workspace (`facts.workspace.path`, at `pr.headRefOid`) and propose one
disposition, with a one-line reason as the entry's note:

- **`apply`** — the polish would be **actively bad to merge**: it meets
  [`../../_shared/polish-ledger.md`](../../_shared/polish-ledger.md) "Apply criteria". This bucket is
  meant to be near-empty: the resolver fixes polish matching those criteria in-loop and never ledgers it
  (`review-fix-round.md` "Classification rubric"), so an
  `apply`-criteria entry here is a **resolver miss** — name it as one in the review body. A PR sent back
  for polish costs a whole resolver session; if most entries want `apply`, the resolver's defect/polish
  line is misplaced — say so rather than sending the PR round again and again.
- **`file`** — worth doing, not worth holding the merge for. Filed after the merge by the routed
  playbook's residual step, grouped per [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md)
  (polish groups file as `incomplete-feature`).
- **`drop`** — taste rather than improvement, or **no longer applies at head** (a later phase removed or
  rewrote the site). The note says which.

An entry that turns out to be a real defect is not polish: it is a dimension failure in S4 (soft-reject
on the evidence), and the entry is `drop`ped with the note `reclassified: defect — see review`.

## 2. Confirm an `apply` with the operator

**Every** proposed `apply` — on any verdict, a re-proposed one from §1 included (the card says it was
confirmed before and left unfixed). An `apply` is binding: the resolver must fix it, so an `apply` the
operator never saw would block the merge on the evaluator's say-so alone. **Merge anyway** on a
re-proposed one writes `drop` with `operator: merge anyway`, exactly as on a fresh one.

- **Default** — ask now (`header: "Polish"`), listing each `apply` entry (id, item, reason):
  **Apply** / **File instead** / **Merge anyway**. On a verdict that is already COMMENT (the PR goes
  back regardless) the card decides only whether the items go back with it; **Merge anyway** there
  reads "drop them", and the route does not change.
- **`ask` policy (and epic-integration) with an otherwise-APPROVE verdict** — fold it into the S7-gate
  `Approve PR` card instead of asking twice: the `question` lists the `apply` entries, **Needs
  Revision** applies them, and **Approve** merges without them.

Answers: **Apply** (or Needs Revision) → the verdict becomes COMMENT when it was not already (below). **File instead** →
every `apply` becomes `file`. **Merge anyway** (or Approve) → every `apply` becomes `drop` with the note
`operator: merge anyway`. This confirmation is the **only** limit on how often a PR goes back for
polish — deliberately an operator decision, not a counter; do not add one.

## 3. Write the dispositions once

After the answer, and before the review posts, rewrite the `## Polish` section with the final
dispositions — the ledger never records a decision the operator overrode. Stage the whole PR body with
the rewritten section to `<facts.scratch>/pr-body-polish.md` and apply it through the single write path
(`edit-pr-body` — the issue-body op `edit-body` rejects a PR number):

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py edit-pr-body <owner/repo> <PR> \
  "<facts.scratch>/pr-body-polish.md"
```

Entries are never deleted (`polish-ledger.md` "Rules").

## 4. A confirmed `apply` — the soft-reject and its route

The review body gains a `## Polish` section listing each `apply` entry by id with its reason, and the
operator-attribution header (`**Operator decision: Needs Revision**`, per `review-comment.md`) since
the operator made the call. Post it as S7-post's `comment` and flip the PR back to draft exactly as a
COMMENT verdict does. The handoff's `review:` marker is `COMMENT (operator: needs-revision)`.

Route by whether applying the items changes the plan — the same test the resolver's fix plan applies to
a fix that reverses a plan decision:

- **Changes the plan** — applying an item would reverse a `## Architecture decisions` / `## UI
  decisions` bullet, add or reshape a phase's scope, or cross an epic's `## Story contracts` →
  **`/github-pipeline:planner revise #<issue>`**. The planner sees the ledger (`facts.revise.open_pr.polish`)
  and absorbs the `apply` items as a new phase; the resolver then builds it in continue mode.
- **Otherwise** → **`/github-pipeline:resolver continue #<PR>`**. The resolver's revision run treats every
  `apply` entry as Addressable whatever its tier and marks it `applied (commit <sha>)` once fixed.
