# Polish adjudication (spine S5.5)

The evaluator decides what happens to the PR's `## Polish` ledger — the polish findings the resolver's
review loop recorded and did not fix. Format, dispositions and ownership live in
[`../../_shared/polish-ledger.md`](../../_shared/polish-ledger.md); this file is the evaluator's
procedure. It runs **after the S5 verdict and before S7's post timing**, because under an `auto` merge
policy an APPROVE posts and merges immediately — a ledger decided after that point could not stop the
merge.

Input: `facts.polish` (prep's scan of the PR body). Nothing to do when it is absent or carries no `open`
entry. A line in `facts.polish.unparsed` is rewritten into grammar by this step's write, keeping its
text; never silently dropped.

## 1. Re-check each `open` entry at head

Read the entry's anchor in the workspace (`facts.workspace.path`, at `pr.headRefOid`) and propose one
disposition, with a one-line reason as the entry's note:

- **`apply`** — the polish would be **actively bad to merge**: a name on a public or cross-module
  surface that misleads, a comment / doc / message that now states something false, user-visible copy
  that is wrong. This bucket is meant to be rare: a PR sent back for polish costs a whole resolver
  session. If most entries want `apply`, the resolver's defect/polish line is misplaced — say so in the
  review body rather than sending the PR round again and again.
- **`file`** — worth doing, not worth holding the merge for. Filed after the merge by the routed
  playbook's residual step, grouped per [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md)
  (polish groups file as `incomplete-feature`).
- **`drop`** — taste rather than improvement, or **no longer applies at head** (a later phase removed or
  rewrote the site). The note says which.

An entry that turns out to be a real defect is not polish: it is a dimension failure in S4 (soft-reject
on the evidence), and the entry is `drop`ped with the note `reclassified: defect — see review`.

## 2. Confirm an `apply` with the operator

Only when the verdict would otherwise be **APPROVE** — on a COMMENT verdict the PR is going back anyway,
so `apply` items ride along in that review with no card.

- **`auto` policy** — no gate card will render, so ask now (`header: "Polish"`), listing each `apply`
  entry (id, item, reason): **Apply** / **File instead** / **Merge anyway**.
- **`ask` policy** (and epic-integration) — fold it into the S7-gate `Approve PR` card instead of
  asking twice: the `question` lists the `apply` entries, **Needs Revision** applies them, and
  **Approve** merges without them.

Answers: **Apply** (or Needs Revision) → the verdict becomes COMMENT (below). **File instead** →
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
