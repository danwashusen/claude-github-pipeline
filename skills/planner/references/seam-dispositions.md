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

1. **Epic-shape triage** (`header: "Issue shape"`) — only when several seams are out-of-slice **and**
   the routed playbook's `off-ramp` fact is `offered`: the issue is structurally an epic filed as a
   standard issue. Offer **Split as epic** (recommended — the epic machinery's `## Story contracts`
   + just-in-time story plans is built to hold exactly this seam registry) / **Gate per-seam**
   (proportionate when the epic's standing ceremony — integration branch, delivery log, per-story
   review round-trips — isn't warranted). On "Split as epic", run the off-ramp flow below and stop —
   no per-seam questions.
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

## Off-ramp flow (planning aborted; the issue becomes an Epic)

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
