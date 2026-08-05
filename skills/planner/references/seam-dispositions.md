# Seam dispositions — inventory, gate, residue, off-ramp

How the planner involves the operator in **seam** decisions (spine S4). A seam is a boundary the
approach must *define* rather than *cite* — an interface, API, module boundary, or data contract that
no codebase precedent and no project doc pins. Early in a project's life precedent is thin, so the
§6.5 decision gate rarely fires — without this step the planner fills the vacuum by inventing
contracts across every seam the issue touches, silently and at scale. Seam scope is the operator's
call, exactly as a tracked open question is a human's call.

## Classify (from the S3 grounding sweep)

Inventory every seam the approach touches, then classify each:

- **defined** — precedent or a doc pins the contract. Cite it and move on; never gate (a gate here
  is noise, not a genuine decision).
- **under-defined** — the contract must be invented; nothing in the repo or docs pins it. Gate.
- **out-of-slice** — the issue's `## Definition of done` does not cover the seam's behaviour, so
  specifying it would decide scope the issue never promised. **Hard-gate**: never post a plan that
  specifies an out-of-slice seam without an operator disposition.

## Gate (two-stage ask)

Conform to [`../../_shared/asking-the-user.md`](../../_shared/asking-the-user.md): one decision per
question, 2–4 options, recommendation as option 1, the auto-appended "Other" absorbs anything the
options omit.

1. **Shape triage** (`header: "Issue shape"`) — only when the seam inventory says this issue is too
   large to plan as one unit, and only for the off-ramps the routed playbook's `off-ramp` fact
   actually offers. Which off-ramp depends on **one** thing: the independence bar the seams clear.

   | Seam inventory | Bar the children clear | Offer |
   |---|---|---|
   | few seams, all inside the issue's DoD | — | nothing: gate per-seam and plan it multi-phase |
   | many increments, each **demonstrable** but sharing one branch and PR | demonstrable | **Slice first** (off-ramp B) |
   | most seams **outside** the DoD, each its own shippable unit | shippable | **Split as epic** (off-ramp A) |

   Offer the apt off-ramp plus **Gate per-seam** (proportionate when the ceremony isn't warranted —
   for an epic that means the integration branch, delivery log, and per-story review round-trips).
   Recommend **Split as epic** when the seams are shippable-independent: the epic machinery's
   `## Story contracts` + just-in-time story plans is built to hold exactly that seam registry.
   Recommend **Slice first** when they are only demonstrable-independent: slices are phase markers on
   *this* issue's branch, so promoting to an epic would buy ceremony the work doesn't need while
   splitting one deliverable across several PRs. On either off-ramp, run its flow below and stop — no
   per-seam questions.
2. **Per-seam questions** — one question per under-defined / out-of-slice seam (`header:` the seam's
   short name), at most 4 seams per `AskUserQuestion` call, further seams in follow-on calls. Offer
   the 3–4 dispositions most apt for that seam:
   - **Pin now** — the operator supplies or approves the contract; plan against it.
   - **Contract only, body deferred** — pin the signature/shape now; the body ships behind it in a
     follow-up. File that follow-up first (below) so the plan cites a real `#M`.
   - **Plan around it** — reshape the approach so the seam is not touched at all.
   - **Own issue** — the seam's definition is its own piece of work; file it (below) and narrow this
     plan. When it genuinely blocks this issue, also link it:

     ```bash
     ${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py link <owner/repo> <N> --add-blocked-by <M>
     ```

   - **It's an open question** — a human outside this session owes the answer: route it through the
     existing `## Open questions` machinery (companion issue + treatment), not a seam disposition.

**Foundation-slot default.** When the target is an epic (or a story under one) whose story set
carries a drafter-filed technical-foundation slot — an opening story whose body defers its content
to planning time — a shared-groundwork seam's home is that story: pin the contract into its
`## Story contracts` entry rather than filing a new issue ("Contract only" / "Own issue" would
double-file groundwork the slot exists to hold). Offer those dispositions only for a seam that
does not belong to the foundation slot.

**Follow-up filing.** A "contract only" / "own issue" answer files its follow-up through the drafter
proxy in [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md) (type hint
`feature`, parent reference `#<N>`) **before S5 drafts**, so every boundary bullet cites a real
issue number — never a dangling "(to be filed)".

## Residue (what lands in the plan)

Record every gated seam's answer — the plan is the resolver's only view of the boundary:

- An `## Architecture decisions` entry attributed `[user decision <date>]` (the §6.5 vocabulary;
  reviewer dimension 6 already accepts it).
- A cut seam (contract-only / own-issue) additionally carries a **boundary bullet** in
  `## Architecture decisions`: "pin the signature of X; do not implement beyond it — body deferred
  to #M". This is the line that stops the resolver helpfully re-expanding scope the operator cut.

No new schema section: the residue rides the existing `## Architecture decisions` vocabulary, so the
resolver's "plan decisions are binding" contract covers it unchanged.

## Off-ramp A (planning aborted; the issue becomes an Epic)

On "Split as epic": stage a **lean** seam-analysis comment to `<facts.scratch>/seam-analysis.md` —
the seam inventory (name, classification, one line each) plus suggested story boundaries, nothing
else. No grounding citations and no draft-plan content (grounding is cheap to redo and the epic
planner redoes it at the right altitude; half-finished plan prose would read as authority to the
drafter). The body must **not** begin with `<!-- implementation-plan:v1 -->` — a marker there would
flip the next planner run into revise mode. Post it through the single write path:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py comment <owner/repo> issue <N> "<facts.scratch>/seam-analysis.md"
```

Then end the session with the **Epic-shaped, planning aborted** handoff
([`handoff-renderings.md`](handoff-renderings.md)): `plan: ✗`, no `Grounding:` line, `Next:` the
drafter revising #N as an Epic. Post **no** plan and **no** `planned` label — nothing was planned;
the comment is the analysis' durable record, and the drafter's prep spills it with the thread, so
the split candidates arrive in that session for free.

## Off-ramp B (planning aborted; the issue is sliced first)

On "Slice first": **post nothing at all** and end with the **Too large to plan as one unit** handoff
([`handoff-renderings.md`](handoff-renderings.md)): `plan: ✗`, no `Grounding:` line, no `planned`
label, `Next:` the slicer on #N.

The asymmetry with off-ramp A is deliberate. The drafter splits *per* the seam-analysis comment, so
that comment is the handover artifact; the slicer instead re-derives its own cut from the repo's
declared grounding docs ([`../../slicer/references/slicing-method.md`](../../slicer/references/slicing-method.md)),
so a planner-authored comment would be a second, staler decomposition proposal competing with it —
and one the operator would have to reconcile. The `Why:` line carries everything the slicer's reader
needs: what makes the issue too large, and why its seams are demonstrable- rather than
shippable-independent.

The slicer hands back here. Its slices then arrive as facts on the next run — `facts.slices` plus the
plan-versus-live diff — and the phase set must satisfy the cardinality rule in
[`sub-issue-reconciliation.md`](sub-issue-reconciliation.md). So this off-ramp is a round trip, not a
dead end, and the second pass plans *against* the approved cut rather than re-deciding it.
