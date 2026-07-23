# Parity — `doc-reviewer` (v1→v2, the eighth and final skill cutover)

> Records the [implementation.md](../../implementation.md) **S19** parity run per the parity protocol
> (`## The parity protocol`) and [prd.md §9.5](../../prd.md). The offline work (the router + its one
> playbook + the carried `references/review-lenses.md` + `tests/test_doc_reviewer_routing.py`) landed
> in S19's implementor pass; the **live scenario below is operator-gated** (the report-structure
> parity read on a sandbox doc, plus the two §8.2 landing legs, all interactive `AskUserQuestion`), so
> an operator runs it on the sandbox ([SANDBOX.md](../../../tests/SANDBOX.md)) and fills each result
> section. `doc-reviewer` is the **last** skill cutover; S20 retires the remaining v1 dirs.

## Naming-collision adjudication — Option A (authorized, riders-bound)

The v2 `doc-reviewer` skill's name **equals** the frozen v1 skill's name — the same collision class
S18 adjudicated for `question-resolver` ([question-pair.md](question-pair.md) §"Naming-collision
adjudication"). The collision was two-fold — same dir path (two `SKILL.md`s can't share it) **and**
same registry `name:`. **Option A** — early-retire only the v1 `skills/doc-reviewer/` dir now (a
one-dir partial S20) — was **pre-authorized with three riders**:

1. **Retirement is its own labeled first action.** `skills/doc-reviewer/SKILL.md` (144-line, the only
   file in the dir — no `references/`, no `playbooks/`; **144 deletions**) was removed as the first
   working-tree change; the pre-retirement **v1 vantage is `7bffb90`** (the last commit carrying the
   dir). The v1 behavior is preserved verbatim in three places: this repo's git history at `7bffb90`,
   the S1 baseline spec [`docs/specs/doc-reviewer.md`](../doc-reviewer.md), and the vantage worktree
   the report-structure scenario's v1 leg runs against (below).
2. **The parity v1 leg runs against the vantage.** Because the v1 dir is gone from `HEAD`, the
   report-structure scenario's v1 leg points `--plugin-dir` at a worktree checked out at `7bffb90`
   (commands in the scenario below — the S18 Scenario-3 recipe verbatim-adapted).
3. **Recorded as an authorized, riders-bound §11-adjacent deviation** (deletion-before-parity for ONE
   dir, forced by the name collision, the reference preserved via spec + git + vantage). **S20 note:**
   S20 will find `skills/doc-reviewer/` already gone (a v2 dir in its place) — it retires the *rest* of
   the v1 dirs; this one dir was retired early here, and S20's census diff should expect the v1
   `doc-reviewer/SKILL.md` absent.

## Line-count metrics ([prd.md §10](../../prd.md); the §9 size bar)

**The binding bar for S19 is the architecture.md §9 router bar (≤ 150), not the ≤half-v1 metric.** The
S19 plan step's DoD carries **no line-count box** (its boxes are the report structure, the two landing
legs, and the `disable-model-invocation` grep gate). The ≤half-v1 metric is therefore **recorded, not
enforced** here — and it is legitimately **not met**, for the same structural reason S18 recorded and
the **S18 §10-scope ruling** ([question-pair.md](question-pair.md) §"Line-count metrics"): §10's
success metrics govern the *pipeline* stages, and the standalone tools are out of §10's reach, so the
half-metric is informational for them. v2 **adds** the prd.md §8.2 workspace+landing behavior (which
v1 `doc-reviewer` did not have — it edited the doc in place with `Edit`, no workspace/PR) onto the
**leanest** v1 standalone tool (144 lines), where halving leaves no room. A test still guards the
loaded set against unbounded growth (a **ceiling** — bumpable only with a recorded justification, the
S18 Scenario-2 Div-4 ceiling ruling), and asserts the router itself stays ≤ 150.

| File | Lines |
|---|---:|
| `SKILL.md` (router) | 77 |
| `playbooks/review-flow.md` (the one flow) | 71 |
| **router + playbook (loaded set)** | **148** |
| `references/review-lenses.md` (on-demand, not counted) | 100 |

