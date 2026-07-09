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

- **Commit:** `a503ddf` (`S3: pipelib primitives + the §3 envelope`).
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

### S21 — GitHub executor ports — ACCEPTED (2026-07-04)

- **Commit:** `246b64c` (`S21: port the four gh executors to Python`).
- **DoD:** all 4 boxes ticked, verified this session.
- **Deliverables:** `scripts/{gh_gather,gh_pr_gather,gh_persist,config_block}.py` (Python ports under
  the §3 envelope, importing `pipelib`) + `tests/test_*.py` + fixtures. v1 `.sh` untouched +
  shellcheck-clean.
- **Contract fidelity:** each preserves its v1 CLI + output field set (gh_persist verified byte-for-byte
  against live v1 side-by-side; config_block round-trips the v1 canonical block forms **byte-identically**
  under adversarial attack). Invariants preserved: empty-body gate → `EMPTY_BODY_FILE` (as a
  `needs_decision` envelope at exit 0 — the v2 envelope form of v1's bare exit 2; the gate is proven to
  run **before** any `gh` write, the #626/#627 guarantee); `body_sha256`; post-new-before-delete-old
  (with an explicit positive call-order assertion); close/reopen idempotency; deps capability-gating →
  `DEPS_UNSUPPORTED` + retry-without; `MARKER_AMBIGUOUS`.
- **Cross-port unification (from review):** inline `thread` is a JSON `str` in **both** gathers
  (conforming to `pipelib.spill`/`envelope_asserts`; gh_gather was corrected to match gh_pr_gather);
  `AUTH_REQUIRED` classified in all gh-facing ports; `config_block.py` made executable.
- **Live smoke (read-only, sandbox):** gh_gather on issue **#4** → `status ok`, marker_comment_count 0,
  deps_available true, `thread`/`issue_body` type `str`; gh_pr_gather on PR **#6** (`--with-diff`) →
  `status ok`, OPEN, diff spilled to path, `thread` type `str`. (Created sandbox PR #6, which also seeds
  the S7 evaluator parity run.)
- **Dual-platform:** 337 tests pass on macOS and in the Linux `python:3-slim` container.
- **Process (fan-out):** 4 port implementors + 1 consolidation fixup; review = 3 reviewers (gathers /
  gh_persist / config_block) round 1 → fixup → 1 gh_gather round-2 reviewer + orchestrator mechanical
  checks (config_block `+x`, gh_persist ordering test). **2 review rounds** (gathers/config_block had
  actionable findings; gh_persist was clean in round 1).
- **Findings resolved:** gh_gather inline-`thread` list→`str` (actionable); `config_block.py` `+x`
  (actionable); advisories folded (gh_gather `AUTH_REQUIRED` for cross-port consistency; gh_persist
  explicit ordering assertion).
- **Carried to S20 (not S21 gaps):** a uniform-`AUTH_REQUIRED` audit note; and a possible
  `stderr_file` field for `tests/shim/gh` — the deps/error stderr-classification paths currently use
  in-process fakes (the shim replays stdout only), which all three reviewers ruled **adequate** for
  S21 (the shim is frozen for S21). A future harness improvement, not required.
- **Deferrals:** none of S21's own DoD.

### S4 — `workspace.py` — ACCEPTED (2026-07-04)

- **Commit:** `e20e4c3` (`S4: workspace.py — worktree lifecycle owner`).
- **DoD:** all 7 boxes ticked, verified this session.
- **Deliverables:** `scripts/workspace.py` (`ensure --work`/`--read`, `remove --work`, `gc`,
  `root-status`, `lint`; root-freshness `ROOT_NOT_ON_MAIN`/`ROOT_DIRTY`/`ROOT_DIVERGED`; `BRANCH_IN_USE`;
  hook execution via `pipelib.hooks` composing `config_block.py` **in-process**; idempotent `.gitignore`
  maintenance) + `tests/test_workspace.py` (63 git-sandbox tests) + the `.worktrees/` `.gitignore` entry.
- **Design calls (reviewer-adjudicated in the implementor's favor):** dirty/unpushed `remove --work` →
  `AMBIGUOUS` (a closed-set code; PRD §4.3 mechanical-blocker card; no §3 amendment needed);
  `config_block` composed in-process via its scan primitives (§2 mandate — subprocessing it would
  violate §1's git/gh-only-spawn rule); root **never auto-fixed** (§12). The v1→v2 hook result-key
  mapping and the malformed-block graceful-degradation divergence are **inlined** into `workspace.py`
  (self-contained — no dangling references to transient artifacts).
- **Manual smoke (orchestrator-run):** `ensure --read main --root .` → `ok`, detached `ro-main` at
  `origin/main`'s SHA; `gc --max-age 0` → removed `ro-main`, root clean.
- **Dual-platform:** 400 tests pass on macOS and in the Linux `python:3-slim` container.
- **Process:** 1 implementor → orchestrator sanity (macOS + Linux + the manual smoke) → 1 opus
  reviewer (PASS, 0 actionable, 4 advisories) → 2 docstring fixups (hook-mapping durability;
  self-containment). **1 review round.**
- **Carried advisories (non-blocking, for later steps):** add a public `config_block.read_block()` API
  to retire the `_private`-function reach; a fresh consuming repo's first `ensure` leaves `.gitignore`
  uncommitted so a 2nd `ensure` trips `ROOT_DIRTY` (one-time bootstrap — surface in S6+/operator docs);
  `gc`/`remove --work` leave the empty `.worktrees/` parent dir (harmless, git-ignored).
- **Deferrals:** none.

### S5 — `parse.py` — ACCEPTED (2026-07-04)

- **Commit:** `fe16977` (`S5: parse.py — the shared body-grammar parser`).
- **DoD:** all 4 boxes ticked, verified this session.
- **Deliverables:** `scripts/parse.py` (`dod` + `dod --render`, `oq-links`, `phases` subcommands over
  a file path, envelope out) + `tests/test_parse.py` (54 tests) + fixtures lifted from the S1/`_shared`
  frozen grammar + adversarial mutations. File I/O only (no gh/git). This ends v1's per-skill inline
  prompt-parsing.
- **Verified (reviewer re-generated evidence):** `dod --render` round-trips **byte-identically** for
  every closed-set annotation form (confirmed against an external byte-oracle); unknown/stacked
  annotations → `DOD_MALFORMED` with no false positives on ordinary prose; all three OQ dispositions
  parse + no-section → `ok` empty list; `phases` parses the plan `## Phases` structured grammar
  (kinds `code-shipping`/`operator`/`decision-only`) with `PHASES_MALFORMED` on malformed (incl. the
  #640 free-form-sequencing regression).
- **Implementor caught + fixed 3 real regex bugs** via adversarial fixtures (prefix outside the
  annotation alternation; a stacked annotation swallowed in a reason field; a `\b` terminator failing
  after `)`), and correctly disambiguated `## Phases` (plan) from `## Phase tracker` (PR body — my
  brief mis-cited the reference; the implementor caught it).
- **Design calls (reviewer-adjudicated):** `oq-links` malformed-entry → `AMBIGUOUS` (the residual
  closed-set code, as S4; strict-parse is faithful to "don't invent/normalize"); `phases` targets the
  plan grammar.
- **Dual-platform:** 454 tests pass on macOS and Linux.
- **Process:** 1 implementor → orchestrator sanity (macOS + Linux) → 1 opus reviewer (PASS, 0
  actionable, 3 advisories). **1 review round.**
- **Carried advisories (non-blocking, semantically lossless — DoD round-trip is byte-perfect for the
  canonical, pipeline-written forms):** `dod --render` normalizes *non-canonical* input (`- [X]`→`- [x]`,
  collapsed inner spaces, a one-leading-space bullet renders at zero indent) — a "parser accepts a shape
  it can't reproduce" edge unreachable from machine writers; a `## Phases` list starting at phase 2
  parses ok (grammar states no "must start at 1"); a future `OQ_LINKS_MALFORMED` §3 code could replace
  the `AMBIGUOUS` reuse. Worth a small hardening when the resolver/evaluator skills (which *use* render
  to write back DoD) are built (S7/S10).
- **Deferrals:** none.

### S6 — `prep_evaluator.py` (the prep-script pilot) — ACCEPTED (2026-07-04)

- **Commit:** `938d618` (`S6: prep_evaluator.py — evaluator facts block (prep pilot)`).
- **DoD:** all 5 boxes ticked, verified this session.
- **Deliverables:** `scripts/prep_evaluator.py` (composes gh_pr_gather + gh_gather + workspace + parse
  + config_block **in-process** into the architecture §4 facts block) + `tests/test_prep_evaluator.py`
  (59 tests, shim + git-sandbox) + fixtures. **Amended `docs/architecture.md` §4** (content-only,
  anchor stable) to match the real evaluator schema (added pr/pr_type/ci/self_review/current_user/
  merge_config; dod/blocked_by/deps_available keyed per closing-issue; replaced the resolver-shaped
  `open_questions` with the evaluator's native `blocked_by`/`deps_available`).
- **Composition pattern (pilot):** in-process, NOT subprocess (§1); prep emits exactly one envelope;
  emit-and-exit executors captured via `redirect_stdout`. Verified: single-invocation budget = 7 gh
  calls (two-sided bound); gate config read at the root main SHA (§12); MARKER_AMBIGUOUS/ROOT_*/
  BRANCH_IN_USE propagate; `--refresh` re-derives CI/PR-state without hook re-runs.
- **Read-only live smoke (real GitHub, sandbox PR #6, on a pristine clone):** `status ok`,
  `target.labels: ['story']`, `workspace.sha == PR head` (cae86c8), `pr_type standard`, `ci green`,
  `self_review True`, `config.sha == root main`. (Labelled PR #6 `story` for the smoke; that label
  stays on the sandbox.)
- **Two shared-layer fixes the pilot surfaced (both actionable, both smoke-verified + re-reviewed):**
  1. **PR labels** — `gh_pr_gather._VIEW_JSON_FIELDS` omitted `labels` (v1 did too, despite the
     evaluator referencing a `labels` array — a latent v1 contradiction), so escalation-label matching
     could never fire. Added `labels` (mapped to name strings), fixing the docstring-vs-code lie;
     `target.labels` now populated.
  2. **workspace `ensure --work` existing-branch bug** — it unconditionally created a new branch at
     `origin/<base>`, so an existing PR branch checked out at `main` (wrong code to evaluate). Fixed
     with 3-case logic (reuse worktree > checkout `origin/<branch>` at its head > create-from-base);
     additive, regression-tested (fail-before/pass-after). This is the fix that made the smoke's
     `workspace.sha == PR head`.
- **S8 RETRO INPUT — composition-API friction (durable record for S8):** the executors have uneven
  composition surfaces — `parse.py` exposes pure `parse_*()→dict`; `gh_gather.run` has a `stream=`
  param + returns; but `gh_pr_gather.run`, `workspace.py` (subcommands), and `config_block.py` (run_*)
  **emit-and-exit with no returnable/stream core**, forcing `prep_evaluator` to use
  `contextlib.redirect_stdout` capture as a *bridge*. **Proposed lock for S8:** every executor exposes
  a pure non-emitting core (e.g. `build_*(...) -> (payload, notices, decision|None)`) and `main()` is a
  thin emit wrapper (the `gh_gather.run(stream=)`/`parse.parse_dod_bullets` shape) — retrofit onto
  gh_pr_gather/workspace/config_block so no later prep (S9/S12/S14/S16/S18) re-implements the
  stdout-capture shim. Also: distinguish "partial-but-honest envelope on failure" (e.g. setup-hook
  failure) from "hard error" as a type-level return distinction; give workspace.py per-subcommand cores.
  Treat the capture-via-redirect_stdout pattern as pilot-only, not the target.
- **Dual-platform:** 517 tests pass on macOS and Linux.
- **Process:** 1 implementor → orchestrator sanity (macOS+Linux) → 1 opus reviewer (CHANGES REQUIRED:
  labels + merge-policy-coverage) → labels fixup → live smoke surfaced the workspace bug → workspace
  fixup → live smoke (pristine) PASS → 1 opus re-review (PASS). **2 review rounds.**
- **Deferrals:** none. Advisories carried: `vector.pr_state` self_review conflation (glance at S15);
  the one-time `.gitignore` bootstrap dirties a fresh consuming-repo root (surfaced in the smoke as a
  correctly-propagated `ROOT_DIRTY` on a re-run — operator commits `.gitignore` once).

### S7 — Evaluator skill rewrite — ACCEPTED (automatable 2026-07-04; live parity 2026-07-05)

- **Commits:** `25be0a5` (automatable build) + the operator-run live-parity commits `11cb5cb` (S1
  standard approve+merge), `031027a` (S2 story merge), `6ea339b` (S3 red-CI rejection), `693f195`
  (S4 ask-policy gate + **box 6 ticked**). (`ae283af`, the SANDBOX config-block seed fix, landed
  between S1 and S2.)
- **Status:** **7 of 7 DoD boxes ticked.** Box 6 — the live 4-scenario parity run — is complete:
  **all four scenarios PASS with zero unexplained divergences**, recorded per scenario in
  `docs/specs/parity/evaluator.md` with a filled Go/no-go block (**Accepted — go**). Verified this
  session (2026-07-09) from the committed parity doc + `git log`: box 6 `[x]`, four `Verdict: PASS`,
  four recorded runs, tree clean at `693f195`.
- **Parity (operator-run, headless/`!`-driven on `danwashusen/gh-pipeline-sandbox`):** twin fixtures
  per scenario (independent parents for destructive mutations); each confirmed schema-identical
  persisted artifacts (cross-consumable both directions), identical gate sets, schema-valid v2
  handoffs, and **one** `prep_evaluator.py` state-assembly call with **0** sub-agents (v1: 4–6
  `github-ops` + 2–3 GATHER). Every divergence traced to the v1→v2 rename, free prose within the
  shared schema, GitHub behavior, or an identical run-time environment substitution.
- **Deliverables:** `skills/evaluator/` authored **from scratch** — `SKILL.md` router (103 lines; the
  4 §9 sections; a visible `vector→playbook` table; `name: evaluator` / `model: opus` / `effort: xhigh`)
  + `playbooks/` (evaluate-spine 320 + standard 51 + story 95 + epic-integration 65 — the §5-bar split
  is a **shared spine + 3 thin post-verdict variants**, zero PR-type conditionals) + `references/`
  (health-cache / review-comment / delivery-log / handoff renderings byte-compatible per `_shared` +
  the S1 examples; the carried test-selection sub-agent prompt) + `tests/test_evaluator_routing.py`
  (23 tests) + `docs/specs/parity/evaluator.md` (metrics + the 4-scenario parity scaffold).
- **Automatable DoD verified (reviewer PASS, 0 actionable):** router 103 ≤150; router+largest 423
  ≤485; artifacts byte-diff clean vs S1 examples; grep gates clean *per intent* (see adjudications);
  frontmatter pins verbatim; all 10 `specs/evaluator.md` operator gates present; census 81 tokens,
  zero drops.
- **Three gate-interpretation adjudications (reviewer-ruled; precedent for the 6 remaining cutovers):**
  1. Artifact footers keep `github-pr-evaluator` — **required**: the S1-frozen example itself contains
     `_Cached by github-pr-evaluator._`, so byte-compat requires it; it's provenance prose readers
     don't parse, not a skill-invocation name.
  2. `gh pr merge` / `gh pr ready --undo` — acceptable **scriptless raw-`gh` executors** (no
     `gh_persist` merge op; spec-named). **→ S8 must amend architecture §10** (the flat "zero raw `gh`
     invocations" → the narrower §7-rule-7 "no raw `gh` write/fetch-envelope ops that *have* a script",
     excepting the scriptless merge/ready executors) so S20's validator regex is authored right.
  3. `git show <end>` — a legit single-commit diff view, **not** the banned `git show <ref>:<path>`
     ref-arithmetic. **→ S20's git-show validator must be ref:path-scoped**, not blanket `git show`.
- **Advisory:** a *story* session loads router+spine+variant = 518 (the DoD metric router+largest = 423
  is met; each file fits one Read). Disclosed in the parity doc; watch larger future spines.
- **Process:** 1 opus implementor (skill authoring) → orchestrator sanity (line counts / grep / census
  / 540 tests) → 1 opus reviewer (PASS, 0 actionable, 3 forward advisories). **1 review round.**

### S8 — Pilot retro & pattern lock — ACCEPTED (2026-07-09)

- **Commit:** `8a43db0` (`S8: pilot retro & pattern lock — pure executor cores, retro, architecture
  amendments`).
- **Scope:** the DoD's two doc boxes plus the code retrofit — S8's goal sentence ("correct the
  shared patterns **while exactly one skill uses them**") and the S6-recorded retro input both
  mandate landing the composition lock now, before the S9/S12/S14/S16/S18 preps are built.
- **D1 — composition retrofit (the pattern lock):** every prep-composed executor now exposes a pure
  non-emitting `build_*(...) -> (payload, notices, decision|None)` core with `main()`/`run_*` as thin
  emit wrappers — `gh_pr_gather.py` (`build_pr_facts`), `workspace.py` (six per-subcommand cores),
  `config_block.py` (four cores). `prep_evaluator.py` composes the cores directly and forwards a
  returned `decision` to a single emitted envelope; the S6 `contextlib.redirect_stdout`/`io.StringIO`
  capture bridge is retired (a minimal `_DiscardStream` sinks the one sanctioned
  `gh_gather.run(stream=)` emit). **Byte-identical envelopes proven:** `tests/` untouched, fixtures
  unedited, 540/540 green on macOS and Linux (container).
- **D2 — retro:** `docs/specs/baseline.md` gains `## 5. S8 pilot retro & pattern lock` — the
  composition friction → adopted lock + the S9+ rule (preps compose cores directly; no new prep may
  reintroduce stdout capture), the two closed S6 shared-layer fixes (labels; `ensure --work`
  existing-branch), the S7 routing-bar confirmations + three gate adjudications as precedent for the
  six remaining cutovers, the census 79→81 growth reconciliation (S7's own additions, zero drops),
  and the go/no-go as recorded.
- **D3 — architecture amendments (content-only; all `## §N` anchors byte-stable):** §2 specifies the
  pure-core/thin-emit-wrapper composition pattern (S6 bridge marked pilot-only, retired); §10
  narrows two prompt validators for S20 — the raw-`gh` rule to the §7-rule-7 form excepting exactly
  the scriptless `gh pr merge` / `gh pr ready --undo` (behavior-cited to `specs/evaluator.md` :195
  merge-execution and :144 draft-flip rows), and the git-ref rule to ref-arithmetic scope
  (`git show <ref>:<path>` / `git grep <ref>` banned; bare `git show <commit>` permitted); §12's
  drift-class invariant row reconciled ("carve-outs in §10"). §3–§5 needed no amendment (S7 parity
  contradicted nothing); `prd.md` untouched.
- **Go/no-go (box 3 — recorded, not decided):** **Accepted — go**, per the operator's
  `docs/specs/parity/evaluator.md` "Go/no-go (S8 input)" block; criteria restated with status in
  baseline §5.4, all met.
- **Reviewer rulings of record (both flagged judgment calls ACCEPTED with falsification attempts):**
  `_DiscardStream`'s write/flush surface is complete against `pipelib.envelope.emit`'s actual stream
  use (no `.buffer` path taken; spills go to files, never the stream); the workspace cores'
  hard-git-failure `sys.exit(1)` is process-identical to HEAD, and the setup-hook-failure case that
  must *not* exit rides in `payload` (`setup.succeeded: false`), preserved.
- **Process:** 1 opus implementor → orchestrator sanity (compileall / 540 macOS / 540 Linux /
  shellcheck / jq / census byte-identical / anchors) → 1 opus reviewer (PASS, 0 actionable, 3
  advisories) → fix round 1 (§10 citation truth-fix to behavior citations; census-growth sentence;
  the same citation error fixed where the retro restated it) → reviewer re-verify (**PASS holds;
  advisory 1 resolved; no advisories remain**). **1 fix round.**
- **Session-mechanics:** this session (2026-07-09) had the named `implementor`/`reviewer` agent
  types available and used them directly (`subagent_type: implementor|reviewer` + opus override for
  both S8 roles) — the prior session's `general-purpose` workaround is no longer needed.

### S9 — `prep_resolver.py` — ACCEPTED (2026-07-09)

- **Commit:** `9f34931` (`S9: prep_resolver.py — resolver startup facts in one call`).
- **Deliverables:** `scripts/prep_resolver.py` (the resolver's ~130 lines of v1 prompt-side startup
  assembly in one call) + `tests/test_prep_resolver.py` (65 tests) + 18 fixture dirs. Facts block:
  `target` (issue + native deps), `vector` (`type` epic/story/standard; **`mode` is a three-value
  closed set `continue` / `gated` / `fresh`** + `prior_pr_row` from the 7-row v1 step-5 table;
  `vector.gate` carries the operator card `{reason, header, options, prior_pr}` verbatim for gated
  rows), `plan` (marker/SHA/staged body), epic facts (discovery zero/one/multiple→`AMBIGUOUS`;
  6-step bootstrap slug), story parent-epic search, `branch` (collision `-vN` suffixing),
  `phases`/`dod` (via `parse` cores), `open_questions` + **top-level `open_questions_gate`
  `{blocked, blocking}`** (Tier-1 tracker join; `question-decision:v1` clears), per-mode
  work/read workspaces, `config` pinned at root main SHA (three resolver blocks + fallback chain),
  `distiller_bundle` (always staged paths, reusing gather spill), `suggested_playbook`,
  `attention`, `prior_pr.stale_cutoff_days` (= 14, a **chosen deterministic default** — v1 says
  only "a long time"; surfaced as a fact, boundary-tested time-invariantly).
- **Composition:** pure cores per the S8 lock (zero stdout capture — first post-lock prep); three
  prep-owned direct calls for genuinely uncovered queries (`git ls-remote`, `gh issue list --label
  epic`, `gh pr list --state closed`). Call budget **two-sided: exactly 5** gh calls canonical /
  **exactly 4** when an open PR short-circuits the closed-PR search.
- **Live smoke (read-only, sandbox):** epic #1 (zero-match discovery → bootstrap slug
  `sandbox-parity-fixture`, `epic.md`) + story #2 (`story.md`; parent-epic search legitimately zero —
  the seeded epic body never references `#2`, a SANDBOX.md seed gap noted, the one-match path is
  proven offline). Zero GitHub writes (`ls-remote` before/after identical).
- **Hermeticity incident (orchestrator sanity catch):** the original submission was green on macOS
  but **596/598 in the Linux container** — `RefreshModeTests` defaulted `--root` to the real
  checkout, so `git ls-remote` hit the live SSH origin (silently *succeeding* on a networked mac —
  the worse failure shape). Fixed test-side (git-sandbox origins, a misnamed invariant corrected,
  +1 positive collision-re-derivation test). **Authorized deviation (recorded):** the orchestrator
  authorized one shared-harness edit outside the add-only boundary — `NETWORK_POISON_ENV` in
  `tests/support/shimenv.py` (GIT_SSH_COMMAND/GIT_PROXY_COMMAND=false, http(s)_proxy→127.0.0.1:1,
  `extra` wins last) so every `intercepted_env()` fails loudly on any live network call
  (architecture §10 now structurally enforced on the shared path). Reviewer ruled the guard sound;
  bypass class (env builders not using `intercepted_env` — none exist today) noted.
- **Review (1 opus reviewer, 1 fix round):** CHANGES REQUIRED — **1 actionable**: the
  open-PR-by-another-author rows (and foreign drafts, via an isDraft-before-authorship ordering
  bug) classified `continue` and **eagerly created a work worktree on a fabricated branch named
  after the other author's PR**, pre-empting v1's operator gate (Review/Comment/Wait ·
  Take-over/Start-fresh) and handing S10 a misleading workspace fact. Fixed: authorship checked
  before draft state; `gated` mode skips branch computation + work-workspace ensure entirely;
  the gate card fact renders v1's row semantics. Re-verified by the reviewer running the fixtures
  itself → **PASS**; DoD box 1 re-verdict verified for all 7 rows (`closed-resolved → fresh` ruled
  acceptable: anomalous-state row, mode never fabricates work for a closed issue).
- **Rulings of record:** blocked-OQ → `comment-only` is v1's blocked outcome (not a re-route that
  hides the gate — prep skips the worktree and surfaces the gate facts); the
  `config_block._read_lines_or_empty`/`_scan_marker` composition is the same surface
  `prep_evaluator` uses (within the S8 lock); the closed-PR resolved rule (`merged` AND issue
  `CLOSED`) is faithful to v1's two rows; OQ-excluded canonical call-budget framing is defensible
  (O(n)-per-OQ tracker fetch disclosed).
- **Carried advisories:** (a) `_read_block_anywhere` is duplicated between the two preps —
  promote to a shared helper at **S12** (the third prep); (b) **S10's brief must carry:**
  `audit_ref` is a BARE ref (`origin/`-prefix before any git/distiller use;
  `read_workspaces.audit.ref` is the prefixed handle), the `vector.gate` card contract, and the
  three-value mode closed set; (c) the network poison covers the `intercepted_env` path only.
- **Dual-platform:** **605/605** on macOS and Linux (container), verified by orchestrator and
  reviewer independently.
- **Process:** 1 sonnet implementor → orchestrator sanity **caught the Linux hermeticity failure**
  → 2 remediation rounds (fix + authorized guard) → 1 opus reviewer (CHANGES REQUIRED, 1
  actionable + 5 advisories) → fix round → re-verify (**PASS**). Ticks all 6 S9 boxes.

### S10 — Resolver skill rewrite — PARTIAL (automatable work done + committed; live legs PENDING) (2026-07-09)

- **Commit:** `806f883` (`S10: skills/resolver/ — resolver cutover + create-pr write path`).
- **Status:** **5 of 7 DoD boxes ticked** (1, 2, 4, 5, 7). **Box 3 (live in-scope-blocked refusal)
  and box 6 (the four live parity runs) are operator-gated and REMAIN unticked** — the run's second
  hard stop. S11 does not start until they close.
- **Deliverables:** `skills/resolver/` authored from scratch — `SKILL.md` router (128 lines; §9
  sections; visible `vector → playbook` table; `model: opus` / `effort: xhigh` pins verbatim) +
  `playbooks/` (**4 routable + 1 shared spine**: `resolve-spine.md` 177 read by standard + story
  only; `standard.md` / `story.md` thin variants; `epic.md` / `comment-only.md` standalone — zero
  cross-type conditionals, grep committed as `PlaybookInterleavingGrepTests`) + `references/` (the
  four carried v1 sub-agent prompts with path-inputs swapped to facts/workspaces — the issue-audit's
  ref-arithmetic fully replaced by `read_workspaces.audit.path` plain reads; DoD-projection forms
  **byte-identical** to the S1 capture; 9 handoff shapes — fixing v1's "seven" miscount; retry
  ladder / follow-up tracking / epic flow / epic baseline) + `tests/test_resolver_routing.py`
  (27 tests) + `docs/specs/parity/resolver.md` (metrics + 4 parity scenarios + the box-3 refusal
  seeding recipe, all operator-marked). Budget: router+largest **305 ≤ 584** (half of v1's 1169).
- **Authorized shared-layer extension (S6 precedent; architecture §2 "extend a script"):**
  `gh_persist.py` gained **`create-pr`** — v1 hand-rolled `gh pr create` (a Rule-7 divergence the
  spec flags); the v2 write path was missing the resolver's central output. Additive only (72
  insertions, 0 deletions; existing ops byte-identical; existing tests unmodified): staged-body
  path + leading empty-body gate, `--title`/`--base`/`--head` required + explicit (no cwd
  inference), `--draft` (v1 opens multi-phase PRs draft — SKILL.md:896), `--dry-run`, receipts,
  AUTH_REQUIRED classification. 20 new tests; the implementor's `PrCreateGapTests` (built to fail
  loudly when the op appeared) flipped to `PrCreateContractTests` pinning the four playbook
  invocation shapes.
- **Authorized architecture amendment (same-commit contract-change rule):** §10's raw-`gh`
  carve-out grew **two → three** sanctioned scriptless executors — added the resolver's
  `gh pr ready <N>` **draft→ready flip** (spec invariant at `specs/resolver.md:213–216`: flip
  immediately before the last-phase handoff or the evaluator's draft-PR guard deadlocks; carried
  from v1 SKILL.md:896), behavior-cited like the evaluator's two; §12's enforcement cell kept
  consistent. Anchors byte-stable. `baseline.md` §5.3(b) untouched (frozen S7-era record).
- **Review (1 opus reviewer, 2 delta rounds, 0 actionable):** PASS. Rulings of record:
  (a) "exactly four playbooks" = 4 routable + 1 non-routable spine — the S7 precedent, faithful;
  (b) the draft→ready flip was a NEW uncarved raw write under §10's then-wording — fixed in-step
  (above), the test comment citing §10 is now true; (c) `create-pr` correctly follows
  `gh_persist`'s existing `_cmd_*` shape — the S8 pure-core lock is composition-driven and
  `gh_persist` is playbook-called via Bash, never prep-composed (a full retrofit is legitimately
  deferrable); (d) the issue-audit ref-arithmetic swap is complete (residuals are provenance +
  negations); (e) census 81 → **83**, zero drops, +2 legitimate (`github-pipeline:drafter`,
  `github-pipeline:evaluator` — resolver next-commands).
- **Carried advisories:** (i) the interleaving grep is a real but **partial** guard (misses
  if-without-else and declarative parallels — the zero-interleaving property was verified by
  reading); S13/S15–S19 briefs must not treat a green grep as proof-of-absence and may broaden the
  patterns; (ii) `gh_persist.py`'s full `build_*` retrofit deferred to a future scripts step;
  (iii) routing-test count is 27 (implementor reports said 22/28 — cosmetic).
- **Dual-platform:** **646/646** on macOS and Linux (container), orchestrator + reviewer
  independently.
- **Process:** 1 opus implementor (skill authoring) → gap report (missing PR-create op) →
  orchestrator-authorized extension → orchestrator sanity (646 both platforms) → 1 opus reviewer
  (PASS, 0 actionable, 3 advisories) → authorized §10/§12 amendment → reviewer delta re-verify
  (**PASS holds; advisory 1 resolved**). **1 fix round.**
- **Live-parity fix round (2026-07-10, commit `db2ca73`):** the operator's scenario
  runs surfaced three v2 defects, fixed + re-reviewed (**PASS holds**, 652/652 both platforms):
  - **D2 (blocking — scenario 1 FAIL):** the spine's fresh-PR staging omitted the closing
    keyword v1 mandates (SKILL.md:888) → issue never auto-closes, evaluator's
    `closingIssuesReferences` gate trips. Fixed: S5 mandates `Fixes #<issue>` as the body's
    first line; the S1 spec's Artifacts-written table gained the missing standard/story
    closing-keyword row (a **capture-gap correction**, quote byte-verbatim per the reviewer —
    the pre-existing row covered only epic-integration); 3 regression tests incl. an
    end-to-end dry-run pinning body + title. S6's phase-tick guard byte-untouched.
  - **D4 (upgraded cosmetic → fidelity):** v1 SKILL.md:885 literally mandates
    `--title "Fix: <summary> (#<issue-number>)"`; the spine is now faithful (feeds the
    evaluator's squash-subject derivation).
  - **D1 (scenario 3, low):** `handoff-renderings.md` gained the question-type terminal shape
    per `_shared/handoff-format.md:33` (no plan/research markers, `Audience:` line; `_shared`
    untouched); `comment-only.md` dispatches by the issue's own type; a conflated worked
    example corrected. 3 tests, fence-scoped (verified load-bearing by the reviewer).
  - Scenario records annotate FIXED **without self-certifying a live PASS** — the operator's
    re-run closes them. Carried advisory: `_shared/handoff-format.md`'s question-type rule is
    labeled "(drafter only)"; a second emitter now exists — relabel on the next legitimate
    `_shared` touch.

### Session-mechanics note (the 2026-07-04 session)

The `.claude/agents/{implementor,reviewer}.md` definitions committed in setup are **not hot-loaded**
into an already-running session, so every sub-agent this session was dispatched via the
`general-purpose` type with the committed role file injected by reference and the model tier pinned
to match (implementor → `sonnet`, reviewer → `opus`). The definition files remain the single source
of truth; a **freshly started** resumed session will pick them up by name and can use
`subagent_type: implementor|reviewer` directly.

---

## Handback log

### 2026-07-09 handback — STOP at S10's live legs (second operator gate) — OPEN

The run is stopped at **S10 boxes 3 + 6** (per the stop conditions: parity runs are operator-owned).
Everything automatable through S10 is accepted and committed on `rewrite/v2-implementation`
(**unpushed**; S7→S10 all green, 646 offline tests on macOS + Linux).

**Operator actions (all scaffolded in [`docs/specs/parity/resolver.md`](parity/resolver.md)):**
1. **Box 6 — four parity scenarios** on `danwashusen/gh-pipeline-sandbox`, v1
   `/github-pipeline:github-issue-resolver` vs v2 `/github-pipeline:resolver`, twin fixtures per
   scenario: fresh bug-fix end-to-end; continue-mode re-entry; comment-only; multi-phase tick
   projection. Same headless recipe as S7 (`claude -p "/github-pipeline:<skill> <issue>"
   --plugin-dir <this branch> --model opus --permission-mode bypassPermissions`, fresh clone per
   run; auto-mode blocks nested runs — drive via `!`). Record per-scenario results + divergences in
   the parity doc; every divergence traces to a PRD § or is filed as a defect.
2. **Box 3 — the live in-scope-blocked refusal** (Scenario 5 in the parity doc, with its full
   seeding recipe): seed a sandbox issue with an `<!-- open-question-links:v1 -->`
   `in-scope (blocked)` entry + an open `question` tracker + native `blocked_by`; run the v2
   resolver; it must REFUSE code work with the gate (comment-only path naming the blocking `#Q`),
   no worktree, no PR.
3. Tick boxes 3 and 6 in `docs/implementation.md` (and only those) when the runs pass with no
   unexplained divergence; commit locally (don't push), per the S7 flow.
4. Resume the orchestrator on `rewrite/v2-implementation` — it re-derives state, flips S10 to
   ACCEPTED, and proceeds **S11 → S12 → S13 → …** (S11 sub-agent exception unification is next;
   the S10 sub-agent prompts deliberately carry v1's exception protocol verbatim for it).

**Context the runs need:** the sandbox's config blocks are canonical since `ae283af`; the
`create-pr` op is new in this branch (the resolver's PR-opens go through it — a v1-vs-v2
divergence in *mechanism*, not artifact, expected in scenarios 1/2/4); the S7-era gotchas
(closingIssuesReferences on non-default-base PRs needs the base-swap trick; GitHub auto-ticks
task-list checkboxes on issue close; self-authored PRs 422 on approve) are recorded in the S7
parity doc + your memory notes.

### 2026-07-04 handback — STOP at S7's live parity (first operator gate) — CLOSED 2026-07-09

**Superseded; retained as a pointer.** The operator completed every action it requested: all four
parity scenarios run and recorded PASS (`11cb5cb` scenario 1, `031027a` scenario 2, `6ea339b`
scenario 3, `693f195` scenario 4 + box 6 tick; `ae283af` fixed the SANDBOX.md config-block seeds —
bare forms parsed empty — between scenarios 1 and 2), the Go/no-go block filled (**Accepted — go**).
S7 flipped to ACCEPTED at `b59e56d`; S8 — the step this handback teed up, both of whose recorded
inputs (the composition lock; the §10 amendment) are now landed — is accepted above. The full
original handback text (operator scenario instructions, accepted-steps table through S7) is in git
history at `ff3064f`. The run has resumed the serial order at **S9**; the next planned operator gate
is **S10's live parity run** (or any earlier stop condition).
