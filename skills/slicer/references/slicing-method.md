# Deliverable slicing — method, grounding contract, and the slice template

How to decompose one filed issue into the ordered deliverable slices that become its native
sub-issues. Read this whole file before cutting; it is the methodology `playbooks/cut.md` delegates
to.

What a deliverable slice **is**, how it differs from a story, and the closing contract are defined
once in [`../../_shared/epic-story-hierarchy.md`](../../_shared/epic-story-hierarchy.md). Cite that;
this file is about *how to cut*.

## 1. The independence bar is a parameter

One operation, one knob. Decomposition asks the same question at every altitude — *what is the
smallest increment of visible behaviour that stands on its own?* — and only the meaning of "stands on
its own" changes:

| Cutting | Children | The bar each child must clear |
|---|---|---|
| a story or standalone issue into slices | slices | independently **demonstrable** — someone can show the new behaviour |
| an epic into stories | stories | independently **shippable** — the child gets its own branch and PR |

Everything below — the ordering rule, the sizing bias, the citation duty, the anti-patterns — is
written against *the bar*, never against the word "slice". Read it with whichever bar the caller is
cutting at. This is deliberate: retargeting the method to epic altitude changes the bar and nothing
else.

## 2. Think vertical, not horizontal

A slice cuts through whatever layers the behaviour needs — interface, application logic, domain
rules, persistence, authorization, validation, tests, observability — rather than delivering one
layer across all behaviours. Each slice answers:

> "What can the actor now do that they could not do before?"

These are **never** slices, because nothing is demonstrable when they finish:

- "Create the database tables" / "write the migrations" / "add the indexes"
- "Build the API endpoints"
- "Implement the UI"
- "Set up the background job"

They are implementation *tasks*, and a task belongs inside a slice — not as a slice, and not as a
sub-issue of one.

## 3. Grounding inputs — read before decomposing

Slices are **composed from what the sources already record, never invented**. A decomposition drawn
from a two-line issue body will hallucinate scope, and invented scope becomes real issues that
downstream stages then plan against.

| Input | Where | Standing |
|---|---|---|
| The repo's declared docs | `facts.grounding_docs` — the `<!-- doc-catalogue -->` entries | **Required.** A `binding` entry is a constraint, not a trade-off; an `informative` one is context. |
| The issue body + thread | `facts.sections` (spilled paths) | **Required.** The thread may have moved past the body — the latest accepted direction wins. |
| Research dossier | `facts.research.present`, staged in `facts.sections` | Optional — current external truth the cut may cite. Input, never authority. |
| Sources the operator names at invocation | the invocation itself | Optional, and the only substitute when no catalogue exists. |

**No catalogue and no operator-named sources → refuse.** That is the one gate with no proceed-anyway
rung ([`../../_shared/doc-catalogue.md`](../../_shared/doc-catalogue.md) explains why a proceeding
reader and a refusing reader are both correct responses to the same absent fact — the slicer is the
refusing kind, because its whole output is derived from documents).

**Citation duty.** Every slice's `## Grounding` names what it derives from — the doc (with its
§heading or register id) that records the behaviour, the body/thread passage, the dossier source. A
slice that can cite **nothing** does not exist: either the behaviour is real and the source has a gap
(surface it as a finding), or the slice is invented scope (drop it). A `provisional-default` open
question travels with every slice it touches, named in that slice's `## Grounding`.

## 4. Method

Write a two-or-three-sentence **decomposition strategy** first: which seam carries the most risk,
what the walking skeleton is, what is deferred. Then cut:

1. **First slice = the thinnest walking skeleton.** The narrowest end-to-end path that crosses every
   architectural seam the issue touches. It proves the seams while changing course is still cheap,
   and gives stakeholders something real to react to.
2. **Each subsequent slice adds exactly one observable increment** — a new path, a new variant, a
   recorded failure behaviour — never "finish the backend".
3. **Every slice clears the bar on its own.** If you cannot describe the demonstration in one
   sentence, the cut is wrong.
4. **Prefer few, thick-enough slices over many thin ones.** Slices sequence risk and feedback; they
   do not shard work. A handful is usually right; **ten or more is an anti-pattern** (§8). Two
   independent reasons: a thin slice's demo sentence stops being interesting, and a rollup of fifteen
   children is noise rather than a progress signal — and the rollup is why these are issues at all.

## 5. Failure paths

