# Parity — the question pair (v1 `open-questions`→v2 `question-sweep`, v1+v2 `question-resolver`)

> Records the [implementation.md](../../implementation.md) **S18** parity run per the parity protocol
> (`## The parity protocol`) and [prd.md §9.5](../../prd.md). The offline work (both routers + their one
> playbook each + the carried/converged references + `prep_question_sweep.py` + `prep_question_resolver.py`
> + tests) landed in S18's implementor pass; the **three live scenarios below are operator-gated** (the
> §8.2 landing gate and the decision gate are interactive `AskUserQuestion`), so an operator runs them on
> the sandbox ([SANDBOX.md](../../../tests/SANDBOX.md)) and fills each result section.

## Naming-collision adjudication — Option A (authorized, riders-bound)

The v2 `question-resolver` skill's name **equals** the frozen v1 skill's name (unique in the rewrite:
every other v2 skill took a distinct new name, so v1/v2 coexist; `question-resolver` is the one v1 skill
whose name already was its v2 target). The collision was two-fold — same dir path (two `SKILL.md`s can't
share it) **and** same registry `name:` during the S18→S20 transition. **Option A** — early-retire only the
v1 `skills/question-resolver/` dir now (a one-dir partial S20) — was **authorized with three riders**:

1. **Retirement is its own labeled first action.** `skills/question-resolver/` (185-line `SKILL.md` +
   71-line `constraint-audit-prompt.md`, 256 deletions) was removed as the first working-tree change; the
   pre-retirement **v1 vantage is `f9f1623`** (the last commit carrying the dir). The v1 behavior is
   preserved verbatim in three places: this repo's git history at `f9f1623`, the S1 baseline spec
   [`docs/specs/question-resolver.md`](../question-resolver.md), and the vantage worktree the resolve+close
   scenario's v1 leg runs against (below).
2. **The parity v1 leg runs against the vantage.** Because the v1 dir is gone from `HEAD`, the resolve+close
   scenario's v1 leg points `--plugin-dir` at a worktree checked out at `f9f1623` (commands in Scenario 3).
   The two sweep scenarios need no vantage — v1 `open-questions` stays frozen in place (no collision there).
3. **Recorded as an authorized, riders-bound §11-adjacent deviation** (deletion-before-parity for ONE dir,
   forced by the name collision, the reference preserved via spec + git + vantage). **S20 note:** S20 will
   find `skills/question-resolver/` already gone — it retires the *rest* of the v1 dirs; this one dir was
   retired early here, and S20's census diff should expect it absent.

## Line-count metrics ([prd.md §10](../../prd.md); the §9 size bar)

**The binding bar for S18 is the architecture.md §9 router bar (≤ 150), not the ≤half-v1 metric.** The S18
plan step's DoD carries **no line-count box** (its boxes are the Tier-1 fixtures, the two landing legs, the
byte-compat/reentrancy, and the names/grep/parity gate). The ≤half-v1 metric is therefore **recorded, not
enforced** here — and it is legitimately **not met**, for a structural reason: v2 **adds** the prd.md §8.2
workspace+landing behavior (sweep) and carries the frozen decision-comment + fold-back renderings
(resolver) onto the **two leanest v1 standalone tools** (147 / 185 lines), where halving leaves no room the
way it did for the 338–1169-line pipeline skills. A test still guards each loaded set against unbounded
growth (a ceiling), and asserts the router itself stays ≤ 150.

| Skill | File | Lines |
|---|---|---:|
| `question-sweep` | `SKILL.md` (router) | 59 |
| | `playbooks/sweep-flow.md` (the one flow) | 62 |
| | **router + playbook (loaded set)** | **121** |
| `question-resolver` | `SKILL.md` (router) | 70 |
| | `playbooks/resolve-flow.md` (the one flow) | 97 |
| | **router + playbook (loaded set)** | **167** |

- **Router bar:** sweep **59 ≤ 150** ✅, resolver **70 ≤ 150** ✅ (architecture.md §9). Each router + each
  playbook fits one default `Read`.
- **≤half-v1 metric (recorded, NOT met):** sweep half = floor(147/2) = **73** (loaded 121); resolver half =
  floor(185/2) = **92** (loaded 167). Rationale above. Pinned informationally by
  `RouterStructureTests::test_loaded_set_under_ceiling_and_half_metric_recorded` in each routing test (a
  ceiling guard + an assertion that promotes the bar to enforced the day a loaded set drops under its half).
