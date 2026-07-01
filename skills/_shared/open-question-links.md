# Open-question links — shared contract

The **`## Open questions`** section is a body section a **build** issue (bug / feature / incomplete /
epic / story) carries when it was drafted from a source that still has **unresolved open questions**
(OQs) — decisions tracked in a doc register the consuming repo keeps, e.g. a `docs/prd.md` open-questions
register (`PRD-OQ-##`) or a design register (`OQ-##` / `DESIGN-Q-#`), often surfaced inline in the
source as `PROVISIONAL — <oq-id>` / `TBD` markers. It records, per OQ, *what scope the OQ gates* and
*how the build issue disposes of it*, and links to the `question`-type issue that routes the decision to
a human. It turns a doc-internal OQ into a **tracker-visible dependency**.

Two linkage layers, doing different jobs:
- **This section** = the human-readable metadata registry (OQ id, source, gated scope, disposition,
  audience, companion question) that GitHub's native relationships can't carry.
- **A native `blocked by` dependency** = the structured relationship, set only for the `in-scope
  (blocked)` disposition (§Dispositions), so GitHub itself, the resolver, and the evaluator can gate on
  it. Capability-gated: when a repo/gh lacks native dependencies, everything degrades to prose (a
  `Related to #N` line in `## Related issues` plus this section) — the relationship is never lost, only
  its native form.

This file is the single source of truth for the section's format, its dispositions, and the ownership
split. Every consumer cites it rather than restating the schema.

## Ownership

| Skill | Role |
|---|---|
| `github-issue-drafter` | **Sole writer.** Creates the section at draft time (one entry per gating OQ), sets the native `blocked by` for `in-scope (blocked)` entries, and reconciles both in revise mode (add newly-open OQs; on an OQ now resolved upstream, surface it and offer to re-file — don't silently delete). |
| `github-issue-planner` | **Reader + extender.** Reads this section and the issue's native `blocked_by` to learn which scope is gated, copies the live entries into the *plan's* own `## Open questions` section, and **never silently resolves an OQ** (a tracked OQ is not a hedge — see the planner's §7.5 carve-out). Does not write this body section. |
| `github-issue-resolver` | **Reads `blocked_by`; hard-gates.** If the issue is natively `blocked by` an **open** question, routes to its `blocked` classification (surface "can't build until #N answers") instead of building the gated criterion. Treats this section as a tracked-dependency registry — **not buildable scope, not a DoD source**. |
| `github-pr-evaluator` | **Reads `blocked_by`; hard-gates.** Holds / soft-rejects the merge while an in-scope blocker (open question) is unresolved, citing it. Does **not** read this section's bullets as acceptance criteria or as DoD gaps. |

The section stays out of the verified `<!-- implementation-plan:v1 -->` plan on purpose: the plan is
immutable, while this dependency record changes as OQs open and resolve.

## Format

The `## Open questions` heading is the human anchor; the `<!-- open-question-links:v1 -->` marker is the
**first line inside the section** (readers locate the registry with a `startswith` match on that line).
Omit the whole section when no OQ gates the issue. One bullet per gated OQ:

```
## Open questions
<!-- open-question-links:v1 -->
- OQ: `<oq-id>` (<source-doc> <§/register-location>) — gates: <one line of the scope this OQ blocks>
  — disposition: scoped-out | in-scope (blocked) | provisional-default
  — question: #<N> | (not filed) — audience: <comma-separated audience:* labels, or (unknown)>
  — [provisional-default only] default: <the provisional choice built on> — retires-when: <#N answered>
```

`disposition` is a closed set of exactly three values. `question: #<N>` is the companion `question`-type
issue that routes the decision (`(not filed)` when the user declined at the drafter's gate).

**Stack-neutral examples** (never present one repo's id syntax as canonical):
```
## Open questions
<!-- open-question-links:v1 -->
- OQ: `PRD-OQ-05` (docs/prd.md §12 Open questions) — gates: which payment methods ship at launch
  — disposition: scoped-out — question: #211 — audience: audience:business, audience:developer
- OQ: `OQ-08` (docs/ui-design.md §5 register) — gates: consult-modality copy on the next-consult tile
  — disposition: in-scope (blocked) — question: #212 — audience: audience:clinical
- OQ: `DESIGN-Q-3` (docs/design/notes.md "Open decisions") — gates: default sort order of the results list
  — disposition: provisional-default — question: #213 — audience: audience:ux
  — default: newest-first — retires-when: #213 answered
```

## Dispositions

- **`scoped-out`** (the drafter's default) — the gated part is removed from *this* build issue's scope.
  It **MUST** have a matching line in the issue's `## Out of scope` naming the same OQ. Because the part
  is out-of-scope, it never enters the `## Definition of done`, so the resolver/evaluator hard-block on
  in-scope documented-constraint deferral is **not** triggered (this is out-of-scope, not an in-scope
  deferral). No native dependency (the issue ships its decided scope and isn't blocked); a `Related to
  #<question>` line in `## Related issues` cross-links the companion. When the question is answered, the
  scoped-out work is re-filed as a fresh build issue (see Closing protocol).
- **`in-scope (blocked)`** — the part stays in the issue's DoD but cannot be completed until the question
  answers. The build issue **MUST** be set natively `blocked by` the companion question (the structured
  gate the resolver/evaluator read) — so this disposition **requires a companion question to exist**. If
  none is filed (`question: (not filed)`) there is nothing to block on: the drafter must not emit a
  dangling `blocked_by`, so it either falls back to `scoped-out` or records a **prose-only** blocker (no
  native dep) and warns that the resolver/evaluator can't hard-gate it until a question exists. The
  drafter warns the user this holds the resolver/evaluator until the question is answered. "(blocked)"
  here is a human qualifier — unrelated to the resolver's `blocked` issue *classification*, though a
  natively-blocked issue does route through that path.
- **`provisional-default`** — the part is built now on a stated provisional choice; the issue is **not**
  blocked. The entry **MUST** carry `default:` (the choice built on) and `retires-when:` (`#<N>
  answered`), and the planner records it as a named watchpoint. It stays in-scope: if the provisional
  choice later contradicts a grounding doc, the evaluator's in-scope hard-block correctly fires — the
  disposition is opt-in and the risk was accepted.

## The doc→tracker bridge

The companion `question` issue's own `## Tracked in` section points at **both** the source-doc register
location (`docs/prd.md → Open questions → PRD-OQ-05`) **and** the build issue `#` that depends on it, so
the loop is closeable from either end.

## Closing protocol

No skill auto-reopens work when a question is answered (consistent with session-per-skill and the
no-auto-cross-boundary rule). The human answers the `question` issue in its thread (terminal). Then: a
`scoped-out` follow-up is a fresh `github-issue-drafter` run (breadcrumbed by the question's
`## Tracked in` build back-link); an `in-scope (blocked)` dependency is cleared by removing the native
`blocked by` (`PERSIST_LINK --remove-blocked-by`) and folding the now-decided scope in via the drafter/
planner revise flow; a `provisional-default` is confirmed or corrected the same way, retiring the
watchpoint.