- **Router bar:** **77 ≤ 150** ✅ (architecture.md §9). Router + playbook fits one default `Read`.
- **≤half-v1 metric (recorded, NOT met):** half = floor(144/2) = **72** (loaded 148). Rationale above.
  Pinned informationally by
  `RouterStructureTests::test_loaded_set_under_ceiling_and_half_metric_recorded` (a ceiling guard at
  **155** + an assertion that promotes the bar to enforced the day the loaded set drops under its
  half). The reference (`review-lenses.md`, 100) is force-read at review time but is **on-demand, not
  counted** — the same convention as `question-sweep`'s reader and `setup`'s `block-authoring.md`.

## The prep decision — no prep (the §9 house-default call the Work records)

**doc-reviewer has no prep script — VERIFIED against the S1 spec.** [`docs/specs/doc-reviewer.md`](../doc-reviewer.md)
§"Deterministic steps" and §"Overview" both record that v1 dispatches **no** `github-ops`, invokes
**no** `gh` anywhere in its 144 lines, and "there is no prep script (nothing to gather)": its two
inputs are working-tree paths — the doc under review (named by the operator) and its bundled guide
(`${CLAUDE_PLUGIN_ROOT}/docs/guides/<basename>.md`). No remote state, no issue/PR, no registry. The
router's §1 pins this absence explicitly ("**No prep script — nothing to gather**… This absence is
**deliberate**") so a future editor reads it as intent, not omission. Pinned by
`NoPrepAssertionTests` (the assertion prose is present **and** no `prep_doc_reviewer.py` exists on
disk). This is the one v2 skill with no prep at all — every other skill's startup is a single prep
call; doc-reviewer's startup is the operator naming a path.

## The playbook-split decision (the §5-bar decision the Work records)

architecture.md §5 "parameterize before you playbook": a playbook exists only for flows that differ in
**actions**, not values. **doc-reviewer is a single linear flow — router + one playbook**
(`review-flow.md`): identify → read → review → report → [apply mode:] stage-in-workspace → land →
summary. Apply mode is **not** a route: the apply/decline and the §8.2 landing approve/decline are
**runtime gates inside** the flow (report-only is the flow with the apply gate declined). No mode fork
(no broad/targeted/revise, no epic/story). The detailed rubric (the five lenses, the honesty rules,
severity calibration, and the report shape) lives in the force-read `references/review-lenses.md`, not
restated in the playbook — the `setup`/`block-authoring.md` pattern.

## The `disable-model-invocation` frontmatter — RETAINED (S17/S18 rule)

Per the S17 adjudication ([setup.md](setup.md) §"disable-model-invocation") and the S18 restatement
([question-pair.md](question-pair.md) §"The `disable-model-invocation` frontmatter") — **setup was the
exception; the other standalone tools are the norm.** `doc-reviewer` carries
`disable-model-invocation: true` in its v2 frontmatter: v1 `doc-reviewer` carried it
(`SKILL.md:5` at the vantage), and `CLAUDE.md:73` names `doc-reviewer` among the three standalone
tools (`doc-reviewer`/`open-questions`/`question-resolver`) that keep the key. Pinned by
`RouterStructureTests::test_router_exists_and_frontmatter_pins` (asserts the key is **present**).

## The report structure carried (DoD box 1, offline anchor)

The v1 report shape — `# Doc review — <doc path> (guide: …)` / `Verdict:` /
`## What's working` / `## Findings` with `🔴 Blocker` → `🟡 Should-fix` → `🟢 Consider` / `## Guide
checklist` — is carried **verbatim** into `references/review-lenses.md` §"Report shape", alongside the
ordering rule (Blocker → Should-fix → Consider) and the "state an empty section rather than pad it"
rule. **There is NO `docs/specs/examples/` capture for a doc-review report** (a review is session
output, never a prd.md §7 persisted GitHub artifact — no issue/PR/comment), so box-1 parity is
measured **directly against this carried v1 shape and the vantage render**, not a byte-frozen capture.
Pinned by `ReportStructureTests` (the fixed structure is present verbatim; and a falsifiable guard
that fails the day a capture *is* added, forcing a byte-match instead).

