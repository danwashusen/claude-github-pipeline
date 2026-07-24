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

- [x] **D1 (report structure preserved)** — v2's report has the carried fixed shape: `# Doc review —
  <doc path> (guide: <basename>)`, a `Verdict:` line, `## What's working`, `## Findings` ordered
  🔴 Blocker → 🟡 Should-fix → 🟢 Consider (each with `guide:` / `doc:` refs), and a `## Guide
  checklist`; a section with no findings says so rather than padding. Structurally matches the v1
  vantage render; every finding traces to a guide principle/anti-pattern/checklist item (stack-agnostic
  — no "this isn't how the example does it").
- [x] **D2 (apply mode — landing approved)** — accept some findings, approve the landing: a PR opens
  whose body summarizes the doc changes, head `doc-reviewer/<doc-slug>`, base `main`; the doc `Edit`s
  all happened **in the workspace** and the project **root is clean and on `main` throughout**
  (prd.md §8.1/§8.2).
- [ ] **D3 (apply mode — landing declined)** — on a fresh clone, accept findings but **decline** the
  landing: **no** commit, push, or PR; the summary reports the workspace path
  (`.worktrees/doc-reviewer/<doc-slug>`) and the exact ready-to-run landing commands (which run as
  printed — `pr.md` was staged before the gate).
- [x] **D4 (v2 process)** — startup = **no prep call** (the operator names the doc); **0**
  `github-ops`; the guide is read from the plugin bundle, never the consuming repo; the guide is never
  edited; writes are exactly the workspace doc edits + the optional `gh_persist.py create-pr`. The
  `disable-model-invocation: true` frontmatter means the skill fires only on explicit
  `/github-pipeline:doc-reviewer`, never model-auto-invoked.
