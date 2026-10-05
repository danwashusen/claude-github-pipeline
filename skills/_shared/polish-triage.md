# Polish triage — shared procedure

The polish ledger's undecided entries ([`polish-ledger.md`](polish-ledger.md)) are decided by the
operator, entry by entry, on one `Polish` card. Two skills run this procedure, in this order on a PR's way
to merge:

- the **resolver's finalisation** (`resolver/references/finalisation.md`) — on the final pass, before the
  phase's push, so an applied entry costs one fix round in the same session;
- the **evaluator's S5.5** (`evaluator/references/polish-adjudication.md`) — the backstop for whatever is
  still undecided when the PR reaches it, before the review posts.

This file is the single source of truth for the steps both share: re-check each entry at head, propose a
disposition, group, ask, and record the answers. Each caller supplies **the entries** it triages, **the
checkout** it reads them in, **the plan** its scope test reads, **its apply bar**, and **what follows the
answers** (its write, its route); everything else stays in its own reference.

## 1. Re-check each entry's claim at head

Read the entry's anchor in the caller's checkout and check the entry's **claim**, not only that the
anchor still exists — the reviewer wrote it against an earlier diff, and a later phase or fix round may
have made it false or narrower. False as written → propose `drop` with the note
`premise false at head — <why>`; true only in part → keep the item text and put what is actually true at
head in the note (`narrowed: <what holds>`), so a filed follow-up carries the corrected claim, not the
reviewer's.

## 2. Propose a disposition

Propose one of the following, with a one-line reason as the entry's note:

- **`apply`** — the entry clears the caller's **apply bar** ("The apply bar").
- **re-plan** — the entry sits inside this PR's scope (the plan's `## Changes` / phase `ships`, or the
  issue's Definition of done in `facts.dod`) but its fix needs a decision the plan does not make: it would
  make a plan decision bullet **false as written** (reverses a choice, redefines a term the plan defines,
  moves work the plan places elsewhere — a list of required behaviour is a minimum, a definition is not),
  or the plan and the Definition of done leave the intended behaviour open, so two fixes fit, each serving
  a different intent. The note names the bullet, or the two intents. This is a proposal, not a
  disposition: the operator's **Re-plan** answer records `apply` and the caller routes to the planner.
- **`file`** — worth doing, but not in this PR at the caller's bar. Filed **after the merge** by the
  evaluator's routed playbook's residual step, grouped per
  [`follow-up-filing.md`](follow-up-filing.md) (polish groups file as `incomplete-feature`) — never
  earlier, so a PR that never merges files nothing. An entry **outside** this PR's scope that also needs
  an intent decided files too — the note states the open question, so the follow-up's planner answers it
  rather than inheriting a guess.
- **`drop`** — taste rather than improvement, a premise false at head, or **no longer applies at head**
  (a later phase removed or rewrote the site). The note says which.

An entry that turns out to be a real defect is not polish; each caller's reference says what happens to
it, and the card never asks about it.

### The apply bar

The one proposal rule that differs by caller, because applying costs each a different amount:

- **Resolver finalisation** — the entry is in this PR's scope (the re-plan bullet's scope test), still
  true at head, and clearly right rather than taste. Applying costs one fix round in this session, so
  size alone is not a reason to file: `file` is for an entry outside the scope, or one big enough to need
  its own plan (a new module, a cross-seam refactor). The proposer is the session whose loop left the
  entry, so judge it against this bar, not against the reason the loop left it — "not cheap" and "not on
  code this phase touched" were the loop's bar, not this one.
- **Evaluator** — the entry meets [`polish-ledger.md`](polish-ledger.md) "Apply criteria": it would be
  **actively bad to merge**. Applying there costs a soft-reject, a whole resolver session and a second
  evaluation, and the operator has usually answered finalisation's card already.

## 3. Group and ask

Group the entries: one group per proposed follow-up (the `file` grouping of
[`follow-up-filing.md`](follow-up-filing.md) — same type, same seam), one group for each `apply` or
re-plan seam, and one group for all the `drop` proposals. Ask one `Polish` card (`header: "Polish"`) with
one question per group — at most 4 questions per card; more groups ask a second card after the first is
answered. Each question lists the group's entries (id, item, the proposer's reason, and any
`premise false` / `narrowed` correction) and offers four options, the proposal first and marked
recommended:

- **File as follow-up** — filed after the merge.
- **Apply in this PR** — the resolver fixes it before the merge.
- **Re-plan** — the planner revises the plan for it before the resolver continues.
- **Drop**

The tool's "Other" takes a split answer by id ("file all but P1.3; re-plan P1.3"); apply it entry by
entry. A caller may give "Other" one reading of its own, named in its reference.

## 4. Record the answers

- **File as follow-up** → `file`, the note carrying `group: <the question's group label>` — the residual
  step files one issue per recorded group, as the operator approved it
  ([`polish-ledger.md`](polish-ledger.md) "Rules").
- **Drop** → `drop`.
- **Apply in this PR** → `apply`. On an entry proposed as re-plan because two intents fit, ask one
  follow-up question first — one option per intent the note names — and record the answer as
  `intent: <chosen>` in the note: the resolver implements that intent and never picks one itself.
- **Re-plan** → `apply`, the note prefixed `operator: re-plan —`, which forces the caller's planner route
  whatever its own plan-change test says.

When an answer differs from the proposal, the note leads with `operator: <answer>` and keeps the
proposer's reason after it. Every answer is the operator's decision, so a later triage never asks about a
decided entry again, with two exceptions the evaluator owns: an `apply` the resolver left unfixed, which
it re-proposes so the operator can release it, and a `premise false` drop whose claim it finds holds at
head (`premise disputed`). An `open` entry noted `operator: leave for evaluator` is the operator's answer
to wait for the evaluator: finalisation skips it. The caller writes the answers once, through the single write
path; the ledger never records a decision the operator overrode, and entries are never deleted
([`polish-ledger.md`](polish-ledger.md) "Rules").