## Carried-content fidelity (lenses + guide resolution — paths only)

The five review lenses (in fixed order), the three honesty rules, the severity calibration, and the
guide-resolution rule (basename match; bundle-only; guide read-only) are carried from the v1 vantage;
**only the file they live in changed** (v1 folded them into the one `SKILL.md`; v2 splits router
(guide table + invariants) / playbook (the flow) / reference (the rubric), the architecture.md §9
router+playbook anatomy). Pinned by `CarriedLensesTests`. The honesty rule "the worked example is an
illustration, not a template" is carried verbatim, including its **labeled multi-stack example**
(Rails + Swift/Python named as examples — the CLAUDE.md-allowed ≥2-stack form); it is the only place a
stack token appears in the skill and it sits in the on-demand reference, so the loaded prompt (router
+ playbook) stays stack-token-free. Pinned by `StackAgnosticTests`.

## The landing gate (post-Div-4 shape, DoD boxes 2/3 offline half)

Apply-mode doc edits follow the exact S17/S18 model (prd.md §8.2), inheriting the **S18 Scenario-2
Div-4 fix from day one**: accepted edits stage in a **work workspace** (`workspace.py ensure --work
doc-reviewer/<doc-slug> --base main --root <repo-root>`), the doc is `Edit`ed **inside** that
workspace, and the PR body (the doc-change summary) is **staged to `pr.md` BEFORE the landing gate** —
so approve and decline share one authored file. The landing (commit + push + a PR summarizing the doc
changes) is **one explicit final gate**. On **decline**: **no git actions** — the summary reports the
workspace path + ready-to-run landing commands, which **run exactly as printed** because `pr.md` is
already staged (citing an unstaged file is a defect). When no finding is accepted the flow is
report-only (no workspace, no landing). Pinned by `LandingGateLanguageTests` (flow + router prose,
incl. `test_pr_body_staged_before_the_landing_gate` and `test_decline_commands_are_runnable_as_printed`)
and `LandingPersistDryRunTests` (the `--dry-run` create-pr envelope: conformant, `would_run` present,
no url). No sub-agent is dispatched anywhere (v1 spec §"Sub-agents dispatched: None") — pinned by
`NoSubAgentTests`, which also confirms `references/` carries no `*-prompt*`/`*-sub-agent*` file, so the
S11 drift-check validator (`tests/test_subagent_prompts.py`) correctly has nothing here to auto-bind.

## Offline validators (S19 DoD, implementor half)

- `python3 -m unittest tests.test_doc_reviewer_routing` — 32 tests: the structural bars (router ≤ 150;
  loaded-set ceiling + half-metric recorded; one playbook); frontmatter pins (opus/high + **present**
  `disable-model-invocation`); the contract-token gate (0 `github-ops`/`github-pipeline:github-`/`GATHER_`
  /`PERSIST_`/`§P`/raw-gh-writes/`w/`); the no-prep assertion (prose pinned + no script on disk); the
  §8.2 landing gate language (post-Div-4: pr.md pre-gate + decline commands runnable-as-printed +
  report-only skip); the carried report structure + lenses + guide resolution + severity; no sub-agent;
  stack-agnostic (loaded prompt clean; reference multi-stack); the `--dry-run` create-pr.
- `python3 -m unittest tests.test_subagent_prompts` — green; discovery finds nothing new under
  `doc-reviewer/references/` (no decision-signal prompt), correctly.
- Census: **zero cross-skill drops**; distinct-token delta **+0**. The archive-diff (vantage `7bffb90`
  token set vs working tree, the S18 method) shows an empty drop set and an empty addition set: the v1
  dir's only contract token, `github-pipeline:doc-reviewer` (×2 in the v1 `SKILL.md`), survives in the
  v2 router's `description` (`/github-pipeline:doc-reviewer <doc-path>`), so it is not even a *new*
  token — the delta is 0, not S18's +1.
- Full offline suite: **1143** tests green (1111 baseline + 32 new).

## No read-only live smoke (implementor)