- **Result: D1 PASS (report structure), 2026-07-25** — this leg was scoped to the
  **report-structure parity read only**: both legs were driven to the apply gate and **declined** (accept
  no findings), so the run is report-only on both sides and the two §8.2 landing legs were deferred.
  **D2 + D4 PASS** in Scenario 2 below (2026-07-25); **D3 remains TODO** (Scenario 3, the decline leg).

  **Harness.** tmux interactive harness ([`setup.md`](setup.md) Scenario-1 recipe + the S18 Scenario-1
  `--allowedTools` upgrade): `claude --plugin-dir <dir> --model opus --allowedTools Bash Read Grep Glob
  Task TodoWrite Edit Write WebFetch`, cwd = a fresh sandbox clone per leg (`/tmp/s19-v1`, `/tmp/s19-v2`),
  both at sandbox `main` `ff490b3`. The v1 leg ran against the **naming-rider-2 vantage**
  (`git worktree add /tmp/v1-vantage-s19 7bffb90`; `--plugin-dir /tmp/v1-vantage-s19`), the v2 leg against
  this branch. `docs/guides/` is **byte-identical** between `7bffb90` and `HEAD` (`git diff 7bffb90 HEAD --
  docs/guides/` is empty), so both legs measured against the same rubric. Transcripts:
  `~/.claude/projects/-private-tmp-s19-v1/0d526fd3-….jsonl` (v1),
  `~/.claude/projects/-private-tmp-s19-v2/b6da4445-….jsonl` (v2). Gate answers: v1 declined in prose ("No —
  do not apply anything"), v2 selected **"Nothing — report only"** on its `AskUserQuestion` card.

  **Fixture (seeded for this run).** The sandbox had no `constitution.md`, and its `prd.md`/`architecture.md`
  are 14-/10-line stubs — too thin to exercise all three severity tiers. Seeded `docs/constitution.md`
  (28 lines, 8 numbered rules, Python-flavored so the guide's **Rails** worked example is a live
  stack-agnosticism trap) as sandbox `main` `d18fc3c → ff490b3`, **pushed** so both legs and the later
  landing legs fork from the same commit (the [`setup.md`](setup.md) Scenario-1 local-drift lesson —
  `workspace.py ensure --work` forks at `origin/<base>`, so a local-only seed gives `ROOT_DIVERGED`). Five
  planted defects, one per guide rule-class — §3 deviable `httpx` preference stated as law *with* rationale
  prose (principle #2/#6), §4 test-first mandated as unverifiable *order* with no coverage bar / no-merge-on-red
  (the guide's last anti-pattern + "Omitting the testing bar"), §5 version-pinned runtime + library defaults,
  §6 aspirational "code should be clean" (the guide's literal counter-example), §7 build/test commands that
  belong in `CLAUDE.md` marker blocks — against three deliberately clean rules (§1 layers, §2 secrets,
  §8 logging) plus a correct preamble, so "credit what's right" had real material to find.

  - **D1 — PASS.** Section set, order, and per-element shape are the same on both legs, and the carried
    `references/review-lenses.md` §"Report shape" is honored by both:

    | Element | v1 (vantage `7bffb90`) | v2 (this branch) |
    |---|---|---|
    | `# Doc review — <doc path>   (guide: <basename>)` | ✅ (paths backticked) | ✅ |
    | `**Verdict:** <closed-set token> — <one-line rationale>` | ✅ `Significant drift` | ✅ `Significant drift` |
    | `## What's working` (grounded, guide-cited) | ✅ 6 bullets | ✅ 5 bullets |
    | `## Findings`, ordered 🔴 → 🟡 → 🟢 | ✅ 3 / 2 / 1 | ✅ 3 / 2 / 2 |
    | `### <emoji> <tier> — <title>    guide: … · doc: …` | ✅ every finding | ✅ every finding |
    | `## Guide checklist`, `- [x]`/`- [ ]` + evidence | ✅ 6 items | ✅ 6 items |
    | Ends with a plain summary, **not** a `## Handoff` | ✅ prose recap | ✅ labeled `## Summary` |

    **Severity markers** are the carried 🔴/🟡/🟢 glyphs on both, in the carried Blocker → Should-fix →
    Consider order, with no interleaving. **The five 🔴/🟡 findings are identical across legs** — same
    target rule (§4, §6, §3 blockers; §5, §7 should-fixes), same guide citation class, same prescribed
    fix, and both independently reached "delete in place, leave the numbering gap, never renumber". The
    **guide-checklist verdicts are identical item-for-item** (`[ ] [x] [ ] [x] [ ] [ ]`), each with doc
    evidence. All five planted defects were caught by both legs; both credited §1/§2/§8 + the preamble.
    No empty section on either leg, so the "state an empty section rather than pad it" rule was not
    exercised (recorded, not a gap in D1 — the fixture has findings in every tier).

    **Honesty rules — honored on both legs.** *Credit what's right*: both opened with a substantive
    `## What's working` naming the three sound rules and the preamble, each with a guide ref. *Only review
    against what the guide says*: every finding on both legs cites a guide principle, anti-pattern,
    checklist item, or sibling-doc table row — **no invented findings** and no generic doc-writing opinion.
    *The worked example is an illustration*: the doc is Python and the guide's worked constitution is Rails;
    **neither leg raised a similarity finding**, and v1 went further, crediting *"Stack-appropriate, not
    example-cloned — Python rules, not transliterated Rails"* explicitly (v2 honored it silently — Div-5).

  - **D4 — partially evidenced (box left unticked; the write half needs the landing legs).** Observed this
    run: startup was **no prep call** on either leg (the operator named the doc — router §1's deliberate
    absence, live-confirmed); **0** `github-ops` and **0** `Agent` dispatches on both; the guide was read
    from the **plugin bundle** on both (`/tmp/v1-vantage-s19/docs/guides/constitution.md` for v1,
    `<this branch>/docs/guides/constitution.md` for v2), never the consuming repo; the guide was never
    edited. Zero writes verified: both clones end clean on `main` at `ff490b3`, `docs/constitution.md`
    `sha1 991a4dd8…` unchanged on both, **no `.worktrees/`**, no `doc-reviewer/*` branch local or remote,
    no new PR (sandbox still tops out at #93). Tool census — **v1: 3 calls** (2 `Read` = doc + bundled
    guide, 1 `ls`), **v2: 7 calls** (4 `Read` = the router-forced `playbooks/review-flow.md` +
    `references/review-lenses.md`, then doc + bundled guide; 1 `ls`, 1 `Grep`, 1 `AskUserQuestion`);
    **0** `Edit`/`Write`/`gh`/`gh_persist.py`/`workspace.py` on both.

  **5 divergences — none blocks D1; three are the expected §8.2 enrichment, two are judgment-tier:**
  1. **Div-1 — 🟢-tier composition differs (judgment, not structure).** v1 emitted **one** Consider (the
     preamble points rationale at `docs/architecture-notes.md`, which doesn't exist in the repo); v2 emitted
     **two** (§1's "entry-point scripts" has no path anchor; `CLAUDE.md` doesn't `@`-include the
     constitution) and folded v1's observation into its §3 blocker as a heads-up plus its closing note. Both
     legs' Considers are guide-grounded (v2's second cites the guide's own "*the skills assume `CLAUDE.md`
     `@`-includes `docs/constitution.md`*"), and 🟢 is by definition the nuance tier — "conciseness, phrasing,
     or nuance". The 🔴/🟡 sets, where the report's stakes live, are identical. v2's `CLAUDE.md` finding
     targets a file *other than* the doc under review; it self-scopes correctly (`doc: n/a (repo CLAUDE.md)`
     and *"flagging, not folding into an apply"*), so it is not an apply-scope leak.
  2. **Div-2 — v2 interposes a "Renumbering note" between the last finding and `## Guide checklist`.**
     A one-paragraph note ("removing §3, §5, §6, §7 leaves gaps. That is correct… I will leave the gaps and
     never renumber survivors") sourced from `review-lenses.md` §"Apply-time discipline". v1 carried the same
     rule but stated it inline inside its §6 finding. **v2 enrichment** — it displaces no section of the
     carried shape and reads as a bridge into the apply gate.
  3. **Div-3 — the apply offer's channel differs, by design.** v1 asked in prose ("Want me to apply these?");
     v2 raised a real `AskUserQuestion` multi-select naming the accept scopes plus an explicit
     **"Nothing — report only"**, and its preamble states the §8.2 model up front ("*Edits stage in a work
     workspace — nothing touches the repo root, and the landing… is a separate gate afterwards*"). Expected:
     v1 had no workspace/landing at all (it `Edit`ed in place), which is the behavior v2 **adds**.
  4. **Div-4 — v2's closing summary is labeled and structured; v1's is prose.** v2 ends with `## Summary` /
     **Doc reviewed** / **Verdict** / findings / **Applied** / **Landing** per router §4, explicitly reporting
     *"No workspace was created, no files were edited, and no git or `gh` commands were run"*; v1 gave an
     unlabeled recap. Both are plain summaries — **neither emitted a `## Handoff`**, correct for a
     non-pipeline tool.
  5. **Div-5 — cosmetic render deltas.** v1 backticks the doc path and guide basename in the H1 and uses a
     single-spaced ` · ` in some finding headers; v2 renders the H1 unbackticked and uses the carried shape's
     `  ·  ` spacing throughout, and states its stack-agnosticism by *not* raising a similarity finding rather
     than crediting it explicitly as v1 did. No contract token is affected either way.

### Scenario 2 — apply mode, landing **approved** (D2, and D4's write half)

**v2-only by design.** v1 `doc-reviewer` `Edit`s the doc in place and has no workspace/landing at all
— the §8.2 gate *is* the v2 addition — so there is no v1 twin to diff; the comparison is against the
specced contract (the same twin-less shape as [`question-pair.md`](question-pair.md) Scenario 2).

**Harness.** tmux interactive harness (the [[s19-scenario1-report-structure]] recipe): `claude
--plugin-dir <this branch> --model opus --allowedTools Bash Read Grep Glob Task TodoWrite Edit Write
WebFetch`, cwd = a **fresh** sandbox clone `/tmp/s19-d2` at `main` `ff490b3`. Fixture reused
unchanged: the Scenario-1 seeded `docs/constitution.md` (`sha1 991a4dd8…`), so the five planted
defects are the accept material. Transcript:
`~/.claude/projects/-private-tmp-s19-d2/6951eb85-….jsonl`. Two gates, both real `AskUserQuestion`
cards: the apply gate → **"Blockers + should-fix (5)"**; the landing gate → **"Yes — commit, push,
open PR"**.

- **Result: D2 PASS + D4 PASS, 2026-07-25.**

  **D2 — PASS.** PR [#99](https://github.com/danwashusen/gh-pipeline-sandbox/pull/99) opened, title
  `Doc review — docs/constitution.md`, head **`doc-reviewer/constitution`**, base **`main`**, state
  `OPEN`. Its body **is** the doc-change summary — per-finding, each naming the guide rule it answers,
  plus a "Rule numbering is unchanged" paragraph and a "Follow-ups not included here" section. The
  `create-pr` envelope returned `"body_bytes": 3520`, `"body_sha256": "7c3437b5…"`, matching
  `shasum -a 256 /tmp/gh-doc-reviewer-constitution/pr.md` exactly — the staged file landed byte-for-byte
  (GitHub's read-back adds one trailing newline; no other delta).

  *Edits in the workspace only.* The single `Edit` targeted
  `/private/tmp/s19-d2/.worktrees/doc-reviewer/constitution/docs/constitution.md`; the workspace holds
  commit `f210fc9` on `doc-reviewer/constitution`, parent `ff490b3`.

  *Root clean throughout.* `git -C /tmp/s19-d2 status --porcelain` was **empty** and `HEAD` was
  `main` `ff490b3` at **four** boundaries — pre-run, after the apply gate, after the workspace `Edit`,
  and after the landing — and `docs/constitution.md` in the root still hashes `991a4dd8…`, unmodified.
  `workspace.py` had written `.worktrees/` into `.git/info/exclude`, so the workspace itself never
  shows as untracked.

  *§-anchors stable per the apply-time discipline.* Surviving rules are **§1, §2, §4, §8**; the
  retired §3/§5/§6/§7 leave **gaps**, nothing was renumbered. §4 was rewritten in place (keeping its
  number) even though it moved up positionally. The run grepped `constitution §` across the repo
  before editing, confirmed no citation would dangle, and said so in both the PR body and the summary.

  **D4 — PASS (both halves now evidenced).** Startup = **no prep call** (the operator named the doc);
  **0** `github-ops` and **0** `Agent`/`Task` dispatches; the guide was read from the **plugin bundle**
  (`<this branch>/docs/guides/constitution.md`) and never edited. Full census: **8** `Bash`, **5**
  `Read` (router-forced `playbooks/review-flow.md` + `references/review-lenses.md`, the doc, the
  bundled guide, the workspace doc), **2** `AskUserQuestion`, **1** `Write` (`pr.md`), **1** `Edit`
  (the workspace doc). Writes were exactly the workspace doc edit + the workspace `git
  add`/`commit`/`push` + `gh_persist.py create-pr` — no hand-rolled `gh` write anywhere. Both scripts
  were invoked **directly as executables**, so the S17 Scenario-1 Div-1 (`0644` prep/workspace
  scripts, exit 126) is **live-confirmed fixed**.

  **The S18 Scenario-2 Div-4 fix holds — live-confirmed.** `pr.md` (3520 B) existed on disk **before**
  the landing gate was answered, and the pre-gate turn said so verbatim: *"The PR body is already
  authored at `/tmp/gh-doc-reviewer-constitution/pr.md`."* Approve and decline share one authored
  file, exactly as playbook §5 requires.

  **Sibling-doc discipline held.** The removed §3/§5 content was **not** written into
  `docs/architecture.md`/`docs/architecture-notes.md`; the summary and the PR body both list that as a
  separate offer — review-lenses §"Apply-time discipline" (*"moving content into a sibling doc is a
  separate offer, never bundled with an accept"*), conformant.

  **3 divergences — none blocks D2/D4:**
  1. **Div-1 — the approve path's git ops ran on the *inherited* Bash cwd, not `git -C <workspace>`.**
     A prior verification step did `cd /private/tmp/s19-d2/.worktrees/doc-reviewer/constitution && git
     diff --stat …`, and the landing then ran a bare `git add … && git commit … && git push …`. Correct
     here (Bash cwd persists within a session, and the root stayed clean — verified), but playbook §5
     prints the **decline** path's commands in the explicit `git -C <workspace>` form; the approve path
     should use the same form. A cwd-inherited `git add` is one step-reordering away from staging in the
     read-only root, which is the exact invariant §8.1 exists to protect. **v2 defect (latent), TO FIX:
     make §5's approve path prescribe `git -C <workspace> add/commit/push`.**
  2. **Div-2 — the apply gate rendered as a *single*-select over bundled scopes** ("Blockers +
     should-fix (5)" / "Blockers only (3)" / "All 7 findings" / "None — report only"), where Scenario 1's
     run rendered a **multi**-select over per-finding scopes. Playbook §5 says only "apply **only** the
     findings the operator accepts" and does not pin the card shape, so both renderings satisfy it —
     but the bundled form is coarser (it cannot express "these two blockers and that should-fix"). The
     card did carry an explicit report-only escape, and the accepted set was applied exactly.
  3. **Div-3 — the workspace commit carries a `Co-Authored-By: Claude Opus 5` trailer.** Not prescribed
     (or forbidden) anywhere in the playbook; cosmetic, recorded for completeness.

  **Sandbox state this leaves for Scenario 3 (the decline leg).** PR **#99 is open** and the remote
  branch **`doc-reviewer/constitution` exists**. Scenario 3 needs a **fresh clone** *and* a reset first
  — close #99 and delete the remote branch — otherwise `workspace.py ensure --work
  doc-reviewer/constitution` meets a pre-existing remote branch instead of forking cleanly at
  `origin/main` (the [[s17-scenario2-landing-declined]] lesson). `/tmp/s19-d2` is left intact as
  evidence.

## Go/no-go (operator)

- [ ] Scenario 1 PASSES (report structure parity + both landing legs; every divergence adjudicated as
  an explained v1 defect / fixture artifact / v2 enrichment).
- **Operator verdict: _(fill)_.**
- **Recommendation (implementor): GO on the offline half.** The router's structural / frontmatter /
  contract-token / no-prep / landing / report-structure / carried-lenses / stack gates and the census
  zero-drop are implementor-complete and green (1143 tests). The interactive scenario (report-structure
  parity on one sandbox doc + the two §8.2 landing legs) is scaffolded above and awaits the operator's
  tmux-harness run.
