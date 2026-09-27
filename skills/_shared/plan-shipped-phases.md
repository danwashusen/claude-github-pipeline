# Shipped-phase records — shared contract

A **shipped-phase record** holds one shipped phase's `## Changes (file-level)`, `## Data model / schema impact` and `## Test plan` entries, **moved verbatim** out of the `<!-- implementation-plan:v1 -->` plan comment. It lives as **one durable comment per shipped phase** on the planned issue, next to the plan.

This file is the single source of truth for its format and ownership. Three skills cite it: `planner` (writer), `resolver` and `evaluator` (readers).

## Why it exists

A story or single-issue plan grows on every revise. Each revise usually adds a phase, and nothing ever leaves: an epic plan shrinks when a story **merges** (`plan-schema.md` "Retirement"), but a shipped phase is only pushed to a draft PR the evaluator has not judged yet. The evaluator checks the **whole** PR diff against the plan's `## Changes` / `## Data model / schema impact` / `## Test plan` (`evaluate-spine.md` S3 "Plan adherence"), so a shipped phase's entries cannot simply be dropped. The one observed case: #690's seven-phase story plan went 53.6k → 63.9k characters against GitHub's 65,536-character comment cap on one revise, and most of the session went to trimming it.

The fix is the delivery log's (#41, [`epic-delivery-log.md`](epic-delivery-log.md)): split the artifact that grows by construction into one bounded comment per unit. The shipped detail stays binding and readable; it just no longer costs the main comment anything.

## What moves and what stays

**Moves**, on **every** revise, for each phase that is ticked in the PR's `## Phase tracker`, is `kind: code-shipping`, and has no record yet (prep reports exactly these as `facts.plan.shipped.to_relocate`):

- the phase's entries in `## Changes (file-level)`, `## Data model / schema impact` and `## Test plan`.

**Stays in the main plan comment**, always:

- every `## Phases` entry, shipped ones included. The tracker joins on phase number, DoD projection reads `closes-dod`, and reviewer Dimension 7 needs the whole set.
- every `## Architecture decisions` / `## UI decisions` / `## Deviations from project docs` bullet. The resolver cites them **verbatim** (Plan-settled, review context, fix design).
- a **shared entry** — one any unshipped phase still builds on (a file phase 2 shipped that phase 7 still modifies). It stays whole and is never split to separate the shipped half; moving it would take a locked decision away from a phase the resolver still has to build.
- everything else.

An `operator` / `decision-only` phase has no entries to move and never gets a record.

**The unit that moves is one top-level bullet**, with its continuation lines and sub-bullets. `## Test plan` is grouped by kind (`Unit:` / `UI / integration:`), so there the unit is a sub-bullet under a kind line, and the record repeats the kind line. A single-line kind bullet listing several phases' suites (`- Unit: a_spec, b_spec`) is a shared entry and cannot move — so a multi-phase plan writes one sub-bullet per suite under each kind line, which the schema's `<suites to add/extend>` placeholder permits.

## Format

The marker is always the **first line**, and line 2 carries the rest of the key:

```
<!-- implementation-plan-shipped:v1:phase:<N> -->
**Shipped on:** #<PR> · Phase <N> — <phase title, as in ## Phases>

## Changes (file-level)
- <entries moved verbatim from the main plan>

## Data model / schema impact
- <entries moved verbatim — omit the section when the phase moved none>

## Test plan
- <entries moved verbatim>
```

No other section appears in a record. The phase in line 2 must match the marker's.

**The marker is a separate family, on purpose.** `<!-- implementation-plan-shipped:` never starts with `<!-- implementation-plan:v1 -->`, so every existing plan lookup (`startswith` in the gathers and the resolver audit) stays blind to records, and a record can never make the plan itself `MARKER_AMBIGUOUS`. `:phase:1 -->` is not a prefix of `:phase:10 -->` — the trailing ` -->` terminates the match.

**Key = (PR, phase).** A record belongs to the PR its phase shipped on. Shipped phases keep their numbers (`revise-reconciliation.md`'s renumbering rule), so the key is stable across revises. Two records with the same (PR, phase) are a genuine duplicate: `MARKER_AMBIGUOUS`.

**The plan's pointer names whose records to read.** Every reader reads the records on the PR the plan's pointer bullets name — normally the open PR. When that PR has closed (a HARD Start-fresh, a hand-closed PR), its records are the **only** copy of the entries the pointer stands in for, so readers still read them and flag the mismatch, and the next revise restores them into the plan and drops the pointer. After that the closed PR's records are **inert**: nothing points at them, and nothing is ever deleted.

**The pointer.** Each main-plan section that lost entries carries one bullet in their place:

```
- Phases 1–6 shipped on #903: entries in the shipped-phase records.
```

It keeps an emptied heading present (the heading is parsed, and "never pad" is what one line satisfies). It carries no `@<sha>`: the plan's footer SHA is read with an unanchored first-match search.

## Invariants

- **Verbatim.** A record is a move of already-reviewer-verified text, never a re-authoring. `plan_shipped.py check` proves it before the post.
- **Immutable.** A record is never edited once posted. Changing one is changing what a shipped phase delivered — **HARD** (`revise-reconciliation.md`).
- **Not a history layer.** A record is live, binding plan content in a second place, not prior text. `revise.md`'s "no history layer" rule is untouched: superseded text still lives only in the comment's edit history and the thread.
- **No backfill.** A plan written before records existed gets them on its next revise. A plan with no records reads exactly as before.

## Writing (planner)

The procedure is [`../planner/references/shipped-phase-relocation.md`](../planner/references/shipped-phase-relocation.md). Records are posted with `gh_persist.py comment` **before** the main plan's `edit-comment`: if the main edit then fails, the only cost is content present in both places, and the next revise's `to_relocate` already excludes the posted phases.

## Reading (resolver, evaluator)

Prep does the read — a thread scan by `scripts/plan_shipped.py collect`, zero extra `gh` calls, for the PR the plan's pointer names — and stages the records as one path. A pointer naming a PR other than the reader's own rides in `attention` / `notices`; so does a record whose line 2 cannot be keyed (`unkeyed`), which no reader can place:

- **resolver** (any mode): `facts.plan.shipped.body_path`, which is also `distiller_bundle.plan_shipped_path`. The distiller's `locked decisions` summary includes the record entries, labelled by phase.
- **evaluator**: `facts.plans[<issue>].shipped.body_path`. Plan adherence reads a shipped phase's `## Changes` / `## Data model / schema impact` / `## Test plan` from its record. A duplicated plan or record degrades to a notice, never a stop: adherence is one judgment among the merge gates.

A main-plan pointer bullet is never itself a locked entry; the records it names are.
