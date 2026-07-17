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

### S10 — Resolver skill rewrite — ACCEPTED (automatable 2026-07-09; live legs 2026-07-10)

- **Commits:** `806f883` (automatable build) + the operator-run live legs `fef7f6e` (scenario 5 —
  blocked refusal, **box 3**), `b41da89` (scenario 3 — comment-only), `b7b6d7a` (scenario 1 — FAIL,
  superseded), `0bc3fed` (scenario 2 — continue re-entry), `e9f3297` (scenario 1 re-run — PASS),
  `ed01de4` (scenario 4 — multi-phase + **box 6**), with two in-flight fix rounds `db2ca73` and
  `c47ada6` (below).
- **Status:** **7 of 7 DoD boxes ticked.** All five live legs recorded in
  `docs/specs/parity/resolver.md` with a filled Go/no-go (**Accepted**): scenario 1 fresh bug-fix
  (FAIL → fix → superseding re-run **PASS**), scenario 2 continue re-entry **PASS**, scenario 3
  comment-only **PASS**, scenario 4 multi-phase tick projection **PASS**, scenario 5 in-scope-blocked
  refusal **PASS** (v2-only by box-3 scope). Verified this session (2026-07-10) from the committed
  parity doc + `git log`: 7× `[x]`, five PASS verdicts, Go/no-go Accepted, tree clean at `ed01de4`.
- **Live-parity defects found + fixed under review (the parity protocol working as designed —
  three were invisible offline):**
  - **D2 scenario-1 (blocking):** fresh-PR body omitted the v1-mandated closing keyword
    (SKILL.md:888) → `closingIssuesReferences: []`, evaluator gate would trip. Fixed in `db2ca73`
    (spine S5 mandate + the S1 spec's missing standard/story closing-keyword row — a reviewer-ruled
    legitimate capture-gap correction + 3 regression tests). Live-certified by the scenario-1
    re-run (`Fixes #40` → `[40]`).
  - **D4 scenario-1 (fidelity, filed cosmetic):** v1 SKILL.md:885 mandates
    `--title "Fix: <summary> (#N)"`; spine made faithful in `db2ca73`; live-certified.
  - **D1 scenario-3 (low):** missing question-type terminal handoff variant (per
    `_shared/handoff-format.md:33`); fixed in `db2ca73`.
  - **D1 scenario-2 (low → RULED):** re-route `PR:`-line `review:`/`health:` markers — ruled from
    the contract (+ the frozen S1 capture `handoff-resolver.md:25-26`): **`not run` is conformant on
    every resolver-authored PR line** (the markers are the evaluator's verdict/gate); v1's bare `✓`
    was the off-contract rendering. Fixed in `c47ada6` (intro made unconditional; THREE off-vocab
    worked examples corrected; standard.md inline restatement, story.md via delegation; 4
    fence-scoped tests). Live-confirmed by scenario 4 on both the re-route and last-phase forward.
  - Scenario-1's first-run D1 was **v1** flaking its own single-phase projection (v2 faithful);
    scenario-1-re-run's D5 was fixture-induced (stale salute copies → v2's audit caught a dim-6
    ambiguity v1 missed and auto-overrode via the verified plan — honestly disclosed as a gate
    condition headless mode auto-records).
- **Scenario-4 live certifications:** draft PR + `## Phase tracker` both legs (v2 via
  `create-pr --draft`); per-phase DoD projection **byte-identical** to the S1-frozen form;
  exact-coverage (b1←p1, b2←p2, no over-tick, no sticky-veto re-tick); last-phase
  **`gh pr ready` draft→ready flip** (the §10 third executor) before the forward handoff;
  close-links populated; ≤1 state-assembly call per session; 0 = 0 gates.
- **Final suite state:** 656/656 on macOS and Linux. Census 83, zero drops.
- **Carried advisories:** interleaving grep is partial (S13/S15–S19 briefs must not treat green
  grep as proof-of-absence); `gh_persist.py` full `build_*` retrofit deferred to a future scripts
  step; `_shared/handoff-format.md`'s question-type rule labeled "(drafter only)" — relabel
  "drafter and resolver" on the next legitimate `_shared` touch; the ReRouteHandoffMarkerTests
  off-vocab regex covers U+2713/U+2717 only (broaden if the reference grows).
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

### S11 — Sub-agent exception unification — ACCEPTED (2026-07-10)

