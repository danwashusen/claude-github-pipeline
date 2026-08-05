# Slicer handoff renderings

The exact `## Handoff` shapes this skill emits. The schema, the omission rules, the `Slices:` line and
the closed-set state-marker vocabulary are owned by
[`../../_shared/handoff-format.md`](../../_shared/handoff-format.md) — this file only records which
shape each clean exit uses and its exact wording.

**Copy the shape verbatim.** The field names, block structure, and closed-set markers are contract,
not prose to summarize: substitute only numbers, titles, states, and grounding citations. Never
paraphrase a field name, drop a `·` segment, restructure the block, inline the fenced command into
prose, or add a block the shape does not have.

Two lines are free-form text rather than state markers, so they carry no closed-set vocabulary:
`Slices:` (the designators + states, or the progress count) and `Grounding:` (the sources the cut
derived from). Every other marker comes from the shared closed sets.

The `Grounding:` line is present on **every exit that filed slices**, and omitted on every exit that
filed nothing — a cut that hides what it was grounded on defeats the grounding gate.

## Renderings

**Slices filed (fresh cut).** The forward route. `Grounding:` names the docs the cut derived from;
`plan: ✗` because the cut precedes planning.

```
## Handoff

**Issue:** #103 — Patient: access & set up account · open · story · plan: ✗
**Slices:** #104 103/S1 (open) · #105 103/S2 (open) · #106 103/S3 (open)
**Grounding:** docs/prd.md §4 (account lifecycle, binding); docs/architecture.md §3 (service layer, binding); docs/ui-design.md §7 (auth screens, informative)

**Next:** plan #103 — its phases must map onto the three approved slices.

    /github-pipeline:planner 103

**Why:** #103 now carries 3 operator-approved deliverable slices as sub-issues. The planner's `sub-issue:` reconciliation maps phases onto the live set, so a plan authored before this cut would mismatch it; the resolver then closes each slice as its last serving phase ships.
```

**Remainder filed (resume).** A re-run over a partially-sliced parent. The `Slices:` line lists the
whole live set — pre-existing and new — because the reader cares about the parent's state, not this
session's delta; the `Why:` names which were added.

```
## Handoff

**Issue:** #103 — Patient: access & set up account · open · story · plan: ✗
**Slices:** #104 103/S1 (closed) · #105 103/S2 (open) · #106 103/S3 (open)
**Grounding:** docs/prd.md §4 (account lifecycle, binding); docs/architecture.md §3 (service layer, binding)

**Next:** plan #103 — its phases must map onto the full slice set, including the two just added.

    /github-pipeline:planner 103

**Why:** #103 already carried #104 (shipped and closed); this run cut the remainder into #105 and #106, numbering from S2. The planner reconciles against all three — a phase set covering only the original slice is now incomplete.
```

**Already fully sliced — nothing to add.** `resume` mode where the operator confirms the existing set
is complete. No writes, so no `Grounding:` line.

```
## Handoff

**Issue:** #103 — Patient: access & set up account · open · story · plan: ✗
**Slices:** 1 of 3 closed · next: #105 103/S2

**Next:** plan #103 against its existing slices.

    /github-pipeline:planner 103

**Why:** #103's slice set is already complete and approved — nothing was filed this run. Confirmed with the operator rather than re-cutting, since re-cutting an approved set would duplicate live slices.
```

**Declined at the write gate.** The operator rejected the cut. **Zero GitHub writes happened**, so
both `Slices:` and `Grounding:` are omitted.

```
## Handoff

**Issue:** #103 — Patient: access & set up account · open · story · plan: ✗

**Next:** plan #103 as a single unit, or re-run the slicer with different guidance.

    /github-pipeline:planner 103

**Why:** the operator declined the proposed cut at the write gate, so nothing was filed and #103 is untouched. The proposed slices are in this session's transcript; a re-run re-derives them from the same sources.
```

**Refused — no grounding.** The one refusal that routes outside the pipeline: the remedy is a doc
catalogue, not another stage.

```
## Handoff

**Issue:** #103 — Patient: access & set up account · open · story · plan: ✗

**Next:** declare this repo's grounding documents, then re-run the slicer.

    /github-pipeline:setup

**Why:** this repo declares no grounding documents — no `docs/README.md`, or no `<!-- doc-catalogue -->` block in it — and no sources were named at invocation. Nothing was filed: decomposing from the issue body alone invents scope, and invented scope becomes real sub-issues the planner then plans against. Setup derives a catalogue from the docs index for your confirmation.
```

**Refused — blocked.** An open native blocker or an `in-scope (blocked)` open question.

```
## Handoff

**Issue:** #201 — Add payment capture · open · feature · plan: ✗

**Next:** answer the open question blocking #201, then re-run the slicer.

    /github-pipeline:question-resolver 61

**Why:** #201 is blocked by open question #61 (native `blocked by`), read from live state rather than the body's recorded line. Nothing was filed: slicing against an unanswered question produces slices the answer may invalidate, and they would be filed as real issues before the decision is made.
```

**Refused — epic target.** Epic altitude belongs to the drafter until the slicer is retargeted.

```
## Handoff

**Epic:** #150 — Epic: onboarding funnel · open · epic · plan: ✗

**Next:** split #150 into stories in a fresh drafter session.

    /github-pipeline:drafter split epic #150 into stories

**Why:** #150 is an epic, and an epic's children are *stories* — independently shippable, each with its own branch and PR — not deliverable slices, which get no branch of their own. The drafter owns epic decomposition; nothing was filed here.
```

**Refused — the target is itself a slice.** Terminal: the pipeline names no follow-up, because the
right next action is on the parent.

```
## Handoff

**Issue:** #105 — 103/S2 — password reset · open · plan: ✗

**Next:** (terminal — no follow-up skill)

**Why:** #105 is itself a deliverable slice of #103 (its parent is not an epic). A slice is never sliced: it has no branch of its own, so a sub-slice could not ship as anything, and a fourth hierarchy level would break the by-construction rule every reader uses to tell slices from stories. Plan or resolve #103 instead; nothing was filed.
```

**Refused — closed target.**

```
## Handoff

**Issue:** #203 — Old feature · closed · feature · plan: ✗

**Next:** (terminal — no follow-up skill)

**Why:** #203 is closed, so nothing would ever ship a phase to close its slices — the parent's rollup would read `0/N` permanently. Reopen it first if the work is genuinely resuming; nothing was filed.
```
