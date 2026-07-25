# End-to-end conveyor run (S20 DoD box 4) — operator-gated

> Records [implementation.md](../../implementation.md) step **S20**'s fourth DoD box: *"Fresh
> end-to-end conveyor run on the sandbox — draft → research (decline acceptable) → plan → resolve →
> evaluate → merge — with every handoff schema-valid."* This is the **run's last operator gate**,
> and the only DoD box in S20 that is not implementor-completable.

**This is not a parity run.** The eight per-skill parity runs are already recorded and accepted
(`docs/specs/parity/*.md`); v1 is gone from the tree, so there is no v1 leg to twin against. What
box 4 asks for is different and complementary: an **integration acceptance run** proving the five
v2 pipeline stages compose end to end through nothing but GitHub artifacts and the `## Handoff` —
the one property no per-skill scenario could test, because each ran one stage in isolation against
hand-constructed state.

The falsifiable claim: *one issue, drafted from informal feedback, reaches a merged PR on the
sandbox's `main` through five separate sessions, with each session started **only** by
copy-pasting the previous session's handoff command, and every handoff validating against
`skills/_shared/handoff-format.md`.*

## Preconditions

- Sandbox: `https://github.com/danwashusen/gh-pipeline-sandbox` ([SANDBOX.md](../../../tests/SANDBOX.md)).
  Labels, grounding docs, config marker blocks, and the controllable CI gate are already seeded.
- `gh auth status` clean; `git` and `python3` on `PATH`; **no other runtime is needed**.
- A fresh clone of the sandbox per run (`/tmp/s20-conveyor`), on `main`, clean — the resolver and
  evaluator both fail closed on a dirty or diverged root (`ROOT_DIRTY` / `ROOT_DIVERGED`), which is
  correct behavior, not a run failure, but it costs a restart.
- Plugin under test: this branch, via `--plugin-dir <repo root>`.
- **Harness.** Every stage gates on `AskUserQuestion`, which headless `claude -p` cannot render, so
  run each session in the **tmux interactive harness** (the recipe in [`setup.md`](setup.md)
  Scenario 1, with the S18 Scenario-1 `--allowedTools` upgrade):

  ```bash
  cd /tmp/s20-conveyor
  claude --plugin-dir /Users/danwas/Development/Projects/claude-github-pipeline --model opus \
    --allowedTools Bash Read Grep Glob Task TodoWrite Edit Write WebFetch
  ```

  Two tmux gotchas recorded by S19 Scenario 1 and worth re-reading before the first leg: the
  ghost-suggestion input trap, and `Submit` being a **tab** (Right), not a Down row, on the
  question card.
- **One session per stage.** Start a new session for each leg — never continue the previous one.
  Session-per-stage is the property under test; continuing would invalidate the run.

## The subject issue

Draft something small, real, and *buildable in one phase* against the sandbox's toy source — the
run is testing the conveyor, not the difficulty of the work. A single-file behavior change with an
obvious Definition of done is ideal (the sandbox carries `salute_a` / `formatter_a`-style helpers
from earlier parity runs; a new sibling helper, or a defect in an existing one, works).

