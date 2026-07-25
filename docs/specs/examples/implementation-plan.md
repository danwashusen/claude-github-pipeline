# Example — `<!-- implementation-plan:v1 -->` plan comment (schema definition)

> Artifact: the `<!-- implementation-plan:v1 -->` plan comment (prd.md §7, row 1).
> Source: `skills/github-issue-planner/references/plan-schema.md:1-110` (the single-issue schema block;
> lines 1-9 give the file's own framing, the fenced block itself runs lines 5-110).
> This is a **schema/template definition**, not a worked instance — v1 has no fixture repo to pull a
> literal posted comment from, so the canonical example is this template block, verbatim, exactly as
> the planner and its consumers (resolver, evaluator) read it.

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

## Coverage gap                   (bug fixes only — omit for feature/incomplete/epic/story)
- Escape: <existing test(s) that should have caught this — file path + suite/section — and the
  path/state/input the root cause exercises that they don't reach, grounded at the plan ref>
- Closed by: <the regression test in ## Test plan that exercises that path — name + assertion
  intent; it must fail against the pre-fix code at the plan ref and pass after the fix>
  (or `(none)` with a reason: a pure dependency bump with no reachable new behaviour, a surface
  with no test harness, or a defect not reproducible in an automated test — matching Dimension 9)

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
- <a **provisional-default** open question named in `## Open questions`,
  with its retirement condition: the same choice that section's
  `default:` field records and the same `retires-when: #<N> answered`
  — surfaced here because the choice ships as real in-scope scope now,
  not a hedge (e.g. "tags are stored lowercased for case-insensitive
  matching (`§5.5`); `question: #51` may later decide case-preserving
  display, which touches only the display layer, not the stored value
  — retires-when: #51 answered")>

**This section does not carry open design decisions.** Phrasings that
defer a choice ("Resolver picks", "either approach is acceptable",
"option A or option B", "TBD", "recommend", "could", "might",
"consider", "evaluate during implementation", "implementer decides")
do not belong here. They go in `## Architecture decisions` (pinned
from precedent — see step 7.5) or surface to the user via the
Decision gate at step 6.5 — never here. The one exception is a
**human-owned open question already tracked** as a `question` issue or
a doc open-questions register entry: that goes in `## Open questions`
below (a tracked open question is not a hedge — step 7.5 carve-out),
not resolved from precedent and not sent to the Decision gate. A
**provisional-default** OQ is the one case that appears in both
sections: the decision itself is built now (an ordinary entry in
`## Architecture decisions` / `## Changes`, not a hedge) — the bullet
here only records its retirement condition, it does not re-open the
choice.

## Open questions              (omit if none — the issue's gated decisions the plan plans around)
- OQ `<id>` (<source §/register>) — gates: <scope> — question: #<N> | (not filed) (audience: <audience:* labels>)
  — treatment: planned-around | recorded-blocked | provisional-default
  - planned-around: <how the unblocked scope is planned without resolving the OQ; what is deferred to the follow-up>
  - recorded-blocked: <the in-scope part the plan cannot specify until #<N> answers — NOT in ## Changes / ## Test plan>
  - provisional-default: <the provisional choice, planned and built as a normal in-scope decision — not deferred> — default: <the provisional choice built on> — retires-when: <#<N> answered> — also add a matching `## Risks & watchpoints` entry

_Authored by `github-issue-planner` and verified in <N> review pass(es). The resolver treats
the decisions above as binding; a plan-invalidating discovery routes back here in revise mode.
Re-run this skill to revise — do not hand-edit._
```

## Epic and story-under-epic variants

The Epic plan replaces `## Phases` with the sections below, inserted after `## Approach` and before
the standard `## Doc grounding` tail. Source: `skills/github-issue-planner/references/plan-schema.md:116-127`.

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

A story under an epic uses the standard single-issue schema above, with the `**Epic:** #<epic-#> —
<epic title>` backlink as the first line after the marker, plus this section (checked by dimension
8 against the epic plan and the delivery log). Source:
`skills/github-issue-planner/references/plan-schema.md:131-135`.

```
## Epic contract              (story under an epic only)
- Delivers: <contract this story produces, matching the epic plan's ## Story contracts entry for it> — [epic-plan: #<N>]
- Consumes: <contract(s) this story builds on, each already recorded in the epic's `<!-- epic-delivery-log:v1 -->` comment, or (none)> — [epic-plan: #<N>]
```
