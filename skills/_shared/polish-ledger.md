# Polish ledger — shared contract

The **polish ledger** is the `## Polish` section of a PR body: the review findings the resolver's loop
classified as **polish** and chose not to fix, carried on the PR so the evaluator can decide what
happens to them. This file is the single source of truth for its format and ownership. Three skills
cite it: `resolver` (writer of `open` / `applied`), `evaluator` (writer of `apply` / `file` / `drop`),
and `planner` (reader, on a revise the evaluator routed to it).

## Why it exists

The review loop used to force every ≤ ~20-line fix (the retired Cheap-fix-override bucket) and exit
only on a round that changed nothing. With a `high`-effort reviewer that finds something new and small
on every run, that produced an unbounded tail of polish rounds that only a fixed iteration cap ended.
The loop now exits on **defect** progress alone (`resolve-spine.md` S5.1), and polish is decided once,
by the skill that sees the whole PR and did not write it: the evaluator. The resolver still fixes polish
on merit; only what it leaves lands here.

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
- **Note** — optional; required on `apply` / `file` / `drop` (the evaluator's reason) and on `applied`
  when it records why the evaluator directed it.

## Dispositions (closed set)

| Disposition | Written by | Meaning |
|---|---|---|
| `open` | resolver, at the phase's S5.2 push | recorded, undecided |
| `apply` | evaluator | must be fixed in this PR before it merges |
| `file` | evaluator | becomes a follow-up (grouped per `follow-up-filing.md`) after the merge |
| `drop` | evaluator | not worth doing, or no longer applies at head; the note says which |
| `applied (commit <sha>)` | resolver | an `apply` item fixed in a revision run |

## Rules

- **Only unfixed polish enters.** Polish the loop fixes itself is never recorded; a **defect** is never
  recorded here — it is fixed, deferred with a filed follow-up, or escalated.
- **An `apply` item is Addressable for the resolver whatever its tier** (`review-fix-round.md`
  "Classification rubric"). It has already been decided; re-recording it as `open` would bounce the PR
  between the two skills indefinitely.
- **Items are never deleted.** A dispositioned item stays as the record of the decision; a stale one is
  `drop`ped with its reason, not removed.
- **The operator bounds the cycle.** An `apply` that only polish would cause is always
  operator-confirmed (`evaluator/references/polish-adjudication.md`), and that confirmation is the only
  limit on how often a PR goes back for polish. It is deliberately not a counter.
- **Writes go through the single write path.** The resolver stages the section into `pr.md` (fresh
  mode) or rewrites it with `gh_persist.py edit-pr-body` (continue mode); the evaluator rewrites
  dispositions with `gh_persist.py edit-pr-body`. A body over the cap surfaces the existing
  `BODY_TOO_LONG` decision — one-line entries make that a practical non-issue.
- **Parsing.** `scripts/parse.py` `scan_polish` reads it for the preps (`facts.polish` in the resolver
  and evaluator, `facts.revise.open_pr.polish` in the planner). It never raises: an unparseable line
  lands in `unparsed` and is rewritten on the next write, the phase tracker's posture.