- **References (on-demand, not counted):** `question-sweep/references/question-status-reader-prompt.md` 79
  (carried from v1 + converged on §3, below); `question-resolver/references/constraint-audit-prompt.md` 71
  (carried **byte-identical** to the `f9f1623` vantage — architecture.md §9 allows carrying a judgment
  sub-agent prompt a cutover names).

## The prep decisions (the §9 house-default calls the Work records)

Both preps are the house default (a real one-call, multi-source assembly — §9.2), composing existing cores
in-process (architecture.md §2; S8 pattern lock), never a subprocess chain from the router.

- **`prep_question_sweep.py`** — facts keys: `repo`, `root{path,sha}`, `scope{arg,default_glob}`,
  `detection{oq_markers{present,raw,source},heuristics_active}`, `docs{present,files}`,
  `registry{count,questions[]}` (**each entry with the Tier-1 `status`** + `resolved`/`tier2_needed`
  /`marker_comment_present` + staged `sections` for the open ones), `scratch`, `attention`. Composes a
  prep-owned `gh issue list` (the registry — `oq_tracker`'s `--search` shape covers only the de-dup lookup,
  not a full enumeration, so it does **not** fit here), one `gh_gather.run` per OPEN question (the marker
  probe + body/thread staging), `config_block.read_block_anywhere` (the OQ config block, identical to
  prep_drafter), and the prep-owned `git rev-parse HEAD`. **Budget:** 1 registry list + one gather (3 gh
  calls) per OPEN question; a `closed` entry costs nothing (Tier-1 short-circuits on `state`).
  `needs_decision`: `AUTH_REQUIRED` only (fatal); a >1-marker question is recorded `status: "ambiguous"` +
  an attention line, never a whole-sweep abort. No `suggested_playbook` (single linear flow, like setup).
