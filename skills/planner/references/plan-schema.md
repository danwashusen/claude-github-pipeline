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

## Section ownership and size

Each fact has **one owning section**; every other section that needs it **cites it by name** rather than restating its substance. `## Doc grounding` above already states this rule for itself; it generalises to the whole schema. The three sections that otherwise converge on the same material carry disjoint obligations:

- `## Doc grounding` — the citation and what it constrains. No rationale, and no restatement of the decision it grounds.
- `## Architecture decisions` — the decision, its rationale, its precedent. No doc summary (cite the `## Doc grounding` entry), and no restatement of the invariant it implies.
- `## Risks & watchpoints` — the runtime invariant the resolver must preserve, naming the decision it follows from rather than re-deriving it.

A cross-reference is a section name, not a paragraph: "per `## Architecture decisions`" is the whole citation. Restating a fact in a second section is the failure this rule exists to prevent, and it is invisible section by section — only the aggregate shows it.

**Delivery status is not plan content.** A plan states what is to be built; what has *already* shipped is owned by the epic delivery log and, for the contract itself, by a merged story's `shipped:` clause in `## Story contracts`. No other section carries a per-story delivered marker — no `✅ Delivered #<N>`, no "already on the epic branch", no shipped-versus-remaining split inside a bullet. This is the same cite-don't-restate rule across artefacts rather than across sections, and it is the one restatement the section-by-section read cannot catch, because each mark is three words: at the point a plan carries the status of every story under it, it has become a second, informal delivery log that every revise must re-verify and no consumer parses. Where a bullet genuinely needs the distinction — a surface a later story still widens — state the *remaining* work, which is the plan's own content, and let the story number carry the rest. One carve-out: the `## Risks & watchpoints` **false-positive trap** entry names what already resolves through a shim or dual-emit precisely so a green run is not read as proof. That is a trap for the resolver, not a status report, and it stays — the test is whether removing the line would let the resolver believe something false, not whether the line mentions what shipped.

**Retirement: a merged story shrinks the plan it came from.** An epic plan is written once and revised as its stories land, so its only bound is what each merge takes back out — applied per merged story, mechanically, on the revise that follows (`playbooks/revise.md`). The story's `## Story contracts` entry keeps `delivers` / `consumes` verbatim as pinned and gains `shipped:`. Every other section loses that story's delivered status outright, after the promotion check — a delivered bullet often carries a decision the plan still binds, so promote the decision and drop the status. A `## Deviations from project docs` entry whose scope has merged compacts to what still binds the *unbuilt* stories, plus a pointer to the record that settled it: a deviation is live plan content only while something is still being built against it. A `## Doc grounding` citation no unmerged story reads any more goes with it. The section grounds the plan that remains, not the plan that was.

**Compaction is narration-only — it never removes an anchor another reader verifies.** Two of them, and both produce a BLOCKER on *every* subsequent revise if compaction takes them: a compacted `## Deviations` entry keeps its `<what deviates>` clause and its `agreed with user <date>`, because Dimension 1 reads an undeclared contradiction as an **undisclosed deviation** and a merged story's decision survives in `## Architecture decisions` by the promotion step above; and a `## Doc grounding` citation is droppable only when **no surviving entry cites it**, because Dimension 6 reads a `DEVIATION (agreed <date>) → see Deviations` or doc-section citation with nothing behind it as **fabricated**. What compaction removes is the paragraphs of argument, never the clause a citation resolves to. This is the same hazard the `shipped:` pointer's additive rule guards in Dimension 5's graph, in three more dimensions.

**Altitude: an epic plan is not the union of its stories' plans.** `## UI decisions`, `## Changes (file-level)` and `## Test plan` are the sections that leak, because story-altitude material is always *true* — it just has an owner, and the owner is the just-in-time story plan authored against current epic HEAD (`playbooks/epic.md`). At the epic grain each is restricted to what no single story owns: a UI decision binding on two or more stories, a shared surface named at directory/module grain, an integration or system test that exercises the stories' convergence. A file, control or suite one story owns belongs in that story's plan, where it will be grounded on the code as it actually stands when that story is planned — not on the epic snapshot, which is stale by the second story. `## UI decisions` is already omittable, but `## Changes (file-level)` and `## Test plan` are not, and this rule can legitimately empty them — an epic whose stories share no directory-grain surface and need no convergence test. Render each such section with the single line `- (none — story-owned)` rather than omitting the heading or padding it: the heading is parsed, and the preamble's "never pad" is what the line satisfies.

