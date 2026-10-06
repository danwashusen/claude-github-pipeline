# Polish ledger — shared contract

The **polish ledger** is the `## Polish` section of a PR body: the review findings the resolver's loop
recorded instead of fixing — polish it left, polish in code the PR does not change, and findings with no
shown cost — carried on the PR so the operator can decide what happens to them. This file is the single source of truth for its format and ownership; the procedure that puts entries
to the operator is [`polish-triage.md`](polish-triage.md). Three skills cite it: `resolver` (writer of
`open` / `applied`, and of the operator's `apply` / `file` / `drop` at its finalisation), `evaluator`
(writer of the operator's `apply` / `file` / `drop` for whatever is still `open` when the PR reaches it),
and `planner` (reader, on a revise either of them routed to it).

## Why it exists

The review loop used to force every ≤ ~20-line fix (the retired Cheap-fix-override bucket) and exit
only on a round that changed nothing. With a `high`-effort reviewer that finds something new and small
on every run, that produced an unbounded tail of polish rounds that only a fixed iteration cap ended.
The loop now exits on **defect** progress alone (`resolve-spine.md` S5.1), and polish is decided once,
by the operator, before merge. It is decided **first at the resolver's finalisation**
(`resolver/references/finalisation.md`) — on the final pass, before the push — because the operator
usually wants polish applied, and applying it there costs one fix round in the same session; applying it
from the evaluator costs a soft-reject, a whole revision session and a second evaluation. The evaluator
stays the backstop: the reader that did not write the PR re-checks at head every decided entry that
rests on a claim about the code — an unfixed `apply`, a `file`, a `premise false` `drop` — and puts any
entry still `open` to the operator. The resolver fixes polish on the PR's own code; only what it leaves
lands here.

## Format

The section is `## Polish` in the PR body, one line per item, in the order they were recorded (the
example's paths mix Python, Ruby and Swift on purpose — the format is stack-neutral):

```
## Polish
- P1.1 · open — rename `parse_row` to say it scans, not parses — scripts/importer.py / parse_row
- P1.2 · file — dedupe the two date-format helpers — app/helpers/date_helper.rb / format_short — follow-up: same seam as P2.1
- P2.1 · applied (commit 3f9c2ab) — comment on `retry_after` states the old unit — lib/client.rb / retry_after — evaluator: misleading on a public API
- P2.2 · drop — prefer early return in `Checkout#submit` — app/models/checkout.rb / Checkout#submit — no longer applies at head
- P2.3 · apply — the error message still names the removed flag — Sources/Sync/SyncError.swift / SyncError.message — misleading to operators
```

- **`P<phase>.<seq>`** — the stable id: the phase whose loop recorded it, then a per-phase sequence.
  A revision run ships no phase, so it records under the last `kind: code-shipping` phase's number
  (`1` on a single-phase issue). `<seq>` continues from the highest existing seq for that phase, so a
  re-entered session never mints a duplicate. Both skills cite items by id; an id is never reused or
  renumbered.
- **Disposition** — one word from the closed set below; `applied` alone carries `(commit <sha>)`.
- **Item** — the finding in one line, in the reviewer's terms. It must not contain ` — ` (the field
  separator).
- **Anchor** — durable only: a path plus a symbol or section heading. Never `path:line` — the line
  moves, and downstream sessions re-derive sites fresh (the rule `follow-up-filing.md` applies to
  follow-up descriptions).
- **Note** — optional; required on `apply` / `file` / `drop` (the proposer's reason, led by
  `operator: <answer>` when the operator overrode it) and on `applied` when it records why the entry was
  applied. An `open` entry carries `operator: leave for evaluator` when the operator answered that at
  finalisation: no later finalisation asks again, and the evaluator does.

## Dispositions (closed set)

| Disposition | Written by | Meaning |
|---|---|---|
| `open` | resolver, at the phase's S5.2 push | recorded, undecided — left by finalisation, or recorded before the final pass |
| `apply` | the operator's answer — resolver (finalisation) or evaluator | must be fixed in this PR before it merges (a note led by `operator: re-plan` routes it through a planner revise first) |
| `file` | the operator's answer — resolver (finalisation) or evaluator | becomes a follow-up (grouped per `follow-up-filing.md`) after the merge |
| `drop` | the operator's answer — resolver (finalisation) or evaluator | not worth doing, or no longer applies at head; the note says which |
| `applied (commit <sha>)` | resolver | an `apply` item fixed — at finalisation or in a revision run |

## Apply criteria

The single list of what makes polish **actively bad to merge** — the evaluator's `apply` bucket
(`evaluator/references/polish-adjudication.md`) and the resolver's must-fix-in-loop rule
(`resolver/references/review-fix-round.md` "Classification rubric") both read it from here. Finalisation
proposes `apply` against a lower bar — in scope, true at head, clearly right
([`polish-triage.md`](polish-triage.md) "The apply bar"):

- a comment, doc or message that states something false;
- a misleading name on a public or cross-module surface;
- wrong user-visible copy.

## Rules

- **Only what the loop chose not to fix enters** (`resolver/references/review-fix-round.md`
  "Classification rubric"): polish on the PR's own code that hit one of the rubric's exceptions (a
  guard-path refactor, a change beyond the PR's seam, taste), polish in code the PR does not change, and
  findings with **no shown cost**, whose note leads `no shown cost: <why>` and which triage proposes as
  `drop`. Polish the loop fixes itself is never recorded; a **defect** is never recorded here — it is
  fixed, deferred with a filed follow-up, or escalated. Polish meeting the "Apply criteria" never enters
  either: the resolver always fixes it in-loop, because parked it only buys a revision session.
- **An `apply` item is Addressable for the resolver whatever its tier** (`review-fix-round.md`
  "Classification rubric"). It has already been decided; re-recording it as `open` would bounce the PR
  between the two skills indefinitely.
- **Items are never deleted.** A dispositioned item stays as the record of the decision; a stale one is
  `drop`ped with its reason, not removed.
- **The operator decides every disposition.** The skill running the triage
  ([`polish-triage.md`](polish-triage.md)) proposes `apply` / `file` / `drop` (or a re-plan, recorded as
  `apply`) with a reason; the operator answers each entry on a `Polish` card — the resolver's at
  finalisation, the evaluator's for whatever is still `open` (on any verdict and under either merge
  policy, `evaluator/references/polish-adjudication.md`) — and the ledger records the answer. A decided
  entry is never asked about again, except an `apply` left unfixed, which the evaluator re-proposes so the
  operator can release it, and a `premise false` `drop` whose claim the evaluator finds holds at head
  (`premise disputed`) — at finalisation the proposer judging that premise wrote the code. That is what lets the evaluator treat an `apply` left unfixed as still binding,
  and it bounds the cycle: the operator's answer is the only limit on how often a PR goes back for polish.
  It is deliberately not a counter.
- **A `file` entry files from its note too.** The residual filing briefs each `file` entry from its
  item **and** its note: a `narrowed:` note supersedes the item's claim (the triage found only that much
  still true at head), and entries file **one issue per recorded `group:`** — the groups the operator
  approved on the `Polish` card, never regrouped at filing. Filing runs after the merge, in the
  evaluator's residual step, whichever skill recorded the `file`.
- **An `apply` note's `intent:` is the operator's decision.** Recorded when the triage found two
  intents the plan leaves open; the resolver implements that intent and never picks one itself.
- **Writes go through the single write path.** The resolver stages the section — finalisation's
  answers included — into `pr.md` (fresh mode) or rewrites it with `gh_persist.py edit-pr-body`
  (continue mode), at its S5.2 push; the evaluator rewrites dispositions with
  `gh_persist.py edit-pr-body`. A body over the cap surfaces the existing
  `BODY_TOO_LONG` decision — one-line entries make that a practical non-issue.
- **Parsing.** `scripts/parse.py` `scan_polish` reads it for the preps (`facts.polish` in the resolver
  and evaluator, `facts.revise.open_pr.polish` in the planner). It never raises: an unparseable line
  lands in `unparsed` and is rewritten on the next write, the phase tracker's posture.