Unlike every prep-bearing skill, doc-reviewer has **no prep script to smoke** read-only — its startup
is an operator-named working-tree path, not a `gh` gather. The only remote write it can make is the
optional §8.2 landing PR, which is exercised offline via the `--dry-run` create-pr envelope
(`LandingPersistDryRunTests`) and live via the operator's landing legs below.

## Live parity scenario (operator-gated — fill each result)

Harness: headless `claude -p --plugin-dir` can't answer `AskUserQuestion`; the interactive gates (the
apply gate, the §8.2 landing) need the **tmux interactive-parity harness** (the
[[s17-scenario1-landing-approved]] recipe — the operator drives a real `claude --plugin-dir <this
branch> --model opus` session, cwd = a fresh sandbox clone). Don't pre-run anything in a run clone
(S13/S15 learning). A v1 skill directory is deleted only after its v2 replacement passes this protocol
(S20) — **except** `doc-reviewer`, retired early under the naming adjudication above.

### Scenario 1 — report structure (parity on one sandbox doc) + the two landing legs

Pick **one** of the five guided docs present in the sandbox (e.g. `docs/prd.md` or
`docs/constitution.md`). Run both legs against the **same doc at the same commit** so the report is a
true parity read.

**v1 leg vantage (naming rider 2).** The v1 `doc-reviewer` dir is gone from `HEAD`; run the v1 leg
from a worktree at the vantage (the S18 Scenario-3 recipe, adapted):

```bash
git worktree add /tmp/v1-vantage 7bffb90
claude -p "/github-pipeline:doc-reviewer docs/prd.md" --plugin-dir /tmp/v1-vantage --model opus   # (interactive: use the tmux harness for the apply gate)
# cleanup after: git worktree remove /tmp/v1-vantage
```

Run the v2 leg from `--plugin-dir <this branch>`. Diff the two report renders (structure + the
severity-tiered findings), then exercise the two §8.2 landing legs on the **v2** leg.

- [ ] **D1 (report structure preserved)** — v2's report has the carried fixed shape: `# Doc review —
  <doc path> (guide: <basename>)`, a `Verdict:` line, `## What's working`, `## Findings` ordered
  🔴 Blocker → 🟡 Should-fix → 🟢 Consider (each with `guide:` / `doc:` refs), and a `## Guide
  checklist`; a section with no findings says so rather than padding. Structurally matches the v1
  vantage render; every finding traces to a guide principle/anti-pattern/checklist item (stack-agnostic
  — no "this isn't how the example does it").
- [ ] **D2 (apply mode — landing approved)** — accept some findings, approve the landing: a PR opens
  whose body summarizes the doc changes, head `doc-reviewer/<doc-slug>`, base `main`; the doc `Edit`s
  all happened **in the workspace** and the project **root is clean and on `main` throughout**
  (prd.md §8.1/§8.2).
- [ ] **D3 (apply mode — landing declined)** — on a fresh clone, accept findings but **decline** the
  landing: **no** commit, push, or PR; the summary reports the workspace path
  (`.worktrees/doc-reviewer/<doc-slug>`) and the exact ready-to-run landing commands (which run as
  printed — `pr.md` was staged before the gate).
- [ ] **D4 (v2 process)** — startup = **no prep call** (the operator names the doc); **0**
  `github-ops`; the guide is read from the plugin bundle, never the consuming repo; the guide is never
  edited; writes are exactly the workspace doc edits + the optional `gh_persist.py create-pr`. The
  `disable-model-invocation: true` frontmatter means the skill fires only on explicit
  `/github-pipeline:doc-reviewer`, never model-auto-invoked.
- **Result: _(operator to fill)_**

## Go/no-go (operator)

- [ ] Scenario 1 PASSES (report structure parity + both landing legs; every divergence adjudicated as
  an explained v1 defect / fixture artifact / v2 enrichment).
- **Operator verdict: _(fill)_.**
- **Recommendation (implementor): GO on the offline half.** The router's structural / frontmatter /
  contract-token / no-prep / landing / report-structure / carried-lenses / stack gates and the census
  zero-drop are implementor-complete and green (1143 tests). The interactive scenario (report-structure
  parity on one sandbox doc + the two §8.2 landing legs) is scaffolded above and awaits the operator's
  tmux-harness run.