**Size.** A comment body cannot exceed **65,536 characters**: GitHub rejects the write at both the GraphQL and the REST endpoint, so an over-cap plan can be neither posted nor edited in place. Count **characters**, not bytes — the write receipts report `body_bytes`, which for non-ASCII text runs ahead of the character count the limit is actually measured in. Read the size from the `size` block `parse.py phases` returns on every staging (S7), fresh draft included — on a relocating revise `plan_shipped.py check`'s `main` block is the same fact — never a hand count. **The cap is the only size line**: below it (`over_limit` false) the plan's length is its own, and you do not cut for size. There is deliberately no lower budget — a sub-cap threshold is read as a target, and the session trims toward a number it computed instead of planning (#959: a 38k-character story plan was cut toward an earlier 32,768 budget twice in one revise, the second time to offset content the reviewer had asked for). Restatement is found by the ownership rule above and the reviewer's audit of it, which runs on every plan whatever its size: apply its findings, and never offset a reviewer-requested addition by cutting elsewhere. Only when `over_limit` is true, compact: on a revise with shipped phases, relocate first (**Shipped phases leave the main comment**) — a multi-phase plan's bulk is often accumulated shipped detail, not restatement. Then look for a fact being restated. Find the restatement; do not trim every section evenly to fit.

**Shipped phases leave the main comment.** A story or single-issue plan cannot retire a shipped phase the way an epic retires a merged story: a shipped phase is pushed but not yet evaluated, and the evaluator judges the whole PR against these sections. So on every revise, each ticked `code-shipping` phase's `## Changes (file-level)`, `## Data model / schema impact` and `## Test plan` entries move **verbatim** into that phase's own `<!-- implementation-plan-shipped:v1:phase:<N> -->` record comment, and each section that lost entries keeps one pointer bullet in their place (`- Phases 1–6 shipped on #903: entries in the shipped-phase records.`). `## Phases`, every decision section, and any entry an unshipped phase still builds on stay here. A single-line `- Unit: a_spec, b_spec` bullet naming several phases' suites is such a shared entry, so a multi-phase plan writes one sub-bullet per suite under each `## Test plan` kind line. The format and invariants are [`../../_shared/plan-shipped-phases.md`](../../_shared/plan-shipped-phases.md)'s; the procedure is [`shipped-phase-relocation.md`](shipped-phase-relocation.md)'s.

## The `sub-issue:` phase key   (multi-phase, non-epic target that already has sub-issues)

When the target already has **sub-issues**, they are its **deliverable slices** by construction: the hierarchy is epic → story → slice, so the sub-issues of a *non-epic* target are slices (an epic's sub-issues are stories, and an epic plan carries no `## Phases` at all). Each `## Phases` entry then carries a sixth key naming the sub-issue it serves, appended after `depends-on`:

```
   - sub-issue: <`#<N>` — the ONE sub-issue this phase serves — or `(none)` for substrate>
```

**Grammar.** `#<N>`, single-valued. The `#` is required: everywhere else here an *issue* is written `#<N>` while a bare int means a DoD index or a phase number, so one spelling per meaning keeps `sub-issue: 3` from reading as "phase 3". `#214, #216` is **malformed, not a shorthand** — a phase serves at most one sub-issue. **Substrate** — groundwork no single sub-issue can demonstrate — is written `sub-issue: (none)`, mirroring `closes-dod: (none)`; it is the only legal way for a phase to serve no sub-issue. An **absent** key is not `(none)`: it means the mapping was never made.

`sub-issue:` is **orthogonal to `closes-dod`** — a phase may serve `#<N>` and still claim `closes-dod: (none)`, and a criterion satisfiable only story-wide is still verified in every phase and claimed by the terminal one, whichever sub-issue that phase serves.

Omit the key entirely when the target has no sub-issues; plans authored before it existed parse without it. The pointer is **one-way, plan → sub-issue**: sub-issue bodies never cite phase numbers, and the planner never files, edits, or relabels a sub-issue. The cardinality rule the phase set must satisfy, the plan-versus-live diff, and the mismatch gate live in [`sub-issue-reconciliation.md`](sub-issue-reconciliation.md).

## The `checkpoint:` phase key   (multi-phase — every `code-shipping` phase but the last)

The resolver ships phases in one session until it reaches a checkpoint, so the plan says, per phase, whether a human reviews that phase's change set before later phases build on it. Each `code-shipping` phase except the **last** one carries the key, appended after `depends-on` (and after `sub-issue` when present):

```
   - checkpoint: <`pause` — the operator reviews this phase's pushed diff before the next phase starts — or `continue`>
```

**Grammar.** Exactly `pause` or `continue`, single-valued. Any other value is `PHASES_MALFORMED` — a typo must not read as either answer. An **absent** key means `pause`: every plan authored before the key existed keeps the one-phase-per-session behaviour it was written for. Omit the key on the last `code-shipping` phase (the session always stops after it — the ready flip and the human-gated evaluator, or the operator phase that follows it) and on `operator` / `decision-only` phases (the resolver cannot run them, so it always stops before one).

**Choosing.** `pause` when the change set wants a human look before anything builds on it:
- security — authentication, authorization, permissions, secrets, input crossing a trust boundary;
- data — a migration, a schema change, a destructive or irreversible operation;
- a contract — a public API, a wire or file format, or the seam a later phase builds on;
- money — billing, payments, pricing;
- a phase that puts a `provisional-default` open question or a `## Deviations from project docs` entry into effect.

`continue` for mechanical, low-blast-radius change sets the resolver's review loop and the evaluator can judge alone — a rename, plumbing, tests, docs. When unsure, `pause`. The choice is the planner's; the resolver may add a stop (its warning signs) but never removes one, and the operator can force a stop after every phase with `--pause`. **On a revise:** each surviving phase keeps its `checkpoint` unless the change to that phase moves it into or out of a `pause` category; a new `code-shipping` phase gets one unless it is the new last `code-shipping` phase; an **unshipped** phase that stops being last (new work appended after it) gains one; and a phase that becomes last drops it. A shipped phase's key is moot — it already shipped — so leave it as it was rather than adding or removing one.

## Phase numbering              (the `## Phases` head line and its reference values)

**Grammar.** A phase head is `<N>. **Phase <N> — <title>**`, and both `<N>` are the **same integer**. The list ordinal and the `Phase N` label are parsed as two separate captures precisely so a renumbering slip is *detectable*, so a disagreement between them is malformed rather than a typo a reader silently repairs. Numbers run **1..n, sequential and non-duplicate**, which makes a phase's number and its position in the list the same fact — there is no way to append an entry numbered 7 and have it sit between 5 and 6. `closes-dod` and `depends-on` values are the literal `(none)` or a comma-separated list of **bare ints**, and nothing else: no prose, no parenthetical, no qualifier. `closes-dod: (none — it re-implements phase 4)` is malformed; that reason belongs in `deliverable`. (Why a bare int and not `#<N>`: the `sub-issue:` phase key above owns that rule.)

**The shapes an author reaches for, all malformed:** `6. **Phase 5c — …**` and its siblings `5a`/`5b`; `6. **Phase 6.1 — …**`; `depends-on: 5c`; a head whose ordinal and label disagree (`6. **Phase 7 — …**`). Every one is the same move — new work has to land *between* existing phases and the author wants the numbers around it left alone. The grammar has no letter, no decimal and no out-of-order integer to spend on that, and the resolver's prep refuses the whole plan with `PHASES_MALFORMED` rather than guess an order — leaving a plan that cannot be executed and, per the footer above, must not be hand-edited. What to do instead is one operation, owned by [`revise-reconciliation.md`](revise-reconciliation.md) ("Inserting a phase after work has shipped").

## The `closes-dod` target       (what a `closes-dod` index points at)

**Rule.** A `closes-dod` index is a 1-based position among the top-level checkbox bullets of the issue body's **`## Definition of done`** section ([`../../_shared/dod-annotations.md`](../../_shared/dod-annotations.md)) — that heading and no other. A checklist under any other heading (`## Acceptance criteria` included) is not the DoD: no parser reads it, so the resolver cannot project a tick onto it and the evaluator cannot verify one. With no `## Definition of done` section, every phase is `closes-dod: (none)`. The facts: `facts.dod` (`present`, `count`, and `other_checklists` — each other `##` section holding checkboxes, the legacy epic `## Stories` excepted), and S7's `parse.py phases … --issue-body "<facts.dod.body_path>"`, whose `dod_coverage` checks the staged plan against them. Fix `out_of_range` (an index past the DoD, or any index when there is none) and `unclaimed` (a DoD bullet no phase claims) in the plan the way you fix `PHASES_MALFORMED` — yours, never a gate; `claimed_more_than_once` is the reviewer's Dimension 7 judgment. `dod_coverage` is `null` for a single-phase plan, which claims no index.

**The DoD-heading card (spine S1).** When `facts.dod.present` is false and `facts.dod.other_checklists` is non-empty, gate before anything else (`header: "DoD heading"`, the `attention` line names the heading and its bullet count; with several headings, one Rename option per heading):

- **Rename to `## Definition of done` (recommended).** Edit only that heading line in `facts.dod.body_path`, then prove it: `${CLAUDE_PLUGIN_ROOT}/scripts/parse.py dod "<facts.dod.body_path>"` must return `ok` with `present: true` and as many `dod` bullets as that checklist's `count`. Apply it with `gh_persist.py edit-body <owner/repo> <issue> "<facts.dod.body_path>"`. The bullets keep their order, so `closes-dod` indexes them as they stand — and on a revise, a live plan that indexed them by eye becomes valid unchanged.
- **Plan without a DoD.** Every phase `closes-dod: (none)`; nothing is projected, and the evaluator judges the checklist by its historical fallback.
- **Re-route to the drafter.** No plan posted, no `planned` label; the abort handoff ([`handoff-renderings.md`](handoff-renderings.md), "DoD heading — re-route to the drafter") points at `/github-pipeline:drafter revise #<issue>`, which renames the heading.

**Why at S1.** The plan reviewer fetches the *live* issue, so a rename has to land before S7 dispatches it — move the card later and the reviewer indexes the old heading again.

**Every issue-body write starts from the body this session last wrote.** `edit-body` replaces the whole body, so each later staging — revise's reconciled body, S8's plan pointer — starts from the last body this session wrote, `facts.dod.body_path` until the first write; never from `facts.sections`' session-start copy, which would write the old heading back over the rename (the resolver spine's same rule, for the same reason).

## Epic-plan and story-under-epic sections

An **epic** plan replaces `## Phases` (single-issue / multi-phase only) with the sections below, in this order after `## Approach`. The epic plan pins the cross-story **contracts** and sequencing; like every implementation plan it is verified and immutable (do not hand-edit — re-run the planner to revise). Child stories are planned just-in-time against it (planner Step 11 + "Just-in-time story planning" mode), not fanned out up front. The *living* record of what each story actually delivered is kept in the **separate** epic delivery log — its own artifact (one comment per shipped story on the epic issue), never in this verified plan (see *Epic delivery log* under the schema below).

```
## Story breakdown            (epic only)
- #<story> "<title>" — <one-line scope>
  (ordered top-to-bottom; this order is the sibling-sequencing source of truth)

## Story contracts            (epic only — the cross-story seams; dimension 5 reads this)
- #<story> — delivers: <type/service/API/file the story produces + intended shape>
            — consumes: <contract delivered by an earlier #<story>, or (none)>
- #<story> — delivers: <the shape as originally pinned — never re-pinned to what shipped>
            — consumes: <as originally pinned>
            — shipped: see the epic delivery log      (merged stories only; third clause)

## Integration strategy       (epic only)
<how the stories converge on `epic/<N>-<slug>` and reach `main`>
```

**A merged story's entry compresses on the next epic revise.** It keeps its `delivers` and `consumes` clauses and gains a third, `shipped:`, pointing at the epic delivery log — and it carries nothing else, per *Section ownership and size* above: what that story actually built is the log's fact, and re-arguing it here is the restatement that rule forbids. Two constraints make the compression safe:

- **The pointer is additive, never a replacement.** Dimension 5 builds its sequencing graph from every entry's `delivers` / `consumes` and treats a `consumes` no entry `delivers` as a dangling-dependency BLOCKER. Dropping either clause in favour of the pointer would make every epic revise after the first merge emit false BLOCKERs.
- **`delivers` stays verbatim as pinned.** The compressing session has the log in hand, so the tempting move is to make the entry agree with it — which silently re-pins the contract to the *shipped* shape. After that, the story-under-epic staleness check compares the log against a copy of itself and can never fire again. Pinned-versus-shipped divergence is the signal; preserving the pinned text is what keeps it visible.

A seam contract pinned by an operator scope cut keeps its `[user decision <date>]` attribution through the compression — dimensions 4 and 6 verify it.

A **story under an epic** uses the standard single-issue schema above — with the `**Epic:** #<epic-#> — <epic title>` backlink as the **first line after** the `<!-- implementation-plan:v1 -->` marker (never above it) — plus this section, which dimension 8 checks against the epic plan and the delivery log:

```
## Epic contract              (story under an epic only)
- Delivers: <contract this story produces, matching the epic plan's ## Story contracts entry for it> — [epic-plan: #<N>]
- Consumes: <contract(s) this story builds on, each already recorded in the epic delivery log, or (none)> — [epic-plan: #<N>]
```

### Epic delivery log (a separate, living comment — not part of the verified plan)

What each story **actually** delivered is tracked in the epic delivery log — one `<!-- epic-delivery-log:v2:story:<N> -->` comment per shipped story on the epic issue, plus a legacy monolithic tier that is read forever and never written again — maintained by the `evaluator` (writer) and read by the `planner` (Just-in-time story planning + Dimension 8). It is **not** part of this verified plan: the plan is immutable, the log changes on every merge. **See [`../../_shared/epic-delivery-log.md`](../../_shared/epic-delivery-log.md)** for its verbatim format and the writer/reader contract.