- **`prep_question_resolver.py`** — facts keys: `repo`, `root{path,sha}`, `target`, `is_question`,
  `reentrancy{mode,marker_comment_present,marker_comment_count,prior_decision?}`, `already_closed`,
  `blocking` (the native reverse edge → `## Unblocks`), `blocked_by`, `deps_available`, staged `sections`,
  `scratch`, `attention`. Composes one `gh_gather.run` (marker-prefixed) + the prep-owned `git rev-parse
  HEAD`. **Budget:** exactly one gather round-trip (3 gh calls). `needs_decision`: `AUTH_REQUIRED`, and the
  >1-marker `MARKER_AMBIGUOUS` forwarded verbatim (v1's "which decision is current" DECISION_NEEDED).
  Not-a-`question` and already-closed are **facts** (`is_question`/`already_closed` + attention), not
  decisions — "facts by script, decision by router", the same posture `prep_setup` uses.

## The playbook-split decisions (the §5-bar decisions the Work records)

architecture.md §5 "parameterize before you playbook": a playbook exists only for flows that differ in
**actions**, not values. **Both skills are single linear flows — router + one playbook.**

- **`question-sweep`** — scope → detect → reconcile → report → apply → land → summary. The three apparent
  branches are **not** routes: the GitHub-write gate (companions + back-link body patches), the doc-edit
  gate, and the §8.2 landing approve/decline are **runtime gates inside** the flow. No mode fork (no
  broad/targeted/revise, no epic/story). So `sweep-flow.md` is the one playbook; the detailed schemas
  (dispositions, the tiered read, the fold-back moves, the question-issue body) stay in the cited `_shared`
  contracts (not restated, not counted).
- **`question-resolver`** — read thread → ground → decide → verify → record → close → fold-back → summary.
  Fresh vs revise is a **fact gate** (`reentrancy.mode` — revise adds "show the prior + pass
  `--delete-marker-id`", a value + one small step, not a distinct action set); the offered close/reopen is a
  **runtime gate**. So `resolve-flow.md` is the one playbook.

## The `disable-model-invocation` frontmatter — BOTH carry it (S18 rule)

Per the S17 adjudication ([`docs/specs/parity/setup.md`](setup.md) §"disable-model-invocation") — **setup
was the exception; these two are the norm.** Both `question-sweep` and `question-resolver` carry
`disable-model-invocation: true` in their v2 frontmatter: v1 `open-questions` and v1 `question-resolver`
both carried it, and `CLAUDE.md:73` names all three of `doc-reviewer`/`open-questions`
(`question-sweep`)/`question-resolver` as the standalone tools that keep the key. Pinned by
`RouterStructureTests::test_router_exists_and_frontmatter_pins` in each routing test (asserts the key is
**present**).

## The Tier-1 join + Tier-2 flag mechanics (DoD box 1)

Per registry entry, prep derives a deterministic Tier-1 `status` (`open-question-links.md` §"Status is the
tracker's"): `closed` (resolved from `state`, no fetch) · `decision-marked` (open + a
`<!-- question-decision:v1 -->` comment, resolved) · `still-open` (open, no marker → `tier2_needed: true`).
`tier2_needed` is the signal that only the **router-dispatched** question-status reader (Tier 2, judgment)
can tell whether the thread already answered it — **prep never runs Tier 2**. A >1-marker question is
`ambiguous` (surfaced, never auto-resolved). Covered by `test_prep_question_sweep.py::test_tier1_status_join_trio`
(the closed/decision-marked/still-open trio in one registry), `test_tier2_needed_surfaced_in_attention`,
`test_ambiguous_marker_is_recorded_not_aborted`, and the budget test.

## The question-status reader convergence (S11 completion)

The carried reader (`question-sweep/references/question-status-reader-prompt.md`) converges on the
architecture.md §3 vocabulary: its one returnable code is `AMBIGUOUS` (a §3 member), and it now cites
`architecture.md §3` in place of the retired `subagent-decision-signal.md`. The moment the
`question-sweep/playbooks/` dir landed, the S11 drift-check validator
(`tests/test_subagent_prompts.py`) **auto-bound** this prompt (and the carried
`question-resolver/references/constraint-audit-prompt.md`) — asserting codes ⊆ §3, no old-doc citation, no
ref-arithmetic. This is the last of the S18-scoped prompts the S11 journal entry named, **completing
S11's sweep** (the S11 DoD's "binds later prompt authors … S18" clause). Verified: discovery lists both new
prompts; the frozen v1 `open-questions/…reader` stays excluded (no `playbooks/`). Sweep-local anchors in
`test_question_sweep_routing.py::ConvergedReaderTests`.

## Byte-identity + reentrancy (DoD box 4, offline half)

- **`question-decision:v1` byte-identity.** The decision-comment schema fence the resolve flow renders
  (`resolve-flow.md` §5) is **byte-for-byte** the frozen S1 capture
  [`docs/specs/examples/question-decision.md`](../examples/question-decision.md) (prd.md §7, row 4) —
  `test_question_resolver_routing.py::QuestionDecisionByteIdentityTests`. (A first draft diverged one line
  of `## Unblocks`; the test caught it, now identical.)
- **Reentrancy.** The revise path passes `--delete-marker-id <reentrancy.prior_decision.comment_id>` so the
  prior comment is **replaced, not duplicated** (`gh_persist.py comment` posts-new-then-deletes-old, its
  built-in); close is a re-run-safe no-op on an already-closed issue; reopen is offered only in the
  materially-changed reentrant case. Pinned by `ReentrancyMechanicsTests`. Prep's reentrancy facts
  (`mode` fresh/revise, `prior_decision.comment_id`, `already_closed`, and the >1-marker forward) are
  covered by `test_prep_question_resolver.py`'s reentrancy trio + `test_already_closed_is_a_fact`.

## The landing gate (S17-model fidelity, DoD boxes 2/3 offline half)

The sweep's apply-mode doc edits follow the exact S17 setup model (prd.md §8.2): approved doc edits stage in
a **work workspace** (`workspace.py ensure --work question-sweep/oq-<slug> --base main`), and the landing
(commit + push + a PR summarizing the doc/link changes) is **one explicit final gate**. On **decline**:
**no git actions** — the summary reports the workspace path + ready-to-run landing commands. Pinned by
`LandingGateLanguageTests` (flow + router prose) and `LandingPersistDryRunTests` (the `--dry-run` create-pr
envelope: conformant, `would_run` present, no url). The resolver has **no** landing/workspace — its two
write surfaces are the decision comment and the offered close, docs are proposal-only (it is not in the
prd.md §8.2 tracked-file-editing list).

## Offline validators (S18 DoD, implementor half)

- `python3 -m unittest tests.test_prep_question_sweep` — 10 tests: the Tier-1 trio + Tier-2 flag; the
  ambiguous-not-aborted case; detection config-block present/absent; the docs inventory; empty registry;
  the two-sided budget (1 list + 3/open question); `AUTH_REQUIRED`; conformance.
- `python3 -m unittest tests.test_prep_question_resolver` — 10 tests: fresh/revise; the >1-marker
  MARKER_AMBIGUOUS forward; the not-a-question guard; the native `blocking` surfacing; already-closed; the
  target/sections shape; the one-gather budget; `AUTH_REQUIRED`; conformance.
- `python3 -m unittest tests.test_question_sweep_routing` — 18 tests: the structural bars (router ≤ 150;
  loaded-set ceiling + half-metric recorded; one playbook); frontmatter pins (opus/high + **present**
  `disable-model-invocation`); the contract-token gate (0 `github-ops`/`github-pipeline:github-`/`GATHER_`
  /`PERSIST_`/`§P`/raw-gh-writes/`w/`); the §8.2 landing gate language; the converged reader (§3 cite, no
  retired doc); the `--dry-run` create-pr; stack-agnostic.
- `python3 -m unittest tests.test_question_resolver_routing` — 19 tests: the same structural/frontmatter/
  contract-token/stack gates; the `question-decision:v1` byte-identity; reentrancy mechanics; the carried
  constraint-audit (S11-clean, returns findings); the reader reached at its question-sweep home.
- `python3 -m unittest tests.test_subagent_prompts` — green over the two newly-auto-bound prompts (S11).
- Census: **zero cross-skill drops**; distinct-token delta **+1** (`github-pipeline:question-sweep`) — the
  v1 `question-resolver` dir's tokens all survive elsewhere (`github-pipeline:question-resolver` in
  `_shared/open-question-links.md` + the new v2 dir; the `GATHER_`/`PERSIST_`/`github-ops` op names in the
  other frozen v1 dirs and `agents/github-ops.md`). Verified against the `f9f1623` vantage.
