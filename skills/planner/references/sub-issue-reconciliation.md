# Sub-issue reconciliation — the phase set against the live deliverable slices

A **deliverable slice** is a sub-issue of a non-epic target. This file calls them **sub-issues**
throughout, to stay clear of the `out-of-slice` seam vocabulary in
[`seam-dispositions.md`](seam-dispositions.md), which means something else entirely (a seam the
issue's DoD does not cover).

Fires whenever `facts.slices` is present — a non-epic target that already has sub-issues. The
hierarchy is epic → story → slice, so a **non-epic** target's sub-issues *are* its slices by
construction (an epic's sub-issues are stories, and an epic plan carries no `## Phases` at all).
Slices that exist **before** planning are an **input constraint on the plan's shape**, not an output
of it: whoever authored them already made scope calls the plan must serve, and they are
human-editable, so drift between two planner runs is the steady state, not the exception.

## The cardinality rule

**The phase→sub-issue map is N:1 and total over the OPEN sub-issue set.**

- Each phase serves **at most one** sub-issue (`sub-issue: #<N>`), or claims **substrate**
  (`sub-issue: (none)`).
- **Several phases may serve one sub-issue** — that is legal and never a finding. The
  `closes-dod` "exactly once" rule does **not** transfer here.
- Every **open** sub-issue must be named by **at least one** phase. A closed one needs none.
- **Substrate** — groundwork no single sub-issue can demonstrate — is the only legal way for a phase
  to serve no sub-issue. It never licenses leaving an open sub-issue unserved.

Substrate is admitted deliberately: a strict bijection would force groundwork to become a sub-issue
that violates the *demonstrable* bar whoever authors sub-issues works to, or to hide inside a phase
whose `deliverable` then misdescribes what it produces.

The grammar itself (the `#<N>` spelling, the malformed shapes, orthogonality to `closes-dod`) is in
[`plan-schema.md`](plan-schema.md) — this file owns the rule the phase set must satisfy.

## What prep already decided

`facts.slices` carries the live set and the plan-versus-live diff, both computed in-script. Read them
as data; never re-derive them, and never fetch the sub-issue panel yourself.

| Fact | Meaning |
|---|---|
| `slices.set[]` | `number`, `title`, `state`, `position` (the sub-issue panel's own order — the sequencing source of truth), `url`, `updated_at`, `maybe_rescoped`, and the body at `body_path` (always a path, so envelope size stays independent of child count) |
| `slices.open_count` | how many are not closed — the set the map must cover |
| `slices.source` | `sub_issues_rest` (enriched) or `sub_issues_node` (the degraded read) |
| `diff.mapped` / `substrate_phases` / `unmapped_phases` | the prior plan's phase→sub-issue map, by phase number. An **unmapped** phase carries no `sub-issue:` line at all: the mapping was never made, which is not the same as `(none)` |
| `diff.uncovered_open` | open sub-issues no phase serves. **The one key for that fact** — a genuinely newly-*added* sub-issue is indistinguishable from one the plan never mapped, since no prior snapshot of the set exists |
| `diff.closed` | a served sub-issue that has since closed |
| `diff.removed` | a served sub-issue that is no longer parented to this target |
| `diff.rescoped` | edited since the plan was posted — a **suspicion**, see below |
| `diff.order_changed` | a `depends-on` edge that disagrees with the panel order; one row per disagreeing pair |
| `diff.computed` | `false`, with every case list empty, in three reported-as-facts states: no prior plan (`rescope_basis: no_prior_plan`), the prior `## Phases` did not parse (`prior_phases_parsed: false`), or the prior plan has no `## Phases` at all (`prior_phases_present: false` — a legitimate single-phase plan) |
| `diff.prior_phases_parsed` / `prior_phases_error` | the prior plan's `## Phases` was unreadable. This revise re-authors that section, which repairs it — carry on |
| `slices.detail_available` / `slices.rescope_basis` | `false` / `unavailable` when this host doesn't serve sub-issue detail: numbers, titles and states survive; bodies and rescope detection do not |

**`rescoped` is a prompt to look, not proof.** It compares each sub-issue's `updated_at` against the
plan comment's, and an issue's timestamp also bumps on comments, labels and assignment — so it
over-reports. Re-read the sub-issue at its `body_path` and judge; do not treat the flag as a verdict
either way. Two carve-outs keep it honest rather than merely noisy: a **closed** sub-issue is excluded
(closing bumps the timestamp, and closure has its own disposition below), and a served sub-issue whose
timestamp is missing or unparseable is named in `attention` as **not covered** — silence would read as
"nothing changed", the one thing this signal must never say.

**On the fresh path there is no diff, but the cardinality rule still binds.** A finding *about a
plan* cannot exist before a plan does. Cut `## Phases` against the live set from the start, and
reviewer Dimension 7 checks the coverage.

## The gate — a mismatch gates or re-routes; it never silently re-cuts

A non-empty `diff.uncovered_open`, `diff.removed`, or `diff.rescoped` — or any open sub-issue your
phase cut would leave unserved — **stops you before you draft `## Phases`**. Gate
(`header: "Sub-issue reconciliation"`), quoting the findings from `facts.slices.diff`. Three options,
in the order they usually apply:

- **Re-cut the phases to cover the change** — the usual answer for an `added` sub-issue, and for a
  `rescoped` one once you have re-read its body. Continue in this session; the new map must still be
  total over the open set.
- **Record the sub-issue as out-of-scope, with a disposition** — one `## Architecture decisions`
  boundary bullet naming `#<N>`, why this plan does not serve it, and the `[user decision <date>]`
  attribution (the [`seam-dispositions.md`](seam-dispositions.md) residue shape, applied to a
  sub-issue instead of a seam). An open sub-issue may stay unserved **only** with that bullet in the
  posted body.
- **Stop and route the sub-issue set back to whoever authors sub-issues** — the answer when the set
  itself is wrong: a `removed` sub-issue a phase still needs, one whose rewritten scope no phase can
  serve, or children that are not deliverable slices at all. Emit the re-route handoff; post no plan
  and apply no `planned` label.

`diff.closed` and `diff.order_changed` do **not** gate. A closed sub-issue behaves like a **shipped
phase** — the shipped-phase rules in
[`revise-reconciliation.md`](revise-reconciliation.md) govern it, and there is no second, parallel
rule set. A `depends-on` that disagrees with the panel order is **surfaced, not corrected**:
disagreeing may be a deliberate call (an ordering-only dependency), so it rides as a Dimension-7
finding for the operator, never an automatic edit.

## Two hard limits

**The planner writes nothing to a sub-issue** — no filing, no body edit, no relabelling. Where an
authoring change is needed, it hands off.

**The pointer is one-way, plan → sub-issue.** A sub-issue body never cites a phase number, this
reconciliation never reads one, and you may not "fix" one that does: a human editing a sub-issue
cannot be expected to maintain a phase pointer, and repairing it would be a write you are not
permitted to make.
