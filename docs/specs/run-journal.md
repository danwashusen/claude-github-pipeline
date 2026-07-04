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

_(none yet — run in progress)_

---

## Current handback

_(No stop reached yet. When the run stops, the operator handback is written here: accepted steps
with SHAs, the current step and exactly which DoD items remain, the precise operator actions for
each, and the resume instruction — re-run the orchestrator prompt on `rewrite/v2-implementation`.)_