- **Commit:** `7b4c3ef` (`S11: unify sub-agent exceptions on architecture §3`).
- **DoD:** all 4 boxes ticked, verified this session.
- **Deliverables:** the four S10-carried resolver sub-agent prompts converged on §3 — **surgical**:
  only `state-distiller-prompt.md` needed edits (two citation surfaces → `architecture.md §3`; its
  three codes were already §3-verbatim); issue-audit / review-loop / test-selection were already
  conformant (byte-untouched, reviewer-verified against their S10 state). The review-loop's
  lowercase `decision_request` kinds ruled a **separate protocol** (the rich card the main loop
  renders), correctly out of §3 scope. `skills/_shared/subagent-decision-signal.md` carries the
  superseded-for-v2 breadcrumb (body verbatim; five v1 citers byte-untouched and still functional
  until S20).
- **The drift-check validator** (`tests/test_subagent_prompts.py`, 11 tests — the S13/S15/S16/S18
  binder): parses §3's closed set from `architecture.md` (slice-scoped so the `DEPS_UNSUPPORTED`
  notice provably can't leak); **discovers v2 prompts by `playbooks/`-subdir presence** (the §9
  anatomy no v1 dir has) — today that's **five** prompts (4 resolver + the evaluator's carried
  test-selection, which passes), auto-binding future cutovers the moment they land while correctly
  excluding the still-v1 question-status reader until S18; asserts codes ⊆ §3 + no old-doc citation
  + no fence-scoped ref-arithmetic; deliberate-violation traces exercise the real predicates (and
  the citation guard fired on a real file during the round — the implementor's first breadcrumb
  draft — proving it bites).