Avoid: an epic (the epic path is already covered by `planner.md` Scenario 2 and `resolver.md`
Scenario 4 and adds a bootstrap leg that is not what box 4 measures); anything touching
`.ci-force-red` (that fixture is the evaluator's red-CI scenario).

## Run record — 2026-07-25

**Subject:** `src/initials.py` — `initials(full_name)` shipped as a stub returning its argument
unchanged, contradicting the docstring contract it already publishes. Untouched by all eight prior
parity runs, single file, one phase, checkable acceptance. Chosen per "The subject issue" above; the
plugin's own pinned-config-header wart was considered and rejected as the subject because it does
not exist in the sandbox (no `COMMANDS.md`, config blocks live in `CLAUDE.md` where the header is
deliberately skipped) and the plugin repo cannot host the run (its `origin/main` is the v1 tree).

**Clone:** `/tmp/s20-conveyor` at sandbox `main` `ff490b3`, one clone for the whole run — the
preconditions' per-run rule, and the only reading under which "root untouched across all five legs"
and the evaluator's teardown of the resolver's worktree are meaningful.
**Harness:** one fresh tmux session per leg (`s20l1b`, `s20l2`, `s20l3`, `s20l4`, `s20l5`), each a
new `claude --plugin-dir … --model opus --allowedTools …` invocation. Both S19 gotchas recurred and
were handled: the ghost-suggestion trap fired twice (a stale `file it` after an Esc, and a
`file an issue for the CI workflow…` after the terminal handoff), and every gate this run rendered
**single**-select with option 1 pre-highlighted, so no `Right`-to-`Submit` dance was needed.

**Fixture preparation, disclosed.** Neither `pytest` nor `flake8` was installed on the host, so the
sandbox's own declared gates (`<!-- pr-evaluator-test-target -->`, `<!-- pr-evaluator-static-checks -->`)
were unrunnable. Both were installed user-scope before leg 1 and the three declared commands
baselined green on `ff490b3`; the `src/__pycache__/` that baselining left behind was removed and the
root re-verified clean. Without this the run would have measured a missing toolchain rather than the
conveyor.

**One discarded pre-file attempt (session `s20l1`).** The first leg-1 run described the defect as a
bug ("looks broken"); the drafter classified it `bug` and drafted — correctly — with **no
`## Definition of done`**, because the bundled bug template carries none by design
(`skills/drafter/references/issue-reviewer-prompt.md:112`: "Definition of done for stories. Steps to
reproduce + expected vs. actual for bugs"). Filing that would have left legs 4 and 5 with no DoD to
project or verify — the `_shared/dod-annotations.md` contract shared by three skills, unexercised in
the one run built to test composition. Nothing had been written to GitHub, so the attempt was
abandoned at the pre-file gate and leg 1 re-run with the same defect described as what it also
literally is — an unimplemented stub. The drafter classified `incomplete` on its own and produced a
9-bullet DoD with no operator dictating its content. Recorded as **Div-1**; the attempt cost nothing
but is disclosed because it shaped the subject's framing.

## Legs

Record each leg's result inline. A leg **passes** when its own criteria hold **and** its handoff
validates (checklist below).

### Leg 1 — `drafter`

```
/github-pipeline:drafter <paste the informal feedback here>
```

- [x] Classifies the feedback (bug / incomplete / feature / epic / question) without asking unless
      signals genuinely conflict; grounds framing in the sandbox `docs/prd.md`.
- [x] Runs its adversarial review before filing; nothing is filed before the confirmation gate.
- [x] Files one issue with a `## Definition of done` whose bullets are checkable.
- [x] Startup performed **exactly one** state-assembly call (`prep_drafter.py`) — [prd.md §9.2](../../prd.md).
- [ ] Handoff points at `/github-pipeline:researcher <N>` — **does not hold; see Div-2.** The
      handoff printed `/github-pipeline:planner #101`, which is what the drafter's contract
      prescribes.
- **Result: PASS** (issue [#101](https://github.com/danwashusen/gh-pipeline-sandbox/issues/101)),
  with the researcher-routing criterion falsified as a spec error, not a skill defect (Div-2).
  Classified `incomplete` unprompted from the cues it quoted ("never got finished", "was never
  written", "no test for it either"). Raised **one** gate, and a legitimate one — degenerate-input
  behavior is genuinely undecided by the docstring, so it asked before drafting rather than
  inventing an acceptance criterion; answered "return empty string", which it then recorded in the
  body as *"Decided while filing"*. The isolated reviewer ran on the staged draft (dimensions 1, 2,
  3, 6) and returned 0 blockers / 1 suggestion / 2 nits, all folded in — including a real one, that
  the "reporting layer" motivation was unverifiable as originally worded. Body carries a 9-bullet
  DoD, every bullet mechanically checkable (7 behavioral assertions + the repo's own
  `pytest`/`compileall`/`flake8` commands). Census: 1 `prep_drafter.py`, 1 `gh_persist.py create`,
  0 other GitHub ops. Labels `bug` + `good first issue` — the repo has no `incomplete` label, and
  the body says so explicitly rather than silently mismatching. Root clean on `main` throughout.

### Leg 2 — `researcher` (a decline is a pass)

```
/github-pipeline:researcher <N>
```

- [x] Applies the currency-risk gate. **Declining is an acceptable outcome** and the likely one for
      a small internal change — the pass condition is that the decline is *stated with its
      reasoning* and that **nothing is posted** (no dossier comment, no marker, no label).
- [x] If it does research: the dossier carries the `<!-- issue-research:v1 -->` marker on its first
      line, tiered + dated sources, and is validated before posting. — n/a, declined.
- [x] Handoff renders `research: ✓` or `research: ✗` from the closed set and points at
      `/github-pipeline:planner <N>`.
- **Result: PASS** (declined). **Started by the operator, not by a printed command** — no handoff in
  the tree points here (Div-2). Walked all four decline conditions explicitly and negated each with
  evidence rather than asserting a verdict: no manifest exists and nothing in `src/` imports a third
  party; no vendor API, deprecation timeline, or platform policy in scope; the one behavioral
  subtlety (argument-less `str.split()` collapsing whitespace runs — exactly what two DoD bullets
  need) is settled core-language behavior; and the sole design point was already decided in the
  issue body. **Zero writes verified independently after the leg:** issue #101 still at 0 comments,
  labels unchanged (`bug`, `good first issue`), and **0 `gh_persist.py` invocations** in the whole
  session. Census: 1 `prep_researcher.py`, 0 GitHub ops. Root clean on `main`.

### Leg 3 — `planner`

```
/github-pipeline:planner <N>
```

- [x] Posts one `<!-- implementation-plan:v1 -->` comment, grounded on an explicitly recorded
      commit SHA, citing sandbox docs by anchor.
- [x] Gates any genuine tradeoff to the operator; records no open design decision in `## Changes`.
- [x] Applies the `planned` label and the issue-body plan pointer.
- [x] Handoff renders `plan: ✓ (<url>)` and points at `/github-pipeline:resolver <N>`.
- **Result: PASS.** Command run **as printed** from leg 2. One plan comment, marker
  `<!-- implementation-plan:v1 -->` on line 1, grounded `read at origin/main@ff490b3` and citing
  `docs/architecture.md §3` + `docs/constitution.md §1/§4/§5/§6/§7/§8` + `CLAUDE.md` by anchor.
  `planned` label applied; issue body carries the plan pointer. No operator gate — correctly, since
  the one design choice (the split form) came with its rejected alternative recorded as a *decision*,
  not left open. The leg's distinguishing behavior was **verifying its falsifiable claims instead of
  asserting them**: it ran `python3 -m pytest -q` against an empty tree and found exit **5**, so the
  plan says "collects zero tests and exits 5" rather than the plausible-but-wrong "passes
  vacuously"; it confirmed `from src.initials import initials` resolves under `python3 -m pytest`
  but fails under bare `pytest`, turning a guess into a pinned decision plus a watchpoint; and it
  ran the join expression against all eight cases, finding seven red pre-fix and
  `initials("") == ""` already green — which is why the plan flags that case as carrying no
  regression signal. Its reviewer caught a real off-by-one in a precedent citation
  (`src/greeter_a.py:10` is the closing `"""`, the return is `:11`), fixed before posting.
  **Two `prep_planner.py` calls**, which is compliant: startup was one, the second is the
  `--refresh` for volatile facts that `skills/planner/SKILL.md:41` prescribes, used here to confirm
  the staged issue body still matched live before writing the pointer. Root clean on `main`; a
  `.worktrees/ro-main` read workspace was created as designed.

### Leg 4 — `resolver`

```
/github-pipeline:resolver <N>
```

- [x] Audits fitness before building; builds **only** in `.worktrees/<branch>` — `git -C
      /tmp/s20-conveyor status --porcelain` stays **empty throughout** and the root stays on `main`
      ([prd.md §8.1](../../prd.md)).
- [x] Opens a PR that closes the issue by keyword (`Fixes #<N>` / `Closes #<N>`), with
      `## Doc grounding`.
- [x] Projects the DoD ticks with annotations from the closed set as the phase ships.
- [x] Runs its review loop to approval, then flips the PR draft→ready before the handoff. — review
      loop approved at iteration 1; the draft→ready flip was **structurally unnecessary** (single
      phase → PR opened non-draft), so there was nothing to flip. Criterion assumes the multi-phase
      shape; see Div-6.
- [x] Handoff carries the PR line and points at `/github-pipeline:evaluator <PR>`.
- **Result: PASS.** Command run **as printed** from leg 3. PR
  [#102](https://github.com/danwashusen/gh-pipeline-sandbox/pull/102), head
  `101-incomplete-initials-initials-returns-the-name`, base `main`, non-draft, `Fixes #101` on the
  first body line, `## Doc grounding` present. **Root untouched, verified independently after the
  leg:** `git -C /tmp/s20-conveyor status --porcelain` empty, still `main` at `ff490b3`; all work at
  `3fd513d` inside `.worktrees/101-…`. Fitness audit returned 0 blockers → no gate; the plan gate
  confirmed plan SHA == workspace HEAD with every locked surface intact, so the plan was **consumed,
  not re-derived**. Test-first ordering (constitution §4, DoD bullet 1) was *observed*, not assumed:
  tests authored and run red first — **7 failed / 1 passed** against the unmodified stub — then the
  `src/` edit, then 8 passed. Static/health gates green on run 1, no retry ladder. Review loop
  approved at iteration 1 with zero addressable items; no follow-ups filed, and the one
  deferrable-looking item was judged unjustified scope rather than quietly deferred. All 9 DoD
  bullets projected as `- [x] … (closed by commit 3fd513d)` — the single-phase fallback form from
  the closed set (`skills/_shared/dod-annotations.md:14`), verified against the live issue body.
  Census: **1** `prep_resolver.py`, zero operator gates.

### Leg 5 — `evaluator` (through merge)

```
/github-pipeline:evaluator <PR>
```

- [x] Runs the health gate (sandbox CI + the configured checks) and caches it in a
      `<!-- pr-evaluator-health-cache:v1 -->` comment keyed on the head SHA.
- [x] Verifies each DoD tick against its annotation; un-ticks with a sticky veto on any mismatch
      (none expected here — a clean run is the pass).
- [x] Posts an `APPROVE` review (never self-approving — the sandbox PR is authored by the same
      account, so **expect and record** the self-review guard's behavior).
- [x] Merges per the sandbox's `<!-- pr-evaluator-merge-policy -->` (default `ask` → an operator
      gate), with the strategy rules for the PR's shape.
- [x] Post-merge: the issue closes, the work workspace is torn down and removed, and the root is
      still clean on `main` — **but the prescribed removal path could not complete it; see Div-3.**
- [x] Handoff is **terminal** (`(terminal — no follow-up skill)`) with a `Cleanup:` line and a
      `Why:` explaining why the pipeline ends here.
- **Result: PASS** (merged), with one real defect on the teardown path (Div-3). Command run **as
  printed** from leg 4. Health gate green — `flake8` exit 0, `compileall` exit 0, `pytest` 8 passed
  — cached in a `<!-- pr-evaluator-health-cache:v1 -->` comment keyed on head `3fd513d`. It declined
  to treat the sandbox's marker-file CI as signal and said so, running the configured checks
  locally instead; its `Why:` carries that forward as a standing warning for future runs in this
  sandbox ("any PR here will report CI green regardless of whether its tests pass"). DoD bullet 1
  was re-verified **empirically rather than taken on faith** — because both files land in one
  commit, ordering isn't provable from the commit graph, so it re-ran the PR's tests against the
  `ff490b3` stub in a scratch copy and reproduced 7 failed / 1 passed, matching the PR body's claim
  including *which* case carries no regression signal. All 9 ticks verified, zero sticky vetoes.
  **Self-review guard behaved as predicted and was handled, not tripped over:** the evaluator
  anticipated GitHub's 422 on self-approval (same account authored the PR), stated it in the gate
  card, and posted the approving review as a `COMMENTED` review — the API confirms
  `reviews: ["COMMENTED"]`. Merge policy `standard: ask` → operator gate → Approve → **squash →
  `main@461e73c`** with `--delete-branch`. Post-merge verified independently: PR `MERGED`, issue
  #101 `CLOSED` by auto-close, `src/initials.py` and `tests/test_initials.py` both on `main`, root
  clean on `main`, work worktree gone (only `ro-main` remains, which is `gc`-by-age, not the
  evaluator's to remove). Census: 2 `prep_evaluator.py` — startup plus the S7-gate `--refresh` that
  re-confirms current truth immediately before the merge decision (prescribed).

## Handoff schema validity (the box's explicit clause)

Validate each of the five handoffs against
[`skills/_shared/handoff-format.md`](../../../skills/_shared/handoff-format.md) — the schema is the
contract, and this run is the first time all five are produced in one chain.

For each handoff, check:

- [x] The block is `## Handoff`, cold-readable without the session transcript. — all five.
- [x] Every state marker is from the **closed set** — no invented synonyms (`open`/`closed`,
      `✓`/`✗`/`stale`, `APPROVE`/`COMMENT`, `squash`/`merge`, the `skipped (…)` reasons). — all
      five; every token emitted this run (`open`, `closed`, `bug`, `incomplete`, `✓`, `✗`, `open`,
      `merged`, `not run`, `APPROVE (operator)`, `✅ at <sha>`, `squash → main@<sha>`) is a member.
      The `type` slot is closed-set-valid on each line but **unstable across the chain** (Div-4).
- [ ] The omission rules hold: no `PR:` line before a PR exists; `Cleanup:` only after a merge ran;
      `Open questions:` only when the issue/plan gated on one. — those three hold exactly. Two
      *other* omissions have no authorizing rule in `handoff-format.md`: the researcher drops
      `plan:` (Div-5a) and legs 3–5 drop `research:` on an issue that did go through the researcher
      (Div-5b).
- [x] The fenced next-action block carries a command that runs **as printed** — the operator ran it
      verbatim to start the next leg (this is the real test; a handoff that needed editing is a
      defect, not a nit). — **4 of 4 printed commands ran verbatim and worked.** The fifth hop
      (1→2) had no printed researcher command to run (Div-2); leg 5 is terminal by design.
- [x] `Why:` is present and specific. — all five; none is generic. The evaluator's carries a
      standing fixture warning, and the resolver's names three informational findings it
      deliberately did *not* file as follow-ups.

Exact `Issue:` / `PR:` lines as emitted are in the per-leg results above; the five handoffs were
extracted verbatim from the session transcripts and checked line-by-line against the schema.

| Leg | Handoff valid | Command ran as printed | Notes |
|---|---|---|---|
| 1 drafter | ✅ | n/a — printed `/github-pipeline:planner #101`, **not** a researcher command (Div-2); the planner leg was started from leg 2's identical printed command | `plan: ✗`, no `PR:`/`Cleanup:` — omissions correct. `research:` correctly absent (issue had not been through the researcher yet) |
| 2 researcher | ⚠️ | ✅ `/github-pipeline:planner #101` | `research: ✗` correct; **`plan:` segment absent** with no authorizing omission rule (Div-5a). Leg itself was operator-started |
| 3 planner | ✅ | ✅ `/github-pipeline:resolver #101` | `plan: ✓ (<url>)` + `Grounding:` with `read at origin/main@ff490b3`; `research:` dropped (Div-5b) |
| 4 resolver | ✅ | ✅ `/github-pipeline:evaluator #102` | `PR:` line present with `review: not run · health: not run · merge: not run`; no `Cleanup:` (correct — no merge ran) |
| 5 evaluator | ✅ | (terminal) | `merged · base main · review: APPROVE (operator) · health: ✅ at 3fd513d · merge: squash → main@461e73c`; `Cleanup:` present (correct — merge ran); `Next: (terminal — no follow-up skill)` |

## Cross-cutting checks

- [x] **One state-assembly call per session** ([prd.md §9.2](../../prd.md), [§10](../../prd.md)) —
      each leg's first tool call is its own `prep_*.py`, and no leg assembles state across multiple
      model-mediated calls. — **holds on the substance.** Startup assembly was exactly one call in
      every leg (drafter 1, researcher 1, planner 1, resolver 1, evaluator 1). The two legs showing
      a second invocation are both the prescribed `--refresh` for volatile facts, mid-flow and
      contract-sanctioned (`skills/planner/SKILL.md:41`; the evaluator's S7-gate re-confirmation).
      Three legs preceded prep with a one-line orientation `Bash` (`git remote -v`) to learn the
      repo slug — not state assembly, but it means "first tool call is its own `prep_*.py`" is
      literally false in 3 of 5 legs (Div-7).
- [x] **Root untouched, all five legs** — `git -C /tmp/s20-conveyor status --porcelain` empty and
      HEAD on `main` before and after every leg. — verified at all six boundaries; `main` stayed at
      `ff490b3` locally (the merge landed on the remote). The only dirt observed all run was the
      `src/__pycache__/` **my own** pre-run baselining created, removed before leg 1.
- [x] **No stale-name breakage** — no session printed or ran a `/github-pipeline:github-*` command,
      and no skill tried to invoke a retired script (the S20 removal's live falsification). — swept
      across all five transcripts: the only `/github-pipeline:*` strings emitted were `drafter`,
      `researcher`, `planner`, `resolver`, `evaluator`, and the only scripts invoked were
      `gh_gather.py`, `gh_persist.py`, `workspace.py`, and the five `prep_*.py`. **No `*.sh`, no
      retired executor, zero hits for any v1 skill name.** The frozen provenance strings *did*
      surface in artifacts exactly where [prd.md §7](../../prd.md) says they should — the plan
      footer and the issue-body plan pointer both read "authored by `github-issue-planner`" — which
      is the contract holding, not a leak (Div-8 records the user-facing cost).
- [x] **Artifacts on the issue/PR** carry their markers verbatim: `<!-- implementation-plan:v1 -->`,
      the optional `<!-- issue-research:v1 -->`, `<!-- pr-evaluator-health-cache:v1 -->`, and the
      DoD annotations. — plan marker on line 1 of the plan comment, health cache marker on the PR
      comment keyed to `3fd513d`, all 9 DoD bullets in the `(closed by commit <short-sha>)` form.
      `<!-- issue-research:v1 -->` correctly absent (research declined).

## Divergences / defects

One row per unexpected behavior. Each must trace to a PRD requirement, a GitHub behavior, a fixture
artifact, or be filed as a defect — an unexplained divergence fails the run (the parity protocol's
rule, applied here too).

**Post-run dispositions (2026-07-25).** Row **2** (the researcher is never routed to) is **RESOLVED
as a doc defect** — the topology was v1-faithful all along and the docs were corrected; no skill
changed. Rows **1** (bug template carries no DoD) and **3** (post-merge teardown refusal) are
**FILED-CANDIDATES for post-run product issues** — both need design decisions, and S20 is the last
step, so neither is fixed here. Rows 4 and 5 keep their recorded fixes as-is. (The rulings are
recorded in each row's Adjudication cell; the row numbers below are this table's, not the order the
findings were reported in.)

| # | Leg | What happened | Adjudication |
|---|---|---|---|
| 1 | 1 | First (discarded, pre-file) leg-1 attempt drafted a `bug` with **no `## Definition of done`**. | **Correct skill behavior, spec-vs-template mismatch.** The bundled bug template carries no DoD by design (`issue-reviewer-prompt.md:112` assigns DoD to stories). Leg 1's third criterion is therefore unsatisfiable for any `bug`-classified subject, and legs 4/5's DoD criteria with it. Re-framed the same defect as the unimplemented stub it also is; the drafter classified `incomplete` on its own and produced the DoD natively. **Fix:** either give the bug template a DoD or state in `conveyor.md` that the subject must not classify as `bug`. **→ FILED-CANDIDATE (2026-07-25), deliberately NOT fixed in S20.** This is a **template/product decision, and a v1-faithful gap** — the bug template has never carried a DoD in either version, so "fixing" it changes filed-issue shape for every consuming repo and ripples into the evaluator's DoD verification (what does it verify on a bug PR?) and the resolver's tick projection. That is a product call with a plan, not a retirement-step edit. Recorded here so the next conveyor run picks a subject that classifies away from `bug`, or picks up the template decision first. |
| 2 | 1 | Drafter handoff printed `/github-pipeline:planner #101` — **the researcher is never routed to.** | **Real seam defect — the run's headline finding.** Not a slip: none of the five renderings in `skills/drafter/references/handoff-renderings.md` names the researcher, and the only skill in the tree emitting a `/github-pipeline:researcher` command is the **planner**, as a re-route for an ungroundable fact (`skills/planner/playbooks/single.md:34`). So the shipped topology is `draft → plan`, with research as a planner-initiated detour — while [CLAUDE.md](../../../CLAUDE.md) and this spec both document `draft ──▶ research ──▶ plan` as a linear chain. A user following the handoffs **never reaches the researcher**. This is exactly the "seam between two accepted skills, most plausibly in a handoff's next-command rendering" the go/no-go predicted. **Fix:** decide which is true and make the other match — either the drafter routes to the researcher (conditionally or always), or the documented pipeline drops research from the linear chain and describes it as planner-initiated. **→ RESOLVED (2026-07-25) as a DOC defect, not a skill defect.** The ruling: the shipped topology is v1-faithful and was always correct; the *docs* were wrong. Evidence — (a) **v1's drafter also forwarded straight to the planner**: [`parity/drafter.md`](drafter.md) Scenario 4(b) records v1's handoff `Next:` as `/github-pipeline:github-issue-planner #86` against v2's `/github-pipeline:planner #85`, "each points at its own generation's planner"; (b) **the researcher is reached by planner re-route**: [`docs/specs/planner.md`](../planner.md) "Knowledge-gap handling" (Step 5: anything broader than an inline fact-check "re-routes to the researcher entirely") plus `skills/planner/references/handoff-renderings.md`'s "Knowledge gap — re-route to the researcher" rendering; (c) **the researcher always hands back to the planner** — [`parity/researcher.md`](researcher.md) D2 in all three scenarios (`Next: /github-pipeline:planner #<N>`), including the decline leg. So `draft ──▶ research ──▶ plan` never described either version's handoffs. **Fixed in the docs, not the skills:** `CLAUDE.md`'s conveyor paragraph and `README.md`'s pipeline intro now state the actual topology (drafter → planner; research a conditional planner-initiated detour that hands back). No prompt or script changed. |
| 3 | 5 | `workspace.py remove --work` **refused twice** post-merge; the evaluator removed the worktree by hand after verifying content on `main`. | **Real defect, reproducible on every clean squash-merge.** Refusal 1: the workspace reads dirty from `__pycache__` bytecode **the evaluator's own health gate just generated** (15 untracked `.pyc`, zero tracked modifications). Refusal 2: `unpushed_commits: 1`, which is structural — `--delete-branch` removed the remote branch and the squash rewrote `3fd513d` into `461e73c`, so the local branch has no upstream and its pre-squash commit reads as unpushed. The session handled both correctly (verified both files on `origin/main`, ran the teardown hook, then `git worktree remove`), and the end state is right — but the prescribed script path cannot complete the evaluator's own teardown. **Fix:** ignore untracked bytecode in the dirty check (or have the gate run in a temp dir), and treat "unpushed" as satisfied when HEAD's content is reachable from the merge target. **→ FILED-CANDIDATE (2026-07-25), deliberately NOT fixed in S20.** `workspace.py remove --work` needs a **merged-verified disposal path**: every clean squash-merge hits the refusal, so this is a standing product gap, not a run artifact. It needs a design decision (what counts as "safely disposable" — content reachable from the merge target? a caller-asserted `--merged` flag? an ignore-list for generated files?) and that decision belongs in a product issue with its own plan, not in the retirement step's cleanup. The evaluator's own end state was correct on this run; only the prescribed script path could not complete it. |
| 4 | all | The `type` token flips across the chain for one issue: `incomplete` (1) → `bug` (2) → `bug` (3) → `incomplete` (4) → `bug` (5). | **Each line is individually schema-valid; the chain is not coherent.** Both values are closed-set members, and the vocabulary table says to "map the repo's own label onto this set" — the sandbox has no `incomplete` label, so `bug` is a defensible read, and so is carrying the drafter's classification. Nothing pins *which*. Same class as the S16 `enhancement`/`feature` flip. Non-blocking (no skill parses it), but a cold reader following the chain sees the issue change type twice. **Fix:** pin the precedence (classification over label, or vice versa) in `handoff-format.md`'s type row. |
| 5 | 2, 3, 4, 5 | Two field omissions with no authorizing rule in `handoff-format.md`. | **Contract gap in `_shared`, not skill defects.** (a) The researcher omits `plan:` — its own rendering authorizes this explicitly ("the issue has no plan yet"), but `handoff-format.md`'s omission-rule list never mentions `plan:` as omittable. (b) Legs 3–5 omit `research:`, though #101 *did* go through the researcher; the rule says omit only for issues that "never went through the researcher". A **decline posts nothing**, so no downstream prep can discover that research happened — the marker is structurally unrecoverable after a `✗`. **Fix:** add `plan:` to the omission rules, and reword the `research:` rule to "no dossier exists" rather than "never went through". |
| 6 | 4 | No draft→ready flip: the resolver opened PR #102 non-draft. | **Correct for the shape.** The draft→ready flip exists so a multi-phase PR isn't evaluated mid-build; a single-phase issue ships in one push with nothing to protect. The criterion is written for the multi-phase shape. `gh pr ready` was never executed (the one scrollback hit is the session's prose explaining why it wasn't needed). |
| 7 | 1, 4, 5 | Three legs opened with a one-line `git remote -v` probe before calling prep; legs 2 and 3 instead inlined `$(gh repo view --json nameWithOwner -q .nameWithOwner)` so their **first** tool call was prep. | **Non-blocking, but the cross-cutting check's literal wording fails in 3 of 5 legs.** The prep scripts take `<owner/repo>` positionally and no router says where to obtain it, so each session invents a way — two inlined it, three probed first. State assembly is still exactly one call everywhere. The discarded first attempt burned an extra `prep_drafter.py --help` on the same uncertainty. **Fix:** prescribe the slug derivation in the routers (the `$(gh repo view …)` form works), or let prep default to the ambient remote when the argument is absent. |
| 8 | 3 | The issue-body plan pointer reads "authored by `github-issue-planner`; **re-run that skill** to revise." | **Frozen contract token behaving as specified — and the same wart the run was originally proposed to fix.** [prd.md §7](../../prd.md) freezes these provenance strings for byte-compatibility with cross-consuming v1 readers, so this is not a stale reference. But unlike the plan-comment footer, this string is a **live instruction to a human**, telling them to re-run a command that no longer exists. Same defect class as the `<!-- github-pipeline-config -->` header's "Re-run `github-pipeline-setup`". **Not a run failure**; recorded because the run found it independently. |

## Cleanup

After the run: `git worktree remove` any leftover workspace, delete the `/tmp/s20-conveyor` clone,
and leave the merged PR + closed issue in place as the run's evidence.

**Done.** The work worktree was already gone (leg 5, by hand — Div-3); the leftover was the
planner's `ro-main` read workspace, which is `gc`-by-age and not any skill's to remove mid-run. The
clone was deleted after the record was written. Issue #101 and PR #102 are left in place as
evidence, along with the local branch `101-…` that leg 5 deliberately kept so the pre-squash commit
`3fd513d` stays reachable — that branch died with the clone, but `3fd513d` is recorded here and in
the PR's own history. Sandbox `main` is now `461e73c` and carries `tests/` for the first time, which
future runs against this sandbox should expect. `pytest` and `flake8` were installed on the host
(user scope) and left installed — the sandbox's declared gates need them.

## Go/no-go (operator) — the run's last

- [x] All five legs pass. — 5/5, with Div-2 (leg 1's researcher-routing criterion) adjudicated as a
      spec error and Div-3 (leg 5's teardown) as a real defect that did not change the end state.
- [x] All five handoffs are schema-valid and every next-command ran as printed. — **4 of 4 printed
      commands ran verbatim and worked**; leg 5 is terminal by design. Leg 2's handoff is
      schema-valid except for the unauthorized `plan:` omission (Div-5a), and no handoff needed
      editing. The 1→2 hop had no printed researcher command to run (Div-2).
- [x] Cross-cutting checks pass. — one state assembly per session, root untouched at all six
      boundaries, zero stale names, all markers verbatim.
- **Operator verdict (2026-07-25): GO.** Ruled by the operator at the run's close: the whole-system claim held (#101 → PR #102 → main@461e73c, every handoff schema-valid, 4/4 next-commands run as printed, one state assembly per session), all three conveyor findings dispositioned (row 2 resolved as doc truth; rows 1 and 3 filed-candidates for post-run product issues). The v2 rewrite is accepted end-to-end.

**The claim held.** One issue, drafted from informal feedback, reached a merged PR on the sandbox's
`main` through five separate sessions — [#101](https://github.com/danwashusen/gh-pipeline-sandbox/issues/101)
→ [#102](https://github.com/danwashusen/gh-pipeline-sandbox/pull/102) → `main@461e73c`, issue closed,
`src/initials.py` + `tests/test_initials.py` both on `main` — with four of the five sessions started
by copy-pasting the previous session's printed command verbatim and nothing but GitHub artifacts and
the `## Handoff` bridging them. No session read another's transcript; no skill crossed a session
boundary via the `Skill` tool.

**What the composition actually surfaced.** Eight divergences, of which three are real and worth
acting on before the next release:

1. **Div-2 — the researcher is unreachable by handoff.** The documented five-stage pipeline is a
   four-stage pipeline in the tree. This is the single most valuable thing the run found, and it was
   invisible to all eight per-skill parity runs precisely because each ran one stage in isolation
   against hand-constructed state. It is the exact failure mode the go/no-go predicted.
2. **Div-3 — `workspace.py remove` cannot complete the evaluator's own teardown** after a
   squash-merge with `--delete-branch`, failing on bytecode its own health gate wrote and then on a
   structurally-unavoidable `unpushed_commits: 1`. Every clean merge will hit this.
3. **Div-1 — a `bug`-classified issue carries no DoD**, so the DoD contract that three skills share
   is silently skipped for the most common issue type.

The other five are contract-wording gaps (Div-5, Div-4), a criterion written for a different shape
(Div-6), an unspecified slug derivation (Div-7), and a frozen-token wart that is behaving as
specified (Div-8).

- **Recommendation (implementor):** **GO**, with Div-2 and Div-3 filed before the next release.
  The conveyor composes: state flows stage-to-stage through nothing but GitHub artifacts and the
  handoff, the workspace topology held under a real build ([prd.md §8.1](../../prd.md) never once
  violated), and the DoD contract projected and verified end-to-end. Every divergence traces to a
  spec/skill contract mismatch or a named script guard — none is an unexplained behavior. Div-2 is
  a routing/documentation defect, not a composition failure: the chain still reached merge, and the
  researcher leg ran correctly when invoked directly.
- **Pre-run note (implementor), kept for the record:** the offline half of S20 is complete and green
  (boxes 1, 2, 3, 5 — see the S20 implementor report); box 4 is this run. The conveyor's composition
  has never been exercised in one chain, so this is the one place a seam between two accepted skills
  could still surface — most plausibly in a handoff's next-command rendering, which is exactly what
  the table above measures. **That prediction was correct** — Div-2 is a handoff next-command
  rendering defect.