Operational behaviour earns its own slice — or explicit scenarios inside a slice's acceptance
criteria — **when and only when a source records it**: concurrency and double submission, expiry,
retries and idempotency, an unavailable dependency, validation failures, recovery after interruption,
authorization failures. Recorded failure modes are requirements with provenance, not optional polish,
and deferring them all to the end defers the riskiest work to last.

Never invent a failure mode the sources don't record. That is new scope, and new scope is elicited
from a human, not minted here.

## 6. Ordering

Present slices in recommended delivery order and state dependencies between them explicitly. The
sequence should retire risk while delivering value early: walking skeleton, then the riskiest
recorded seam, then breadth.

**The order the operator approves is the order the slices are created in** — `addSubIssue` appends,
so creation order *is* the display order under the parent and the order the resolver's phases will
follow. Get it right at approval time; there is no reordering afterwards.

## 7. The slice template

The template **is** the sub-issue body. Title: `<parent#>/S<K> — <behaviour phrase>` — a behaviour,
never a layer, because the title is read in the parent's rollup and on a board's progress hover,
out of context and with no body.

```markdown
**Parent:** #<N> — <parent title>

## Outcome

<One or two sentences: the behaviour that exists once this ships, actor- or business-visible.>

## Why a separate slice

<Why this is a useful delivery milestone on its own.>

## Acceptance criteria

- [ ] **AC-1** — <criterion summary>
  - Given <precondition>
  - When <action>
  - Then <observable outcome>
- [ ] **AC-2** — <criterion summary>
  - Given / When / Then

## Out of scope

<What is deliberately deferred, and to which sibling slice (`<N>/S<K>`) or back to the parent.>

## Grounding

<The sources read and what each contributed: doc + §heading, body/thread passage, dossier source.
Any provisional-default open question carried by the behaviour this slice delivers.>
```

**`## Acceptance criteria`, deliberately not `## Definition of done`.** The DoD heading carries a
contract three skills own — the resolver projects ticks onto it, the evaluator verifies them with
sticky vetoes, the planner reconciles them — and all three operate on the issue the resolver is
running on, which under slice-as-phase is the **parent**. A DoD on a slice would be a checkbox set
nothing ticks. The checkbox form here is the drafter's existing `## Acceptance criteria` shape plus a
stable id per criterion.

**The `AC-N` ids are useful even though nothing ticks them per-criterion:** a plan phase's
`deliverable` line can cite `AC-2, AC-3` in prose, with no grammar change. Stable ids beat positional
references for the same reason §-anchors do.

**Ticking (Tier 1).** The resolver ticks **all** of a slice's criteria at the moment it closes the
slice — its last serving phase shipping — so a closed slice never reads as half-unmet. Per-criterion
ticking as each phase ships (Tier 2) is deliberately **not** built: it would need a seventh key in a
closed phase grammar, a second projection target, slice-scoped annotation forms, and a second
reconciliation axis. **The trigger for revisiting it, with its diagnosis attached:** per-criterion
progress only reveals anything when a slice spans more than one phase — and a slice needing three
phases before it is demonstrable is a slice whose one-sentence demo is straining, so check whether
the cut is too thick *before* concluding the machinery is missing.

## 8. Presenting for approval

Show the operator, in this order:

1. **Grounding summary** — one line per source read, or noted absent, with its authority.
2. **The decomposition strategy** (§4).
3. **The ordered slice list**, one line each: `<N>/S<K> — <title>` + the outcome sentence.
4. **The full slice bodies.**
5. **A closing note**: major technical risks, assumptions made, and anything needing stakeholder
   clarification. A real open question routes out to the drafter, never silently into a slice body.

They may approve, re-cut, reorder, retitle, or drop slices; iterate until approved. Nothing is
written to GitHub during this step.

## 9. Anti-patterns

- **Horizontal slices** — any slice whose title names a layer instead of a behaviour.
- **The issue restated** — one slice that is just the whole issue. If it genuinely cannot be cut, say
  so and explain why rather than pretending otherwise.
- **Uncited slices** — nothing to cite means invented scope (§3).
- **Slice inflation** — more slices than the sources' distinct outcomes justify. Ten or more means
  the cut is sharding tasks rather than sequencing behaviour.
- **Editing the parent body** — slice detail lives only in slice bodies; the parent is never touched.
- **A slice with its own sub-issues** — a slice is never sliced.
- **Inventing failure modes** — operational slices trace to recorded requirements (§5).