- **Box 4 live smoke (orchestrator-run, read-only):** `prep_resolver.py` against sandbox issue #44
  (continue-mode scenario-4 twin; plan at `3db6044`, 2 phases, bundle staged) → two context-blind
  sonnet dispatches. **Distiller:** full conformant brief (evidence-cited, thread-vs-plan
  `confirms`, phases parsed, no exception). **Audit:** conformant shape with two dimension-2
  BLOCKERs that are **correct judgment** (at `main` the twin's helpers are still buggy — the fixes
  live on unmerged PR #46 — while the DoD cites commits unreachable at the audit ref); the
  text-side and code-side reads corroborated across the read-type seam exactly as spec'd. Reviewer
  verified the record against the prompts' own return-shape definitions.
- **Dual-platform:** **667/667** on macOS and Linux. Census 83, zero drops (stash-diff proof).
- **Process:** 1 opus implementor → orchestrator sanity (both platforms) + orchestrator-run smoke →
  1 opus reviewer (**PASS, 0 actionable**, 2 advisories: one trace-completeness nit; the
  `_REF_ARITH` inheritance note). **0 fix rounds.**

### S12 — `prep_planner.py` — ACCEPTED (2026-07-10)

- **Commit:** `27ab53b` (`S12: prep_planner.py — planner facts + reference-filter fix + reader
  promotion`).
- **DoD:** all 4 boxes ticked, verified this session (reviewer PASS ×2 rounds, 0 actionable).
- **Deliverables:** `scripts/prep_planner.py` (revise detection; the **full 6-row plan-ref table**
  — v1's 5 rows with row 5 split into independently-testable bootstrap/no-parent facts; open-PR-head
  wins unconditionally per v1 precedence; each row yields `plan_ref` + a **read-only** grounding
  workspace `{path, ref, sha}` — the planner never gets a work workspace; the `@<short-sha>` derives
  at the RESULT ref) + epic facts (stories + live states, delivery-log + epic-plan staging) +
  JIT-story facts (`## Story contracts` staged) + revise facts (prior plan staged path + parsed
  `## Phase tracker`, both SHAs no-judgment) + **the Bug (a) mechanism**: `open_question_candidates`
  — a deterministic `--label question` tracker search (query = the OQ's own id per
  `open-question-detection.md` §Matching) for every body entry recorded `(not filed)`, plus an
  unmissable attention line, closing the frozen falsifiable requirement (specs/planner.md:141-168) —
  + grounding-doc inventory inside the read workspace + `suggested_playbook` proposal
  (`standard`/`epic`/`story`, mode as an overlay; `vector.{type,mode,plan_ref_row}` is the real S13
  contract). `tests/test_prep_planner.py` (63 tests) + 15 fixture dirs.
- **Authorized shared-layer round 1 — the reader promotion (S9-carried advisory closed):**
  `config_block.read_block_anywhere` (+ `candidate_config_files`/`find_includes_one_level`/
  `DEFAULT_CONFIG_CANDIDATE_FILES`) is the one shared multi-file config-block reader;
  `prep_evaluator` (5 call sites) + `prep_resolver` (7) refactored to it — pure call-site swaps,
  their test files unmodified and green (byte-identity). Home ruled correct (`pipelib` would
  invert the layer direction).
- **Authorized shared-layer round 2 — the bare-digit `in:body` false-positive fix (live-smoke
  catch, newly-discovered v1 defect):** GitHub's search tokenizes bare digits AND the `#` prefix
  gives **zero** protection (live-verified: both query forms returned the same four false hits for
  issue #2 — PRs containing "Phase 2" prose), so the smoke's `plan_ref` grounded on a stranger's
  branch. Fixed with `gh_gather.references_issue` — a digit-and-word-boundary-guarded `#N` body
  match (`(?<![\w#])#N(?![0-9A-Za-z])`, hex-color/`#2abc`-proof after the review round) or a
  `closingIssuesReferences` hit — post-filtering all four search sites (gh_gather open-PR;
  resolver closed-PR; both parent-epic searches); filter-only fields stripped so envelopes stay
  byte-identical. ~60 fixture updates (S6-labels class), a stranger/genuine mixed regression
  fixture, 16 filter unit tests. **Spec addenda (capture-gap class, reviewer-approved):** planner
  Bug (c) + a resolver Known-bugs bullet record the v1-inherited defect and mark v2's filtering an
  **expected parity divergence** for S13/S15 runs (`gh-gather.sh:80` remains the documented
  still-exposed v1 site).
- **Post-fix smoke:** story #2 → `story-no-open-parent-epic`/`main`; epic #1 →
  `epic-as-target-bootstrap`/`main`; resolver on #44 still `open-pr-yours`/`continue` (true
  positives preserved). Sandbox seed gaps noted for S13 parity prep: epic #1 has **no `## Stories`
  section** (+ the known #2/#3 back-reference gap).
- **Call budget:** canonical exactly **3** gh calls (two-sided); revise-with-open-PR 4; epic +2/story;
  JIT-story 7 (full-gather reuse precedent); Bug (a) +1 per `(not filed)` entry.
- **Reviewer rulings of record:** local `## Stories`/`## Phase tracker` regex scans acceptable (no
  parse.py grammar exists; raw bodies staged as fallback); promotion home correct; spec addenda
  legitimate; `open_prs[0]` without author-priority acceptable (author classification is the
  resolver's concern); the 3-name playbook proposal adequate — the vector fields carry S13
  regardless of names.
- **Carries into the S13 brief:** (i) the Bug (a) prep-search covers only body-recorded
  `(not filed)` entries — the planner prompt must still tracker-search any OQ it newly detects
  mid-plan; (ii) `plan_ref` rides **bare** — S13's footer rendering owns the `origin/` prefix for
  the default branch (never emit a bare `main@<sha>` footer); (iii) hybrid epic+story detection
  (Bug (b)'s scenario) is derivable from the facts; (iv) the sandbox epic needs a `## Stories`
  section seeded for the epic parity leg.
- **Dual-platform:** **747/747** on macOS and Linux. Census untouched (no skills/ edits).
- **Process:** 1 sonnet implementor → live smoke **caught the search defect** → orchestrator-ruled
  blocking + authorized fix round → 1 opus reviewer (PASS, 0 actionable, 4 advisories) →
  advisory-1 guard tightening → reviewer re-verify (**PASS holds, stronger**). **2 fix rounds.**

### S13 — Planner skill rewrite — ACCEPTED (automatable 2026-07-10; live parity closed 2026-07-17)

- **Parity (operator-run, four scenarios, all PASS):** `f5df2e7` scenario 1 (plan-new single — box-1
  SHA equality exact; the resolver's plan reader cross-consumed both legs), `9e8e598` scenario 2
  (plan-new epic — bootstrap row; filed D4-s2), `3b61d97` scenario 3 (JIT story + the bug-(b)
  composite — **boxes 3+4 both legs; the bug-(a) trap defeated twice**; bug (b) did NOT reproduce:
  v1's worked-example half was already fixed by `9e4222e`, so box 3 is a clean both-legs pass),
  `3b12ec3` scenario 4 (revise — HARD path with `close-pr` + the byte-exact supersession close
  comment; **boxes 1/3/4/5 ticked by the operator**; D6 live-confirmed). Go/no-go **GO**, closed
  unconditional 2026-07-17 (closure block in the parity doc).
- **In-flight fix rounds (each reviewed + re-verified):** `387efa9` D4-s2 (truthful
  `story-parent-epic-bootstrap` row — the facts no longer self-contradict); `33bbf4b` D6 (the
  `.worktrees/` exclusion moved to `info/exclude` via `--git-common-dir` — preps re-runnable in one
  clone, guard keeps its teeth, §6 amended) + the **Bug (d)** addendum (v1's composite session
  structurally stalls: its only bootstrap guidance is force-read at Step 12, unreachable at Step 3 —
  source-verified AND live-observed, 2 operator resumes vs v2's 0 gates; composite gate counts
  non-comparable by v1's defect); the final uncommitted round (in the acceptance commit): D4-s4
  (HARD "Start fresh" now closes → re-preps → re-grounds at the row-table ref → posts — a revised
  plan can no longer ground on a dead branch) + D8 per the **operator's adjudication ("tighten")**:
  the falsifiable citation-completeness rule in plan-spine.md S4 (whole-choice citations only),
  landed inside the zero-headroom budget via five precision-preserving in-spine compressions
  (reviewer-verified, no dropped qualifier; spine held at exactly 122).
- **Latent v1 bugs on the spec record from this parity:** Bug (d) above (the 4th of the run) — plus
  the scenario-4 field confirmation that v1's predecessor detection never consumes its own marker.
- **Harness learnings (parity-doc seeding notes):** operator gates are untestable under `claude -p`
  (0-gate fixtures by construction); never pre-check prep inside the run clone.
- **Carried:** the revise.md step-1 rationale says "step 2" where it means step 3 (one-word nit,
  reviewer-specified — next legitimate revise.md touch); sandbox fixture defects queued pre-S15
  (CLAUDE.md unit target points at `scripts/<module>.py` vs `src/`; a config block duplicated at
  lines 9+37); D3 (both legs' footers self-attribute `github-issue-planner`) is **contract-correct**
  byte-compat (S7 adjudication (a)) — never "clean it up".
- **Final suite state:** **822/822** macOS + Linux. Census 85, zero drops.

#### Original PARTIAL entry (2026-07-10, superseded by the acceptance above)

- **Commit:** `d28d87c` (`S13: skills/planner/ — planner cutover + edit-labels/close-pr ops`).
- **Status:** **2 of 6 DoD boxes ticked** (box 2 zero-ref-arithmetic; box 6 line-count record —
  the wholly-offline boxes). **Boxes 1/3/4/5 carry explicit parity language and remain unticked**
  — the run's third hard stop. S14 does not start until the four planner parity scenarios close
  them.
- **Deliverables:** `skills/planner/` from scratch — `SKILL.md` router (129; pins `opus`/`xhigh`
  verbatim) + **spine + four routable playbooks** (`single`/`epic`/`story-jit`/`revise` — the
  plan's mandated names; all four read the spine; story-under-open-epic short-circuits to
  story-jit BEFORE the revise check per v1's Step-2 exception, parentless story → single) +
  `references/` (plan-schema **carried verbatim, byte-identical to the S1 capture**; the reviewer
  prompt rewritten to read-workspace paths — S11-validator-bound and green; handoff renderings
  with the footer rule [`origin/main`-prefixed default branch / bare epic branch + the grounding
  workspace short-SHA] and the **bug-(b) composite epic+story worked example**; revise
  reconciliation on v2 write paths) + `tests/test_planner_routing.py` (36) +
  `docs/specs/parity/planner.md` (metrics + 4 operator scenarios + sandbox seeding notes).
  **The two falsifiable rules:** bug-(a) "(not filed)" only on empty/rejected candidates (both
  search paths named); bug-(b) OQ line in every gated handoff shape.
- **Authorized script touches:** `prep_planner._suggested_playbook` aligned to the four real names
  (+ `parent_epic_open` arg); additive `--oq-query` one-shot candidate lookup (mechanism (ii) for
  newly-detected OQs — option (i) rejected: the planner must not rewrite the drafter's body
  section); **`gh_persist.py` gained `edit-labels` + `close-pr`** (the S10 create-pr precedent;
  additive, 16 new tests, six pre-existing ops byte-identical) — `edit-labels` for the `planned`
  label (docstring names S15/S16 as future consumers), `close-pr` for the HARD-revise close with
  the **byte-faithful `Re-plan superseded this PR` supersession marker staged to the close
  comment**, firing only after v1's preserved three-way gate.
- **Latent v1 bug discovered (the third of the run):** v1's predecessor-PR detection **never
  fires** — its query fetches `--json …,body` only while the marker it filters for lives in the
  close comment (source-derived: v1 SKILL.md:873-878 vs revise-reconciliation.md:49). Recorded as
  an authorized capture-gap addendum in `docs/specs/resolver.md` (row-134 † + a falsifiable
  Known-bugs bullet; reviewer-verified citations; the "never fires" claim confirmed exact). Any
  future v2 predecessor consumer must read close comments, never `--json body`.
- **Review (1 opus reviewer, 1 fix round + 1 authorized micro-round):** CHANGES REQUIRED — **1
  actionable**: a stale pre-extension gap-note in handoff-renderings.md contradicted revise.md
  (would have told the operator to close an already-closed PR); fixed + re-verified, zero stale
  notes remain. Rulings of record: the exactly-at-the-bar budget **251 ≤ 251** is compliant
  (methodology per S10) but **zero-headroom — any future SKILL.md/plan-spine.md line must be
  offset** (test-pinned); `--oq-query` clean; close-pr's comment-as-argv within the §12 invariant
  (the race surface is the prompt boundary — the file crosses as a path); **the S12 filter ×
  S9 predecessor-search contract survives** (filter selects by body issue-ref; marker match reads
  comments — orthogonal); routing precedence v1-faithful; edit-labels no-op semantics correct.
- **Carried advisories:** (i) the resolver-spec addendum has one wording nit (line-878 sentence
  says "filters that fetched body for the marker"; the precise defect is a query/filter data
  mismatch — conclusion + remediation correct as written); (ii) the 251/251 budget pin;
  (iii) S15/S16 reuse `edit-labels`, don't re-propose; (iv) future predecessor consumers read
  close comments.
- **Census:** 83 → **85** (+`github-pipeline:researcher`, +`§6.5`; zero drops). **Dual-platform:**
  **801/801** macOS + Linux. S11 validator green over the new prompt.
- **Process:** 1 opus implementor → gap report (two missing write ops) → orchestrator-authorized
  extensions → orchestrator sanity (801 both platforms) → 1 opus reviewer (CHANGES REQUIRED, 1
  actionable + 4 advisories) → fix round + authorized spec addendum → re-verify (**PASS**).

### S14 — `prep_drafter.py` — ACCEPTED (2026-07-17)

- **Commit:** `f0167ba` (`S14: prep_drafter.py — drafter facts + oq_tracker promotion`).
- **DoD:** all 4 boxes ticked, verified this session (reviewer PASS, 0 actionable).
- **Deliverables:** `scripts/prep_drafter.py` (three-mode vector `new`/`revise`/`epic-revise` —
  spec-faithful: no `--issue` → new/type-null [freeform classification is the router's judgment];
  epic target → epic-revise; else revise with question-type → `question.md`), repo-context
  inventory (templates; labels; PRD 4-candidate-path search per v1 SKILL.md:168), the
  `<!-- drafter-open-question-markers -->` block via the shared reader (+ `heuristics_active`
  fallback), search-before-file OQ candidates + `--oq-query`, revise/epic-revise gathers
  (`references_issue`-filtered; the drafter-specific `closedByPullRequestsReferences`/
  `projectItems` extra-json), the epic-revise checkbox/live-state mismatch **attention** line
  (reports, never reconciles). `tests/test_prep_drafter.py` (59) + 17 fixture dirs. Budget
  two-sided: **new 1 < revise 5 < epic-revise 5+N**.
- **Promotion (the third consumer rule, S12 precedent):** the OQ tracker search →
  `scripts/oq_tracker.py` (single-purpose module; `pipelib` would invert layers); `prep_planner`
  refactored byte-identically (its 69 tests unmodified, green; the `build_oq_query` alias +
  `import parse` shim sanctioned by the tests-unmodified bar).
- **Ruling of record — no root-freshness for the drafter (FAITHFUL):** §12's invariant ("gate
  config read only at the recorded root main SHA, never from a PR head") has a threat model — a PR
  weakening its own gates — that is structurally inapplicable to the root-only drafter (no PR head
  is ever read; v1 grounds on the ambient, likely-dirty tree by design). `root` carries `{path,
  sha}` only; `--refresh` deliberately omitted (nothing to skip). **§6 amended** (one-line
  clarification: the pinning binds workspace-operating skills; anchors stable) so the prose no
  longer contradicts the ruling.
- **S15-authoring flags (carried into the S15 brief):** `config.oq_markers` is NOT trust-pinned
  (ambient read — never treat it like resolver/evaluator gate blocks); the mismatch attention line
  is report-only (the router owns any body write); `suggested_playbook` proposes
  `new`/`revise`/`epic-split`/`question` (epic-split shared by fresh-epic + epic-revise; the real
  contract is `vector.{mode,type}`); referenced-issue + story epic-backlink lookups are flow-time
  (§1), not facts.
- **Live smoke (read-only, 5 targets):** #4 → revise/standard, #5 → revise/question (→
  `question.md`), #58 → epic-revise with both stories correctly state-reconciled, #1 → epic-revise
  with `stories: []` (independently re-confirming the seed gap), new-mode → real block + 15 labels.
- **Dual-platform:** **881/881** macOS + Linux. Census untouched.
- **Process:** 1 sonnet implementor → orchestrator sanity (both platforms) → 1 opus reviewer
  (**PASS, 0 actionable**, 3 advisories; five rulings all favorable) → reviewer-specified
  micro-round (§6 line + dead import). **0 actionable rounds.**

### Session-mechanics note (the 2026-07-04 session)

The `.claude/agents/{implementor,reviewer}.md` definitions committed in setup are **not hot-loaded**
into an already-running session, so every sub-agent this session was dispatched via the
`general-purpose` type with the committed role file injected by reference and the model tier pinned
to match (implementor → `sonnet`, reviewer → `opus`). The definition files remain the single source
of truth; a **freshly started** resumed session will pick them up by name and can use
`subagent_type: implementor|reviewer` directly.

---

### S15 — Drafter skill rewrite — PARTIAL (automatable done + committed; live parity PENDING) (2026-07-17)

- **Commit:** `c1fa3aa` (`S15: skills/drafter/ — drafter cutover + _shared relabel + sandbox
  fixes`).
- **Status:** **1 of 5 DoD boxes ticked** (box 5, wholly offline). Boxes 1–4 carry parity language —
  the run's fourth hard stop; S16 waits on the four drafter scenarios.
- **Deliverables:** `skills/drafter/` from scratch — router 123 (pins `opus`/`high` verbatim; the
  new-mode classification-override rule visible) + **spine + four routable playbooks**
  (`new`/`revise`/`epic-split`/`question`; epic-split serves fresh-batch AND epic-revise, ruled
  within the §5 bar) + carried judgment references (7-dimension reviewer prompt — S11-bound and
  green; templates; renderings). Schemas **byte-identical** to the S1 captures (question-issue,
  open-question-links). The falsifiable OQ-absorption rule with teeth (both search paths, closed
  disposition set, native-dep wiring, "absorbing an untracked OQ silently is a defect").
  `tests/test_drafter_routing.py` (43). Budget **270 ≤ 288** (v1 576).
- **Authorized touches:** the S10-carried `_shared/handoff-format.md` relabel landed (question-type
  rule → "(drafter and resolver)", exactly one line, zero census impact); the S13-queued sandbox
  fixes landed (recipe `scripts/<module>.py` → `src/<module>.py` in both test-target blocks — the
  "duplicated block" was the same wrong path in two distinct blocks, parser-refuted as a whole-block
  dup — live re-seed pushed `6c5f669`, all 11 markers exactly-one-block verified).
- **Ruling of record — the companion write-path refinement:** the v2 drafter patches **no**
  companion `## Tracked in` (reused → a non-destructive `Related to #<build>` comment; newly-filed →
  no back-link) — reviewer-traced as the CORRECT role split (`open-question-links.md:32` assigns
  back-linking to the sweep; machine readers key on the build issue's native `blocked_by`); v1's
  body-patch was an over-reach. Recorded in the parity doc as the expected scenario-4(b)
  divergence. **Mental model for S16–S19: the drafter never back-links companions.**
- **Dual-platform:** **924/924** macOS + Linux. Census 85, zero drops (additions all under
  `skills/drafter/`).
- **Process:** 1 opus implementor → orchestrator sanity (both platforms) → 1 opus reviewer
  (CHANGES REQUIRED: one parity-doc record gap — the refinement was broader than the implementor's
  own framing) → record fix → re-verify (**clean PASS**). **1 fix round (doc-only).**
- **Live parity — Scenario 1 (new bug draft) run 2026-07-17 (operator-launched via `!`; boxes left
  unticked — operator owns the tick).** Fixture: identical informal feedback on a real defect (the
  `src/formatter_a.py` stub formatters, `:11,16,21`), built-in Bug fallback (no repo template),
  filing pre-authorized so gates 0=0 headless. Twin A → v1 filed **#68**, Twin B → v2 filed **#69**,
  both single `bug` label. **PASS on the machine-relevant parity:** v2 startup = 1 `prep_drafter.py`
  call; gates 0=0 both legs; v2's only sub-agent the `Explore` reviewer; forward route
  `Next: /github-pipeline:planner #69` (v2 rename) + `plan: ✗`; no `## Open questions`/no
  `**Open questions:**` line + no fabrication on either (v2 correctly declined the register's unrelated
  `SBX-OQ-21/22`). **Two explained authoring divergences** (details in
  [`parity/drafter.md`](parity/drafter.md) Scenario-1 Result): **Div-1 (D1)** the bodies are not
  section-set-identical — v2 conforms to the built-in Bug template, v1 embellished (`## Summary`
  rename + added `## Root cause`/`## Definition of done`), a v1-side opus latitude divergence (S10-s1 D1
  precedent), v2 the faithful leg; **Div-2 (D2)** v2's handoff rendered `**Filed:**`/dropped the `open`
  state marker/added a `**Snapshot:**` block/inlined the `Next:` command — rendering-time latitude
  against a correct `handoff-renderings.md` prompt, routing substance intact; a v2-only re-run would
  confirm reproducibility vs a systematic regression before D2 is ticked. Scenarios 2–4 (epic split /
  revise / question) still TODO. GitHub was mid "Partially Degraded Service" incident during the run;
  the endpoints the new-mode path uses stayed live. Committed locally (unpushed).
- **Live parity — Scenario 2 (epic split — twins) run 2026-07-17 (operator-launched via `!`; boxes left
  unticked — operator owns the tick).** Fixture: identical informal feedback that *explicitly asks for an
  epic with child stories* (report-generation capability: reporting-core → locale/format-profile →
  CSV/JSON export → personalized greeting header), grounded on the `src/` formatter + greeter helpers;
  making the Epic scope the user's own call is the 0-gate design (no `Issue size` gate to stall the
  headless run). Twin A → v1 filed **Epic #70 + stories #71–#75** (5); Twin B → v2 filed **Epic #76 +
  stories #77–#80** (4). **PASS on the machine-relevant epic-split parity:** both filed one `epic` + N
  `story` in one **hands-off batch** (gates 0=0 — split loop + body review stand in for the gate); both
  **patched the Epic `## Stories` placeholders to real `#NN` links** (v2 via `gh_persist.py edit-body`),
  both patched bodies diff **clean** (**D2**); every Story carries the `**Epic:** #<epic-#> — <title>`
  first-line backlink (**D3**). v2 startup = **1 `prep_drafter.py` call**; write path = 5 `create` + 1
  `edit-body`, **0 raw `gh`**; sub-agents = 2× `Explore` (split-mode + body reviewer, no `github-ops`);
  router logged the **new-mode classification override** (`new.md` → `epic-split.md`, no size gate — the
  epic-split single-playbook routing, S13-scenario-3 precedent). No `## Open questions` on any body (the
  register's `SBX-OQ-21/22` are unrelated) + no fabrication. **Four explained divergences** (details in
  [`parity/drafter.md`](parity/drafter.md) Scenario-2 Result): **Div-1 (D1)** story sets differ (5 vs 4) —
  v1 grepped and filed a prerequisite `#71 fix-formatter-stubs` story + a different order; both
  dependency-valid foundation-then-fan-out splits, opus split judgment on a correct prompt (S10-s1
  precedent); **Div-2** v2 set the **native `blocked by #77`** graph on #78/#79/#80 (capability-gated;
  sandbox `deps_available: true`, so no `DEPS_UNSUPPORTED` fallback) while v1 used prose/order only — a v2
  enrichment, not a regression; **Div-3** v1's Epic added a `## PRD impact` note (extends-not-conflicts),
  v2 omitted it (spine adds it only on genuine tension) — authoring latitude; **Div-4** v2's handoff again
  **dropped the `open` state marker + restructured** the Epic-batch block (routing substance intact,
  v2-renamed `/github-pipeline:planner #76`), **corroborating Scenario-1 Div-2 across 2 of 2 scenarios** —
  reads as an opus handoff-rendering tendency, not a fixture artifact; operator call whether
  `handoff-renderings.md` needs tightening. Scenarios 3–4 (revise / question) still TODO. Committed
  locally (unpushed).

## Handback log

### 2026-07-17 handback — STOP at S15's live parity (fourth operator gate) — OPEN

The run is stopped at **S15 boxes 1–4's parity halves**. Everything automatable through S15 is
committed on `rewrite/v2-implementation` (**unpushed**; 924 offline tests green both platforms).

**Operator actions (scaffolded in [`docs/specs/parity/drafter.md`](parity/drafter.md)):** the four
scenarios — new bug draft; epic split (twins — it patches the epic); revise; question — v1
`/github-pipeline:github-issue-drafter` vs v2 `/github-pipeline:drafter`, same headless recipe
(fresh clone per run, 0-gate fixtures, drive via `!`). **Known expected divergences on record:**
the companion write-path refinement (scenario 4(b) — v2 posts the `Related to #<build>` comment,
never body-patches; confirm the breadcrumb, don't flag the deferral); Bug (c) (the reference
filter); the v2 next-command renames. The sandbox's test-target blocks now point at
`src/<module>.py` (fixed live, `6c5f669`). Tick boxes 1–4 when the scenarios pass; commit locally;
never push; resume the orchestrator — it flips S15 to ACCEPTED and proceeds **S16 → S17 → S18 →
S19 → S20**.

### 2026-07-10 handback — STOP at S13's live parity (third operator gate) — CLOSED 2026-07-17

**Superseded; retained as a pointer.** The operator ran all four planner scenarios (PASS ×4 across
`f5df2e7`/`9e8e598`/`3b61d97`/`3b12ec3`, boxes 1/3/4/5 ticked at scenario 4) with three orchestrated
in-flight fix rounds (`387efa9` D4-s2, `33bbf4b` D6+Bug (d), and the acceptance commit's D4-s4+D8
round) and one operator adjudication (D8 → "tighten"). Go/no-go closed **GO** unconditional. S13
flipped to ACCEPTED above. The run resumes at **S14 → S15 → …**; the next planned operator gate is
**S15's parity** (drafter), with the queued sandbox-fixture fixes landing first.

The run is stopped at **S13 boxes 1/3/4/5's parity halves** (stop condition: parity runs are
operator-owned). Everything automatable through S13 is accepted and committed on
`rewrite/v2-implementation` (**unpushed**; 801 offline tests green on macOS + Linux).

**Operator actions (all scaffolded in [`docs/specs/parity/planner.md`](parity/planner.md)):**
1. **Four parity scenarios** on `danwashusen/gh-pipeline-sandbox` — v1
   `/github-pipeline:github-issue-planner` vs v2 `/github-pipeline:planner`, twins per scenario:
   **plan-new single issue; plan-new epic; JIT story; revise.** Same headless recipe as S7/S10
   (fresh clone per run; drive the nested `claude -p` runs via `!`).
2. **Per-scenario parity halves to confirm** (each scenario's checklist binds them):
   plan comment schema-identical + **planned-at SHA equals the facts grounding-workspace SHA**
   (box 1); the **bug-(b) composite** epic+story handoff renders the `Open questions:` line
   (box 3, scenario 3); the **bug-(a) rule** — no "(not filed)" with a non-empty unconsulted
   candidate list (box 4); all recorded with divergences traced (box 5).
3. **Sandbox seeding first:** epic #1 has **no `## Stories` section** and never references #2/#3 —
   the epic + JIT scenarios need a properly-seeded epic (recipe in the parity doc's seeding
   notes). **Expected divergences already on record:** Bug (c) (v2's reference filter vs v1's
   fuzzy search); v2 applies the `planned` label via `edit-labels` (same artifact, new mechanism);
   HARD-revise closes the PR via `close-pr` with the supersession close comment (v1's own
   predecessor detection is latently broken — see the resolver-spec addendum — so do not expect
   v1 to consume the marker).
4. Tick boxes 1/3/4/5 in `docs/implementation.md` when their parity halves pass; commit locally
   (never push); resume the orchestrator — it flips S13 to ACCEPTED and proceeds **S14 → S15 → …**

### 2026-07-09 handback — STOP at S10's live legs (second operator gate) — CLOSED 2026-07-10

**Superseded; retained as a pointer.** The operator completed all five live legs across six
scenario commits (see the S10 acceptance entry above for the full leg/fix-round record): scenario 5
closed box 3 (`fef7f6e`); scenarios 3 → 1(FAIL) → 2 → 1-re-run → 4 ran with two orchestrated
in-flight fix rounds (`db2ca73` D2/D4/D1-s3, `c47ada6` D1-s2 marker ruling); scenario 4 closed
box 6 and filled the Go/no-go (**Accepted**) at `ed01de4`. S10 flipped to ACCEPTED above. The full
original handback text is in git history at `47d3107`. The run resumes at **S11** (sub-agent
exception unification — the S10 sub-agent prompts deliberately carry v1's exception protocol
verbatim for it); the next planned operator gate is **S13's parity** (or any earlier stop
condition).

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