- Full offline suite: **1107** tests green (1050 baseline + 57 new).

## Read-only live smoke (implementor, 2026-07-22)

Both preps run clean against the real sandbox (`danwashusen/gh-pipeline-sandbox`), read-only:

- `prep_question_sweep.py` — 7 `question` issues (#84/#83/#61/#30/#29/#27/#5), all `still-open` →
  `tier2_needed` (none carries a decision marker yet), `heuristics_active: true` (no config block), 43 docs
  in scope. Budget 1 list + 7×3 = 22 read-only gh calls, no error.
- `prep_question_resolver.py` on #61 — `is_question: true`, `mode: fresh`, `blocking: [86]` (the native
  reverse edge, `deps_available: true`), the `## Unblocks` attention line present; on #27 — `blocking:
  [28]`. Both one gather round-trip, read-only.

## Live parity scenarios (operator-gated — fill each result)

Harness: headless `claude -p --plugin-dir` can't answer `AskUserQuestion`; the interactive gates (the §8.2
landing, the decision gate) need the **tmux interactive-parity harness** (the
[[s17-scenario1-landing-approved]] recipe — the operator drives a real `claude --plugin-dir <this branch>
--model opus` session, cwd = a fresh sandbox clone). Don't pre-run a prep in a run clone (S13/S15 learning —
a pre-run prep can dirty the root). A v1 skill directory is deleted only after its v2 replacement passes
this protocol (S20) — **except** `question-resolver`, retired early under the naming adjudication above.

### Scenario 1 — sweep, report-only

Run v2 `question-sweep` on the sandbox and **decline every write** (no companions filed, no doc edits, no
landing). Expect a full reconciliation report grouped by class and a plain summary; **zero** GitHub writes,
**zero** git actions.

- [ ] **D1 (parity: reconciliation)** — v2's report classifies each OQ/question pairing into the closed set
  (`untracked`/`stale-doc`/`missing-back-link`/`orphaned-issue`/`in-sync`), reading resolution from prep's
  Tier-1 `status` (+ the Tier-2 reader for `tier2_needed` entries), never from a doc field.
- [ ] **D2 (report-only)** — declining performs **no** GitHub write and **no** git action; the summary is a
  plain summary (not a `## Handoff`), and any orphan is surfaced, never auto-closed.
- [ ] **D3 (v2 process)** — startup = exactly one `prep_question_sweep.py`; 0 `github-ops`; the Tier-2 reader
  is dispatched only for `tier2_needed` questions.
