# Implementation-plan schema

The `<!-- implementation-plan:v1 -->` comment body uses this schema verbatim — the resolver (step 4.6) and pr-evaluator parse these section headings, so don't rename or reorder them. The marker is always the first line of the comment body (every consumer locates the plan with a `startswith` match). Omit sections marked optional when they'd be empty; never pad.

```
<!-- implementation-plan:v1 -->
**Implementation plan** — #<N> <title> — planned <ISO-8601 UTC> at `<plan-ref>@<short-sha>`

## Approach
<1–3 paragraphs: the strategy and why it's the right shape for this codebase>

## Doc grounding
<the PRD / architecture / architecture-notes / ui-design / constitution sections that
constrain this, with §refs — the citations, not a restatement of the approach>

## Architecture decisions
- <decision> — <rationale> — [precedent: `path/to/file:NN` | architecture.md §X | architecture-notes §Y | user decision <date> | DEVIATION (agreed <date>) → see Deviations]
- ...

## UI decisions                  (omit if no UI surface)
- <decision> — [precedent: ui-design §X | DEVIATION (agreed <date>)]

## Changes (file-level)
- `path/to/file` — <what changes; new/modified types, methods, signatures; layer>
- ...

## Data model / schema impact     (omit if none)
- <new/changed model fields/columns, relationships, migration considerations per constitution §8>

## Test plan
- Unit: <suites to add/extend, per constitution §5 coverage targets>
- UI / integration: <integration-test flows, identifiers/selectors, mock/fixture expectations>

## Phases                         (multi-phase issues only — omit for single-phase; epics use the dedicated ## Story breakdown / ## Integration strategy sections)
1. **Phase 1 — <short title>**
   - kind: code-shipping | operator | decision-only
   - ships: PR commits to the issue branch | comment on the issue | external follow-up issue
   - closes-dod: <1-indexed DoD-bullet refs against the issue body — `(none)` when this phase only enables later phases (substrate, harness infrastructure)>
   - deliverable: <one-line concrete artifact this phase produces — quoted verbatim by the resolver's handoff for operator/decision-only phases>
   - depends-on: <earlier phase numbers, or `(none)` for the head phase>
2. **Phase 2 — <short title>**
   - kind: ...
   - ...

## External sources consulted     (omit if none)
- <url or path> — <what decision it informed>

## Deviations from project docs    (omit if none)
- <what deviates> — <why> — agreed with user <date>

## Risks & watchpoints
- <runtime invariant the resolver must preserve while implementing
  (e.g. "keep the trigger gated on the empty-chat invariant so the
  worst case is a single no-op, not a spurious bubble")>
- <false-positive trap from a shim or dual-emit, with the named
  retirement condition: a target that still resolves through a
  temporary shim or dual-emit, so a green run is not proof the change
  is complete — name the shim, the file/line, and the condition that
  retires it (e.g. "`chatSurface.history` still emits via a shim until
  #563; a test using it passes today but the migration is incomplete
  — assert against the new identifier")>
- <edge-case behaviour the plan has *already decided* how to handle,
  surfaced so the resolver doesn't second-guess it (e.g. "cross-day
  completion: no special handling needed because the Finalise button
  isn't surfaced on a past day anyway")>

**This section does not carry open design decisions.** Phrasings that
defer a choice ("Resolver picks", "either approach is acceptable",
"option A or option B", "TBD", "recommend", "could", "might",
"consider", "evaluate during implementation", "implementer decides")
do not belong here. They go in `## Architecture decisions` (pinned
from precedent — see step 7.5) or surface to the user via the
Decision gate at step 6.5 — never here.

_Authored by `github-issue-planner` and verified in <N> review pass(es). The resolver treats
the decisions above as binding; a plan-invalidating discovery routes back here in revise mode.
Re-run this skill to revise — do not hand-edit._
```

## Epic-plan and story-under-epic sections

An **epic** plan replaces `## Phases` (single-issue / multi-phase only) with the sections below, in this order after `## Approach`. The epic plan pins the cross-story **contracts** and sequencing; like every implementation plan it is verified and immutable (do not hand-edit — re-run the planner to revise). Child stories are planned just-in-time against it (planner Step 11 + "Just-in-time story planning" mode), not fanned out up front. The *living* record of what each story actually delivered is kept in a **separate** `<!-- epic-delivery-log:v1 -->` comment — its own artifact, never in this verified plan (see *Epic delivery log* under the schema below).

```
## Story breakdown            (epic only)
- #<story> "<title>" — <one-line scope>
  (ordered top-to-bottom; this order is the sibling-sequencing source of truth)

## Story contracts            (epic only — the cross-story seams; dimension 5 reads this)
- #<story> — delivers: <type/service/API/file the story produces + intended shape>
            — consumes: <contract delivered by an earlier #<story>, or (none)>

## Integration strategy       (epic only)
<how the stories converge on `epic/<N>-<slug>` and reach `main`>
```

A **story under an epic** uses the standard single-issue schema above — with the `**Epic:** #<epic-#> — <epic title>` backlink as the **first line after** the `<!-- implementation-plan:v1 -->` marker (never above it) — plus this section, which dimension 8 checks against the epic plan and the delivery log:

```
## Epic contract              (story under an epic only)
- Delivers: <contract this story produces, matching the epic plan's ## Story contracts entry for it> — [epic-plan: #<N>]
- Consumes: <contract(s) this story builds on, each already recorded in the epic's `<!-- epic-delivery-log:v1 -->` comment, or (none)> — [epic-plan: #<N>]
```

### Epic delivery log (a separate, living comment — not part of the verified plan)

What each story **actually** delivered is tracked in a separate `<!-- epic-delivery-log:v1 -->` comment on the epic issue — maintained by `github-pr-evaluator` (writer) and read by `github-issue-planner` (Just-in-time story planning + Dimension 8). It is **not** part of this verified plan: the plan is immutable, the log changes on every merge. **See [`../../_shared/epic-delivery-log.md`](../../_shared/epic-delivery-log.md)** for its verbatim format and the writer/reader contract.
