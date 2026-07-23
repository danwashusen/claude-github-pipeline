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
- **Result: PASS** (both legs, 2026-07-23). Twin-less comparison — one shared live registry, so v1
  `/github-pipeline:open-questions` and v2 `/github-pipeline:question-sweep` ran against **identical**
  starting state (7 open `question` issues, sandbox `main` `1b048ba`), one fresh clone each, both
  **report-only** (every gate declined). Run **interactively under the tmux harness** (the
  [`setup.md`](setup.md) Scenario-1 recipe — `claude --plugin-dir <this branch> --model opus`, cwd = the
  clone): both legs raise a real multi-question `AskUserQuestion` write gate, which headless `claude -p`
  cannot answer. Transcripts: `…-s18-scen1-clone-v1/247c9924-….jsonl` (v1),
  `…-s18-scen1-clone-v2/f974e666-….jsonl` (v2).

  **Fixture (as-found, unseeded).** `docs/open-questions.md` carries two register entries — `SBX-OQ-21`
  (repeated event name) with `**Tracked in:** (no companion question filed yet)` → **untracked**, and
  `SBX-OQ-22` (retention cap) with `**Tracked in:** (see the tracker)` → **missing-back-link** against #61
  (which names the doc correctly on its side). The other six questions (#84/#83/#30/#29/#27/#5) have no
  in-scope doc marker → **orphaned-issue**. #29/#30 each carry one owner comment that *answers* the
  question without a decision marker — the Tier-2 trap. Prep: all 7 Tier-1 `still-open`,
  `tier2_needed: true`, `heuristics_active` false (the `drafter-open-question-markers` block is present),
  3 docs in scope.

  - **D1 — PASS (identical class assignment; v2 strictly better-grounded).** Both legs produced the same
    reconciliation over the same closed set: **untracked 1** (`SBX-OQ-21`, both citing the same doc line
    and the same de-dup search result), **missing-back-link 1** (`SBX-OQ-22` ↔ #61, both naming the doc
    side as the gap), **orphaned-issue 6** (#84/#83/#30/#29/#27/#5, both flagging #83/#84 as a duplicate
    pair with no doc source, both surfacing rather than closing), **stale-doc 0**, **in-sync 0**. v2 read
    resolution only from prep's Tier-1 `status` plus the Tier-2 reader — never from the register's own
    `**Status:** Open` field, which it never cites as evidence of resolution. See Div-1: only v2 caught
    that #29/#30 are answered-but-open.
  - **D2 — PASS.** Zero writes on both legs, verified against pre/post snapshots: the full issue list
    (71 issues) and each of the 7 questions' `body`/`state`/`updatedAt`/`comments` are **byte-identical**
    pre-vs-post; the PR list is unchanged; `main` is still `1b048ba`. Zero git actions: both clones end
    clean, on `main`, at `1b048ba`, with no `.worktrees/` entry and no local branch beyond `main`
    (`git worktree list` shows only the clone itself). Both legs closed with a plain `## Summary`
    (companions filed / docs updated / back-links added / discrepancies left) — **no `## Handoff`** in
    either transcript. Orphans surfaced, none closed; v2 explicitly refused (*"The sweep will not close
    them"*) and both breadcrumbed the follow-on skill in prose.
  - **D3 — PASS.** v2 startup = **exactly one** `prep_question_sweep.py` call. **0** `github-ops` (the
    only `Agent` dispatches are 2 `Explore` Tier-2 readers). Tier-2 was dispatched **only** for
    `tier2_needed` entries (#29 and #30 — both flagged by prep), each with the reader prompt's `<<…>>`
    placeholders filled from prep's staged `sections` (body + thread inline), and each returned
    `resolved-in-thread`. Tool census — v2: 6 Bash (1 prep, 1 `gh repo view`, 2 read-only `gh issue list`
    de-dup searches, 2 local `wc`/`grep`), 7 Read, 2 Agent, 1 `AskUserQuestion` (2 questions), **0**
    `Edit`/`Write`, **0** `gh_persist.py`. v1: 10 Bash, 5 Read, 1 Grep, 1 `github-ops` Agent, 1
    `AskUserQuestion` (3 questions), 0 Edit/Write.

  **6 divergences (none blocks the scenario; Div-1 is a v1 defect, Div-2 a v2 report defect — RESOLVED):**
  1. **Div-1 — v1 asserted "empty threads" for questions it never read; v2 caught the answered-but-open
     pair.** v1 gathered only #61/#83/#84 through `github-ops` and closed its report with *"every question
     in scope is unambiguously still open (empty threads, no decision markers), so nothing needed
     escalation to a Tier-2 reader."* #29 and #30 each carry an owner comment that answers the question —
     v1's claim is contradicted by data it never fetched. v2's prep staged all 7 threads, and its two
     Tier-2 reads returned `resolved-in-thread` with the quoted answer, so v2's report surfaces the
     highest-value finding of the run: two questions answered in-thread with no `<!-- question-decision:v1
     -->` comment, which every Tier-1 consumer (drafter/planner/resolver) will keep treating as
     unresolved. **v1 defect / v2 enrichment** — this is exactly the drift the tiered read exists to
     catch, and it is the one class of finding the whole skill is for.
  2. **Div-2 — v2's orphaned-issue count label disagreed with its own table — RESOLVED.** The section
     header rendered `🟣 orphaned-issue — 5` while the table below it listed **6** rows
     (#84/#83/#30/#29/#27/#5) and the final summary correctly said *"6 orphaned question issues."* A
     per-class count that undercounts its own rows is a report-integrity defect even though no action
     derives from it. No count was authored in `sweep-flow.md` §3 (the report shape is the model's), so
     this was a rendering slip, not a spec bug. **Fix:** `sweep-flow.md` §3 now states the single-source
     count invariant — *every per-class header count and every summary total IS that class's row count in
     the one classification table; derive by counting the rows, never tally a class independently; a
     header/summary/table row-count mismatch is a defect* — the falsifiable-wording class. Pinned by
     `test_question_sweep_routing.py::ReportCountIntegrityTests` (the §3 invariant prose is present).
     **Not self-certified:** the pin fixes the *instruction*, not the rendered report (which is the
     model's at runtime); **Scenario 2's live report render is the confirmation** that the hardened
     instruction holds — a re-occurrence there reopens this. **Confirmed live (2026-07-23):** both
     Scenario-2 legs rendered counts equal to their table rows and named the derivation; no recurrence.
  3. **Div-3 — both legs read the docs directly instead of fanning out `Explore`.** `sweep-flow.md` §1
     (and v1's Step 2) prescribe a grep-prefilter then an `Explore` fan-out over the candidate files.
     With 3 docs totalling 47 lines, **both** legs prefiltered and then read them inline, each saying so
     explicitly (v2: *"Docs are small, so I read all three directly rather than fanning out"*; v1:
     *"Small doc set (3 files, 2 prefiltered) — I'll read them directly"*). Identical on both sides ⇒
     parity-neutral, and the reported prefiltered-vs-read count was preserved. Records that the fan-out
     is a cost control, not a correctness requirement, at this scale.
  4. **Div-4 — v2 short-circuited 5 of the 7 `tier2_needed` entries on `thread_comment_count: 0`.** Prep
     flags every still-open question `tier2_needed` and its attention line says the router dispatches the
     reader for all 7; v2 dispatched 2, reasoning that an empty thread is deterministically still-open
     with nothing for judgment to read. D3 as written is an **only** constraint (both dispatches *were*
     `tier2_needed`), so this passes — and the economy is sound (5 saved sub-agents, no information lost,
     since prep already stages `thread_comment_count`). Recorded because a future reader of the D3 box
     might expect 7 dispatches.
  5. **Div-5 — v1 burned 5 minutes on a self-authored polling loop.** After dispatching `github-ops`, v1
     ran `until [ -n "$(ls -A /tmp/gh-open-questions-sbx/ 2>/dev/null)" ]; do sleep 5; done` to wait for
     the sub-agent's scratch dir to populate — a race that cannot resolve, since the `Agent` result
     arrives through the tool result, not the filesystem. It hit the 5-minute Bash timeout (exit 143) and
     the leg self-recovered. Structural to the delegated-executor model v2 removes (v2 has no sub-agent
     to wait on at gather time — prep returns the facts synchronously), so **not** a fixture artifact.
  6. **Div-6 — gate shape and one extra v1 proposal.** v1 raised 3 questions (GitHub writes / doc edits /
     how to handle the #83/#84 duplicate pair, the last offering non-destructive cross-link comments);
     v2 raised 2 (GitHub write / doc edits) and handled the duplicate pair as a report-only observation.
     v1 also proposed a second GitHub write v2 did not — patching **#61's** `## Tracked in` to name the
     build issue it natively blocks (#86); v2 had the same `blocking` edge in its prep facts but judged
     #61's issue side already correct (the contract's back-link is doc↔issue, not issue↔build). Both
     gate before any write, both default to the non-destructive option — a values-level difference, not
     an actions-level one.

### Scenario 2 — sweep, apply (landing approved + declined legs, per the S17 model)

Seed a non-trivial drift (e.g. an untracked OQ in a doc, and a stale-doc where a resolved question's doc
still marks it open). Run v2 `question-sweep`, approve the companion filing and the doc edits, then run the
**two landing legs**: (a) **approve** the landing → a PR opens whose body summarizes the doc/link changes,
head `question-sweep/oq-<slug>`, base `main`, root clean throughout; (b) **decline** the landing → **no git
actions**, the summary reports the workspace path + ready-to-run landing commands. Reset the seed between
legs; use a fresh clone for the decline leg.

- [x] **D1 (landing approved)** — a PR opens with a body summarizing the doc/link changes; the project root
  is clean and on `main` **throughout** (all doc edits happened in the workspace — prd.md §8.1/§8.2).
- [x] **D2 (landing declined)** — **no** commit, push, or PR; the summary reports the workspace path
  (`.worktrees/question-sweep/oq-<slug>`) and the exact ready-to-run landing commands.
- [x] **D3 (GitHub writes via the single path)** — companions filed via `gh_persist.py create` (audience
  labels created inline first); back-link body patches via `gh_persist.py edit-body`; the landing via
  `workspace.py ensure --work` + `gh_persist.py create-pr`; 0 `github-ops`, 0 hand-rolled `gh … create`.
- **Result: PASS** (both landing legs, 2026-07-23). **v2-only by design** — the scenario tests the prd.md
  §8.2 workspace+landing behavior, which v1 `open-questions` does not have (it edits docs in place), so
  there is no v1 twin to diff; the comparison is against the specced contract, not a v1 leg. Run
  **interactively under the tmux harness** (the [`setup.md`](setup.md) Scenario-1 recipe + the Scenario-1
  `--allowedTools` upgrade above), one **fresh clone per leg**, with a full reset between legs.
  Transcripts: `…-private-tmp-s18s2-a/5cd232c1-….jsonl` (leg a), `…-private-tmp-s18s2-b/302d88d9-….jsonl`
  (leg b).

  **Fixture (seeded — the recipe).** From the Scenario-1 as-found state, three moves put one row in each
  actionable class:
  1. Posted a `<!-- question-decision:v1 -->` comment on **#61** (retention capped at the last 500 entries,
     oldest-first; `## Unblocks` names the native `blocking` #86) and **left the issue open** — Tier-1
     `decision-marked`, so prep still gathers it and the decision text is staged for the fold-back. (A
     *closed* issue would also read resolved but costs no gather, leaving the flow nothing to fold back.)
  2. Set the register's `SBX-OQ-22` entry to `**Tracked in:** #61` so its only drift is the resolution
     status → a clean **stale-doc** (doc says `Status: Open` / `Provisional default: unbounded`).
  3. Appended a `SBX-OQ-24` register entry (export format, `**Tracked in:** (see the tracker)`) matching
     open **#27**, whose `## Tracked in` names no doc → **missing-back-link**, both sides.
  `SBX-OQ-21` stays as-found → **untracked**. Seed commit `d18fc3c` pushed to sandbox `main`. Prep
  confirmed the join: #61 `decision-marked` (`marker_comment_present: true`), the other six `still-open`
  → `tier2_needed`, 3 docs in scope.

  - **D1 — PASS.** PR [#93](https://github.com/danwashusen/gh-pipeline-sandbox/pull/93) opened, head
    `question-sweep/oq-reconcile`, base `main`, workspace commit `0207481`. Body summarizes the doc/link
    changes under `## Doc changes` (the `SBX-OQ-22` fold-back in both locations, both back-links, the
    register-header fix), plus `## Not changed` ("No question issue was closed or resolved by this sweep")
    and `## Related` (#61/#92/#27). **Root clean throughout**, verified at three points — before the run,
    mid-run right after `workspace.py ensure`, and after the landing: `/tmp/s18s2/a` is `git status`-empty,
    on `main`, at the seed SHA `d18fc3c` every time; `git worktree list` shows the root at `d18fc3c [main]`
    with the only other entry the workspace. Every `Edit` targeted a path under
    `.worktrees/question-sweep/oq-reconcile/`.
  - **D2 — PASS.** Landing declined ⇒ **zero git actions**: workspace HEAD still `d18fc3c` with
    `docs/open-questions.md` + `docs/prd.md` **uncommitted** (`git status` shows ` M` both), the remote
    branch list **byte-identical** to the pre-run snapshot (no `question-sweep/*` remote branch), no new PR
    (the PR list's newest is leg (a)'s #93, closed during the reset), `main` still `d18fc3c`. The summary
    reports the workspace path (`/private/tmp/s18s2/b/.worktrees/question-sweep/oq-reconcile`, branch and
    base named) and a ready-to-run `W=…` / `git -C "$W" add` / `commit` / `push -u origin` /
    `gh_persist.py create-pr` block. Root clean on `main` at `d18fc3c`. See Div-4: the `create-pr` line
    cites a `pr.md` the declined run never staged, and the run said so.
  - **D3 — PASS, both legs.** Companion filed via `gh_persist.py create … --label question --label
    audience:developer` (leg a: `gh label create audience:developer … || true` inline first — it already
    existed, no label created; leg b checked `gh label list` and skipped the create). Back-link patch via
    `gh_persist.py edit-body … 27 <staged path>`. Landing via `workspace.py ensure --work
    question-sweep/oq-reconcile --base main --root <root>` + `gh_persist.py create-pr`. Every body staged
    to `facts.scratch` first. **0** `github-ops`, **0** hand-rolled `gh issue create`/`gh pr create`/`gh
    issue edit`; the only raw `gh` calls are read-only (`repo view`, the de-dup `issue list`, `label
    list`). Tool census — leg a: 10 Bash (1 prep, 2 read-only greps, 1 `gh repo view`, 1 label+create, 1
    edit-body, 1 `workspace.py ensure`, 1 workspace `git diff`, 1 workspace `add`/`commit`/`push`, 1
    `create-pr`), 8 Read, 3 `Explore`, 1 Grep, 2 `AskUserQuestion`, 4 Edit (all in-workspace), 3 Write (all
    to scratch). Leg b: 11 Bash (same shape minus commit/push/create-pr, plus a vestigial `ls`/`sleep 1`),
    9 Read, 2 `Explore`, 2 `AskUserQuestion`, 4 Edit (all in-workspace), 0 Write.

  **Reconciliation was identical on both legs** — untracked 1 (`SBX-OQ-21`) · stale-doc 1 (`SBX-OQ-22` ↔
  #61) · missing-back-link 1 (`SBX-OQ-24` ↔ #27) · orphaned-issue 5 (#84/#83/#30/#29/#5) · in-sync 0, total
  8 rows; each leg re-derived the #29/#30 `resolved-in-thread` finding and refused to close anything.

  **Scenario-1 Div-2 (count integrity) did NOT recur — confirmed fixed.** Both legs rendered per-class
  counts that equal their table's row counts and a total that equals the sum, and both said so in the
  falsifiable form the hardened §3 asks for (leg a: *"Counts (row counts from the table above)"*; leg b:
  *"Counts (each = its row count above)"*). This is the live confirmation Div-2 was left open for; it
  closes.

  **5 divergences (none blocks the scenario; Div-4 is a v2 defect — RESOLVED-pending-live):**
  1. **Div-1 — leg (a)'s doc-edit gate under-scoped the edit set it then made; leg (b)'s did not.** Leg
     (a) gated on *"Doc edits to `docs/open-questions.md`"* and then also edited `docs/prd.md` §2 (the same
     `SBX-OQ-22` drift, second location) and the register's header sentence. It **disclosed all three
     before the landing gate** (*"the diff above includes three things beyond the two literal doc-edit
     items you picked"*, with an offer to revert), and every edit was in the workspace, so nothing was
     silently applied and the landing gate still governed. Leg (b) scoped `prd.md` **into** the gate option
     up front (*"Plus prd.md §2: OQ-22 removed from the 'not yet decided' sentence"*) and offered the
     `SBX-OQ-21` back-link as its own option. Same final edit set, better gate wording — the fold-back
     legitimately spans every doc that asserts the stale state (`sweep-flow.md` §5 says "rewrite to the
     decided state", not "one file"), so the fix is to name the full file set **in** the gate, not to
     narrow the edit.
  2. **Div-2 — Tier-2 dispatched for a subset of `tier2_needed` (recurrence of Scenario-1's Div-4).** Prep
     flagged 6 still-open questions; leg (a) dispatched 3 (#27/#29/#30), leg (b) 2 (#29/#30), both
     short-circuiting the entries prep already showed with `thread_comment_count: 0`. Leg (b) reached the
     same **missing-back-link** classification for #27 without a reader (Tier-1 `still-open` + an empty
     thread is deterministic). D3's "only for `tier2_needed`" is an **only** constraint, so both pass;
     recorded because the dispatch count is not the flag count.
  3. **Div-3 — both legs read the docs inline instead of the `Explore` fan-out (recurrence of
     Scenario-1's Div-3).** Same 3-file/47-line scale, same prefilter-then-read, same explicit
     prefiltered-vs-read reporting. Confirms the fan-out is a cost control at this scale, not a
     correctness requirement.
  4. **Div-4 — the decline path's "ready-to-run" commands cited a `pr.md` that was never staged — v2
     defect, RESOLVED-pending-live.** `sweep-flow.md` §5's decline branch reported the `create-pr` command
     from §5's fence, which takes `"<facts.scratch>/pr.md"` — but the PR body was only authored on the
     *approve* path, so on decline that path did not exist. Leg (b) emitted the command **and flagged the
     gap honestly** (*"(pr.md isn't written — the gate was declined before staging it. Write a short body
     covering the three changes above, or open the PR with `gh pr create` directly.)"*), which is why D2
     still passed: the operator was not misled. Still, "ready-to-run" is the contract word. **Fix:**
     `sweep-flow.md` §5 now **stages `pr.md` (the doc/link-change summary) BEFORE the landing gate**, so
     both paths share that one authored file — approve consumes it via `create-pr`; decline's reported
     commands run exactly as printed. Falsifiable wording added: *the decline commands must run exactly as
     printed — `pr.md` is already staged, so citing it is safe; citing an unstaged file is a defect.*
     Pinned by `test_question_sweep_routing.py::LandingGateLanguageTests::{test_pr_body_staged_before_the_landing_gate,
     test_decline_commands_are_runnable_as_printed}` (the staging-order + the staged-path citation).
     **Not self-certified:** the pins fix the *instruction*, not a live decline render — and **no
     remaining scenario re-renders the decline path** (Scenario 3 is the resolver, no landing). So the live
     confirmation is honestly **deferred** to real-world use or an optional operator re-leg of Scenario 2's
     decline branch; a re-occurrence there reopens this.
  5. **Div-5 — leg (b) ran one vestigial `ls <scratch>` + `sleep 1; echo ok`** while waiting on its
     backgrounded `Explore` readers — a faint echo of the v1 Scenario-1 Div-5 polling loop, but bounded
     (one second, no timeout, no dependence on the filesystem for the result). Cosmetic.

### Scenario 3 — resolve + close (incl. the reentrant-revise clause)

Run v2 `question-resolver <N>` on an open sandbox question (e.g. **#61** — it natively blocks build #86, so
the decision comment's `## Unblocks` and the summary breadcrumb are exercised). Reach a decision, record it,
and **close**. Then **re-run** the same issue with a materially-changed decision to exercise the reentrant
revise (post-new-then-delete-old on the `<!-- question-decision:v1 -->` comment) and the offered reopen.

**Sandbox state left by Scenario 2 (read before picking a target).** Scenario 2's seed and its leg-(b)
outputs were deliberately **not** rolled back — leg (a) was fully reset (PR #93 closed + branch deleted,
companion deleted, #27 restored), leg (b) was not. So going in: **#61 is open and already carries a
`<!-- question-decision:v1 -->` comment** (the Scenario-2 stale-doc seed), which makes `prep_question_resolver`
report `reentrancy.mode: revise` — i.e. a #61 run starts on the *reentrant* path, not the fresh one. To run
the fresh leg on #61, delete that comment first (`gh api -X DELETE
repos/danwashusen/gh-pipeline-sandbox/issues/comments/5054106253`; body preserved in this record and in the
seed scratch), or target a still-fresh question instead — **#27** also carries a native `blocking` edge
(#28) and so exercises `## Unblocks` the same way. Also present from leg (b): companion **#94**
(`SBX-OQ-21`) and #27's patched `## Tracked in`. Sandbox `main` is at the Scenario-2 seed `d18fc3c`.

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
