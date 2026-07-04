# v2 implementation — run journal

Execution log for the orchestrated build of [implementation.md](../implementation.md). One entry
per **accepted** step. Plan state is the union of: ticked DoD boxes in `docs/implementation.md`,
this journal, and `git log` on `rewrite/v2-implementation`. On every (re-)start, the first
incomplete step is derived from that union and the plan's dependency table.

## Standing deviation from the plan

This run executes on a **single working branch (`rewrite/v2-implementation`) with one commit per
accepted step**, instead of the plan's *one issue → one PR per step* model
([implementation.md "How to use this plan"](../implementation.md)). Rationale: the plan assumes a
consuming repo with write-protected `main`; here the orchestrator is building the plugin itself and
an operator reviews the branch as a whole. **Everything else in the plan is followed as written** —
the per-step DoD, the global DoD, the parity protocol, the from-scratch authorship rule, and the
serial execution order all stand. Each step is still: brief → implement → orchestrator sanity check
→ adversarial review → findings loop (≤3 rounds) → accept (tick verified boxes + journal entry +
one commit).

Commit message convention: `S<N>: <imperative summary>`. Any prd.md / architecture.md content
amendment a step legitimately requires rides in that step's commit (anchors stay stable).

## Execution order (strictly serial)

S1 → S2 → S3 → S21 → S4 → S5 → S6 → S7 → S8 → S9 → S10 → S11 → S12 → S13 → S14 → S15 → S16 →
S17 → S18 → S19 → S20. (Serial through S8 is the plan's requirement; staying serial afterward is
this run's choice so the single branch stays coherent.)

## Authorization boundaries (recorded for continuity)

Pre-authorized: all local work + per-step commits on this branch; read-only `gh` live smokes;
creating the S2 sandbox repo (`gh repo create … --private`) and mutating **only** that repo; Linux
test runs via the `tests/README.md` container invocation (Docker is available in this environment).
Never: push this repo, open issues/PRs on this repo, write to any GitHub repo other than the
sandbox, or delete anything outside the working tree and the sandbox.

---

## Accepted steps

> Each entry's own commit SHA is backfilled immediately after its commit (a commit cannot contain
> its own hash), so the SHA lands in the **following** step's commit. The authoritative mapping is
> always `git log` on `rewrite/v2-implementation` (commit subjects are `S<N>: …`).

### S1 — Baseline capture & per-skill functional specs — ACCEPTED (2026-07-04)

- **Commit:** `S1: baseline capture — nine v1 skill specs, census, artifact examples` (SHA backfilled
  next commit — see `git log`).
- **DoD:** all 6 boxes ticked, each verified this session with reviewer-generated evidence.
- **Deliverables:** nine per-skill v1 functional specs
  (`docs/specs/{drafter,researcher,planner,resolver,evaluator,setup,question-sweep,question-resolver,doc-reviewer}.md`);
  `docs/specs/baseline.md` (v1 line counts + contract-token census + the §7 writer/reader
  cross-reference table); `docs/specs/examples/` (17 verbatim examples — 12 §7 artifacts + 5
  pipeline-skill handoffs, each with a `path:line` source link).
- **Baseline census:** **79 distinct contract tokens** over `skills/` + `agents/` (command + verbatim
  output in `baseline.md` §2). This is the frozen reference every later cutover step
  (S7/S10/S13/S15–S19/S20) re-runs and diffs against; it deliberately includes v1-only tokens
  (`§P-IDs`, `GATHER_*`/`PERSIST_*`, `github-pipeline:github-*`) that v2 will legitimately retire.
- **Planner bugs (frozen as falsifiable requirements in `specs/planner.md`):** (a) a tracked OQ must
  be cited by its `#N`, never recorded "(not filed)" (+ the `planned-around`/`provisional-default`
  label-consistency defect); (b) the handoff `**Open questions:**` line must render in composite
  epic+story sessions — re-grounded to current source (`9e4222e` added the worked example; the
  residual S13 requirement is rendering *logic*, not example coverage).
- **Approach — fan-out** (recorded because S1 deviated from the one-implementor/one-reviewer loop
  this run uses elsewhere): 7 extraction implementors + 1 consolidation implementor produced the
  deliverables; **review round 1** = 6 per-skill adversarial reviewers + 1 global reviewer; a
  4-implementor fixup round; **review round 2** = 3 re-reviews (planner/evaluator/resolver) + an
  orchestrator mechanical check of the advisory batch. **2 review rounds** (cap is 3).
- **Actionable findings resolved (all re-verified in round 2):** planner Bug (b) stale grounding
  (predated `9e4222e`); evaluator missing DIRTY/BLOCKED/BEHIND merge-readiness rule + the closed-set
  `skipped (DIRTY|BLOCKED|deferred|verdict)` markers + the pending-CI watch loop; resolver two
  row-count errors (prior-PR table 8→7 **enumerated**, outcome-rubric 12→13). ~9 advisories folded
  in to harden the frozen baseline. **Zero actionable findings survived round 2.**
- **Deferrals:** none — S1 has no operator-gated DoD items.

### Session-mechanics note (applies to the whole run in this session)

The `.claude/agents/{implementor,reviewer}.md` definitions committed in setup are **not hot-loaded**
into an already-running session, so every sub-agent this session was dispatched via the
`general-purpose` type with the committed role file injected by reference and the model tier pinned
to match (implementor → `sonnet`, reviewer → `opus`). The definition files remain the single source
of truth; a **freshly started** resumed session will pick them up by name and can use
`subagent_type: implementor|reviewer` directly.

---

## Current handback

_(No stop reached yet. When the run stops, the operator handback is written here: accepted steps
with SHAs, the current step and exactly which DoD items remain, the precise operator actions for
each, and the resume instruction — re-run the orchestrator prompt on `rewrite/v2-implementation`.)_