- **Result: _pending operator_**

### Scenario 2 — sweep, apply (landing approved + declined legs, per the S17 model)

Seed a non-trivial drift (e.g. an untracked OQ in a doc, and a stale-doc where a resolved question's doc
still marks it open). Run v2 `question-sweep`, approve the companion filing and the doc edits, then run the
**two landing legs**: (a) **approve** the landing → a PR opens whose body summarizes the doc/link changes,
head `question-sweep/oq-<slug>`, base `main`, root clean throughout; (b) **decline** the landing → **no git
actions**, the summary reports the workspace path + ready-to-run landing commands. Reset the seed between
legs; use a fresh clone for the decline leg.

- [ ] **D1 (landing approved)** — a PR opens with a body summarizing the doc/link changes; the project root
  is clean and on `main` **throughout** (all doc edits happened in the workspace — prd.md §8.1/§8.2).
- [ ] **D2 (landing declined)** — **no** commit, push, or PR; the summary reports the workspace path
  (`.worktrees/question-sweep/oq-<slug>`) and the exact ready-to-run landing commands.
- [ ] **D3 (GitHub writes via the single path)** — companions filed via `gh_persist.py create` (audience
  labels created inline first); back-link body patches via `gh_persist.py edit-body`; the landing via
  `workspace.py ensure --work` + `gh_persist.py create-pr`; 0 `github-ops`, 0 hand-rolled `gh … create`.
- **Result: _pending operator_**

### Scenario 3 — resolve + close (incl. the reentrant-revise clause)

Run v2 `question-resolver <N>` on an open sandbox question (e.g. **#61** — it natively blocks build #86, so
the decision comment's `## Unblocks` and the summary breadcrumb are exercised). Reach a decision, record it,
and **close**. Then **re-run** the same issue with a materially-changed decision to exercise the reentrant
revise (post-new-then-delete-old on the `<!-- question-decision:v1 -->` comment) and the offered reopen.

**v1 leg vantage (naming rider 2).** The v1 `question-resolver` dir is gone from `HEAD`; run the v1 leg from
a worktree at the vantage:

```bash
git worktree add /tmp/v1-vantage f9f1623
claude -p "/github-pipeline:question-resolver 61" --plugin-dir /tmp/v1-vantage --model opus   # (interactive: use the tmux harness for the decision gate)
# cleanup after: git worktree remove /tmp/v1-vantage
```

Run the v2 leg from `--plugin-dir <this branch>`. Diff the recorded decision comments (schema + marker) and
the close/reopen outcome.

- [ ] **D1 (decision comment byte-schema)** — v2 records a `<!-- question-decision:v1 -->` comment whose
  schema is byte-identical to the frozen S1 capture (marker first line; `## Decision`/`## Rationale`/
  `## Constraints respected`/`## Unblocks`/`## Caveats`); `## Unblocks` names the native `blocking` (#86).
- [ ] **D2 (operator-decides + verify)** — the decision is the operator's; the constraint audit ran before
  recording; a BLOCKER (if seeded) halted recording and returned to the discussion.
- [ ] **D3 (reentrant revise)** — the re-run **replaces** the prior decision comment (post-new-then-
  delete-old via `--delete-marker-id`), leaving exactly one decision comment; close is a no-op on the
  already-closed issue; reopen offered when the decision materially changed.
- [ ] **D4 (v2 process)** — startup = one `prep_question_resolver.py`; 0 `github-ops`; the doc fold-back is
  **proposed only** (0 doc edits); writes = `gh_persist.py comment` (+ optional `close`/`reopen`).
- **Result: _pending operator_**

## Go/no-go (operator)

- [ ] All three scenarios PASS (or every divergence is adjudicated as an explained v1 defect / fixture
  artifact / v2 enrichment).
- **Recommendation (implementor): GO on the offline half.** Both preps' fixture matrices (Tier-1 trio,
  reentrancy trio, budgets, decision paths), both routers' structural/frontmatter/contract-token/landing/
  byte-compat/reentrancy gates, the S11 reader convergence, and the census zero-drop are implementor-complete
  and green (1107 tests); both preps ran clean read-only against real sandbox questions. The three interactive
  scenarios (sweep report-only, sweep apply, resolve+close) are scaffolded above and await the operator's
  tmux-harness run.
