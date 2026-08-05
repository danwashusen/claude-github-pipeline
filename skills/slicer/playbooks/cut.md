# cut — ground, decompose, approve, file

The one flow: ground → decompose → approve → the write gate → sequential filing → handoff. `fresh` and
`resume` differ only in values (`facts.slices` holds what exists; `next_index` is where numbering
continues). Facts come from prep (SKILL.md §1); the write discipline, the zero-mutation gate, the
never-edit-the-parent rule and the partial-failure rule are SKILL.md §3, not restated here.

## S1 — Ground, or refuse

`Read` [`../references/slicing-method.md`](../references/slicing-method.md) first — the method, the
per-slice template, and the presentation format this flow delegates to. Then read the target's body and
thread from `facts.sections` (spilled paths).

Read the docs `facts.grounding_docs` declares, from `facts.root.path` by absolute path — plain
`Read`/`Grep`. Treat each per its `role` (what it answers) and `authority`: `binding` = a cut that
contradicts it is wrong, not a trade-off; `informative` = context you weigh and cite. Skip and note an
entry whose `present` is false. If `facts.research.present`, also read the dossier — current external
truth the cut may cite, never authority.

**The grounding gate — the one gate that cannot degrade into proceeding.** No entries (or
`DOC_CATALOGUE_ABSENT` in `facts.notices`) **and** no sources the operator named at invocation: file
nothing, emit the *Refused — no grounding* shape, stop. If the operator did name sources, read those
and proceed.

## S2 — Decompose

Write the **decomposition strategy** first — two or three sentences: which seam carries the most risk,
what the walking skeleton is, what is deliberately deferred. It stays in this session; persisting it
parent-side would create a second source of truth about the slice set, and each slice's own `## Why a
separate slice` reconstructs the reasoning.

Cut per the method reference: walking skeleton first; each subsequent slice adds exactly one observable
increment; every slice demonstrable in one sentence; prefer few thick-enough slices. On `mode: resume`
treat `facts.slices` as fixed — already approved, possibly already shipped — and cut only the
remainder, numbering from `facts.slices.next_index`.

**Citation duty.** Every slice's `## Grounding` names what it derives from: the catalogue docs (with
§refs) recording the behaviour, the issue body/thread, the dossier. A slice that can cite nothing is a
gap in the source or invented scope — surface it as a finding and leave it out of the cut. Carry any
`provisional-default` marker from `facts.open_questions` into the `## Grounding` of every slice it
touches.

## S3 — Present and iterate

Show the operator, per the method reference's presentation format: the grounding summary (one line per
doc read or noted absent), the strategy, the ordered slice list (designator + outcome sentence each), the
full proposed bodies, then a closing note of risks, assumptions, and anything wanting stakeholder
clarification. They may approve, re-cut, reorder, retitle, or drop slices — iterate until approved. An
open question surfacing here is **not** a slice: route it out (`/github-pipeline:drafter` files the
companion `question` issue) rather than burying a decision in a slice body.

## S4 — The write gate

One summary table — designator · title · one-line outcome · pending write — then **one** explicit
`AskUserQuestion` gate (per [`../../_shared/asking-the-user.md`](../../_shared/asking-the-user.md)).
Aborting here costs nothing; on decline perform no writes and emit the *Declined at the write gate*
shape (the proposed cut is in the transcript; a re-run re-derives it).

## S5 — File the approved slices

Stage each body to `<facts.scratch>/slice-S<K>.md`, then file **one at a time, in approved order**:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py create <owner/repo> "<facts.scratch>/slice-S<K>.md" \
  --title "<N>/S<K> — <behaviour phrase>" --parent <N>
```

The envelope returns the new issue's `url`, not its number — parse `#<n>` from the URL's trailing segment
for the report and the handoff.

A `SUBISSUES_UNSUPPORTED` notice means the relation was not established, so that slice is **unparented**:
stop, report it, file no more. An unparented slice drives no rollup — the entire reason these are issues
— so prose-linked slices are worse than none: they read as tracked progress that does not exist.

## S6 — Handoff

Emit the matching shape from [`../references/handoff-renderings.md`](../references/handoff-renderings.md)
verbatim, per SKILL.md §4. The forward route is the planner: its phases must map onto the slices just
filed (`sub-issue:` in [`../../planner/references/plan-schema.md`](../../planner/references/plan-schema.md)),
and its reconciliation reads the live set — so a plan authored before this cut is now stale.
