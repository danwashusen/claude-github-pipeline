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

- **Commit:** `3724328` (`S1: baseline capture — nine v1 skill specs, census, artifact examples`).
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

### S2 — Offline test harness — ACCEPTED (2026-07-04)

- **Commit:** `69399c7` (`S2: offline test harness + live sandbox repo`).
- **DoD:** all 7 boxes ticked, verified this session.
- **Deliverables:** `tests/run.py` (stdlib `unittest` discovery + a PATH-interception self-check that
  fails fast if `gh` doesn't resolve to the shim); `tests/shim/gh` (fixture-replaying `gh` stand-in,
  exact-argv match, loud miss diff); `tests/support/poison/gh` (no-real-`gh` tripwire sentinel);
  `tests/support/gitsandbox.py` (temp bare-origin + clone, cleanup on pass **or** fail);
  `tests/support/shimenv.py`; the self-test suite (**25 tests** across
  test_shim/test_no_real_gh/test_gitsandbox/test_run_py); fixtures; `tests/README.md`;
  `tests/SANDBOX.md`. Plus a root `.gitignore` (`__pycache__/`, `*.pyc`).
- **Dual-platform:** 25 tests pass on macOS (Python 3.14.6) **and** in a Debian `python:3-slim`
  container (Linux/GNU userland, git 2.47.3) via the documented `docker run` invocation — proves the
  architecture §9.6 portability requirement, not just asserts it.
- **Live sandbox:** created **`https://github.com/danwashusen/gh-pipeline-sandbox`** (private) and
  seeded per `SANDBOX.md`: 8 labels (`epic`/`story`/`question`/`planned`/`researched`/`audience:×3`),
  issues **#1** epic + **#2/#3** stories + **#4** bug + **#5** question, 11 config marker blocks in the
  sandbox `CLAUDE.md`, grounding docs (`docs/prd.md`, `docs/architecture.md`), and a controllable CI
  gate (fails when `.ci-force-red` is present on a branch). URL recorded in `tests/SANDBOX.md`. This is
  the target for every later parity run + read-only live smoke (S6/S7/S9/S10/…).
- **Process:** 1 implementor (offline harness + both docs) → orchestrator sanity (macOS + the Docker
  Linux leg) → 1 opus reviewer (PASS, 3 advisories) → 1 advisory fixup → orchestrator-run live sandbox
  creation + seed verification. **1 review round.**
- **Findings:** reviewer PASS with 3 advisories, all fixed (shim hit-path guard for a missing
  `stdout_file` → curated `MISS-LIKE:` message via `is_file()`; stale poison docstring path;
  README `os.path.realpath`→`Path.resolve()` wording). Zero actionable.
- **Deferrals:** none.

### S3 — `scripts/pipelib/` + the envelope — ACCEPTED (2026-07-04)

- **Commit:** `<backfilled next commit>` (`S3: pipelib primitives + the §3 envelope`).
- **DoD:** all 6 boxes ticked, verified this session.
- **Deliverables:** `scripts/pipelib/` — `decisions.py` (the 13 closed decision codes + `needs_decision`
  builder + `DEPS_UNSUPPORTED` notice), `hashing.py` (sha256), `spill.py` (threshold precedence
  new→legacy→`25600`), `envelope.py` (build/emit `ok`|`needs_decision`, exit-code constants),
  `process.py` (locked-down runner: arg-lists only, `git`/`gh` only, UTF-8, `shell=False`,
  `AUTH_REQUIRED` via `gh` exit-4), `hooks.py` (the §1 carve-out — the sole `shell=True` call site,
  `workspace.py`-only). Plus `tests/support/envelope_asserts.py` (7 conformance helpers imported by
  later suites), `tests/test_pipelib.py` (118 tests), two gh-auth fixtures, a toy e2e script, and a
  4-line `tests/run.py` change (adds `scripts/` to `sys.path`).
- **Key §12 invariants enforced here:** the drift-check test **parses the 13 codes out of
  architecture §3** and asserts lib==doc (mutation-tested both directions); the runner refuses `str` +
  non-`git`/`gh` by construction (`isinstance` is the first statement); `shell=True` exists only in the
  separate hook executor (AST-verified, not substring).
- **Dual-platform:** 143 tests pass on macOS and in the Linux `python:3-slim` container (0.87s).
- **Process:** 1 implementor → orchestrator sanity (macOS + Linux) → 1 opus reviewer (PASS, 0
  actionable, 3 advisories). **1 review round.**
- **Carried notes (not deferred DoD):** adv-1 — harden the AST `shell=` guard to also reject a
  non-literal `shell=<var>` kwarg; adv-2 — `process.run` defaults `cwd=None`, so S21/S4 callers must
  pass explicit `cwd` (or `git -C`). Both carried into the S21 brief. No DoD item deferred.

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
