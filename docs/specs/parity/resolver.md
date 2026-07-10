# Parity — resolver (v1 `github-issue-resolver` → v2 `resolver`)

> Records the [implementation.md](../../implementation.md) **S10** parity run per the
> [parity protocol](../../implementation.md) (`## The parity protocol`) and [prd.md §9.5](../../prd.md).
> The offline work (router + playbooks + references + tests) landed in S10's implementor pass; the
> **four live scenarios below plus the box-3 live refusal are operator-gated** — run them on the sandbox
> ([SANDBOX.md](../../../tests/SANDBOX.md)) and fill each result section. A v1 skill directory is
> deleted only after its v2 replacement passes this protocol (S20).

## Line-count metric ([prd.md §10](../../prd.md); S10 DoD box 7)

The success metric: the prompt a session loads (router + the one playbook it executes) is **at most
half** the v1 `SKILL.md` line count. v1 `github-issue-resolver/SKILL.md` = **1169 lines**
([baseline.md](../baseline.md) §1) → bar = **584** (floor of 1169/2).

| File | Lines |
|---|---:|
| `skills/resolver/SKILL.md` (router) | 128 |
| `skills/resolver/playbooks/resolve-spine.md` (the shared spine — largest) | 184 |
| `skills/resolver/playbooks/epic.md` | 114 |
| `skills/resolver/playbooks/comment-only.md` | 59 |
| `skills/resolver/playbooks/story.md` | 33 |
| `skills/resolver/playbooks/standard.md` | 28 |
| **router + largest playbook (the loaded set)** | **312** |

**312 ≤ 584** ✅. Router **128 ≤ 150** ✅ (architecture.md §9 size bar). References are read on-demand
and are not part of the loaded-prompt metric; recorded for completeness: `common-pitfalls.md` 240,
`review-loop-sub-agent.md` 221 (carried from v1), `epic-flow.md` 220, `handoff-renderings.md` 216,
`test-selection-sub-agent.md` 178 (carried), `issue-audit-prompt.md` 177 (carried),
`retry-ladder.md` 181, `state-distiller-prompt.md` 106 (carried), `dod-projection-rule.md` 104,
`follow-up-tracking.md` 92, `epic-baseline.md` 45.

A standard/story session loads router (128) + `resolve-spine.md` (184) + one thin routed playbook
(28–33) = **≤ 345**; the DoD's metric is *router + largest playbook* = 312 (the growth from the initial
298 across this step's two live-parity-driven fix rounds: the concrete `create-pr` invocation the
write-path prose now names, and the D2/D4 fixes below — the mandatory closing-keyword + title-shape
lines). An epic session loads router + `epic.md` (114) = 242; a comment-only session router +
`comment-only.md` (59, grown by the D1 question-type dispatch fix below) = 187. Each document fits one
default `Read`.

## Playbook split (the §5-bar decision the Work says to record)

architecture.md §5 "parameterize before you playbook": a playbook exists only for flows that differ in
**actions taken**, not in values. The split landed as a **shared spine + four routable playbooks** —
the S7 evaluator template, adapted to the resolver's shape:

- **`playbooks/resolve-spine.md`** — the code-shipping flow both the standard and story routes run
  (distill → audit → plan-gate → doc grounding → phases → code + review loop → per-phase push + DoD
  projection → follow-ups). The type differences here are **facts** — `audit_ref`, the work
  workspace's `base_ref`, the audit's dimension set, the handoff shape — never branches. Only the two
  routes that ship code read the spine.
- **`playbooks/standard.md`** — spine + the forward-to-evaluator handoff (base `main`, audit ref `main`).
- **`playbooks/story.md`** — spine + the `Story:`/`Epic:` handoff variant (base = the parent epic
  branch, audit ref = the parent epic branch, dimension-5 audit against siblings, the integration-branch
  caveat). Differs from `standard.md` only in **facts**, so both read the same spine.
- **`playbooks/comment-only.md`** — a distinct action flow: stage + post one comment (the OQ / native
  hard-refusal, or an answer/triage/decline). Opens no PR, does **not** read the spine.
- **`playbooks/epic.md`** — a distinct action flow: the epic-branch lifecycle (discover/bootstrap the
  `epic/<N>-<slug>` branch, drift rectification, the full-canonical baseline + trust state, the
  integration PR, the epic body-tick close-out). An epic is a container — no code lands here — so it
  does **not** read the code-shipping spine.

Why a spine + four routable playbooks rather than one monolithic file per type (each restating the whole
flow) or a single file with `if epic … else if story …` (banned by §5)? The code-shipping flow is
identical across the standard and story types up to *facts*; a shared spine keeps it in one place (no
drift). Comment-only and epic are genuinely different **actions**, so they are their own linear flows
that don't touch the spine. The five playbook files contain **zero cross-type conditionals** — the route
*is* the branch — verified by
`tests/test_resolver_routing.py::PlaybookInterleavingGrepTests` (both an `if … <type> … else` construct
grep and a "when the issue is a <type>" prose-branch grep). `continue` mode is parameterization inside
whichever playbook the type selects (`vector.mode` + `prior_pr` + `workspace.reused` drive it), not a
fifth flow.

## Contract-token census ([global DoD](../../implementation.md) skill-cutover clause)

The S1 baseline census ([baseline.md](../baseline.md) §2, distinct count **79**; grown to **81** at S7)
was re-run against the identical command after this cutover. Result: distinct count **83** — **zero
drops vs the S7 (81) or the S1 (79) baseline**, and the **+2** are both legitimate `skills/resolver/`
v2-namespace next-command tokens:

- `github-pipeline:evaluator` — the resolver forwards to the evaluator (the standard/story/epic-integration
  forward handoffs). No prior skill named the evaluator as a next-command (the evaluator's own handoffs
  point *forward* to `planner`/`resolver`, never at itself), so this token is net-new at S10.
- `github-pipeline:drafter` — the resolver re-routes to the drafter (fitness-audit blocker / doc-conflict).

New `skills/resolver/` files introduce **no** `github-ops`, **no** `GATHER_*`/`PERSIST_*` op names,
**no** `github-pipeline:github-*` v1 namespace strings, and **no** `§P` IDs (the resolver-local §P
scheme is retired). The resolver's own `<!-- …:v1 -->` / config-block markers it reads are all already in
the census from other skills (`<!-- implementation-plan:v1 -->`, `<!-- open-question-links:v1 -->`,
`<!-- issue-resolver-test-target -->`, `<!-- pr-evaluator-static-checks -->`,
`<!-- pr-evaluator-test-target -->`) — no new marker, no drop.

**Deliberate-retirement note (deferred to S20).** No v1 token retires at S10 — the v1
`skills/github-issue-resolver/` directory is untouched and still contributes all its baseline census rows
(the `§P1`–`§P6` IDs, `GATHER_ISSUE`/`PERSIST_COMMENT`, `github-pipeline:github-ops`, the
`github-pipeline:github-issue-*` handoff strings, its bare `§N` anchors). Those retire when S20 deletes
the v1 directory after this v2 replacement passes the live parity below; the S20 census diff accounts for
that drop then.

## Grep gates (S10 DoD box 5) — recorded green

Run over `skills/resolver/` (mechanized in `tests/test_resolver_routing.py::ContractTokenGateTests`):
- `github-ops` — **0 hits**.
- Old skill-invocation namespace (`github-pipeline:github-*`) — **0 hits**.
- v1 op names (`GATHER_*` / `PERSIST_*`) — **0 hits**.
- `§P` IDs (resolver-local; must not appear) — **0 hits**.
- Raw `gh` persist/gather **writes** in code fences (`gh issue|pr create|edit|comment|review|close|reopen`,
  `gh api … DELETE`) — **0 hits**. (The resolver has **no** scriptless raw-`gh` executor — merge and the
  draft-flip are the evaluator's; every resolver write is a `gh_persist.py` call.)
- Ref-arithmetic in code fences (`git show <ref>:<path>`, `git grep <ref>`) — **0 hits**. The fitness
  audit now reads a **read workspace** by absolute path (`facts.read_workspaces.audit.path`) instead of
  the v1 `git show <audit_ref>:` reads; test-selection's `git diff <target>...HEAD` branch diff is not
  the banned form; a bare `git show <commit>` view is permitted.
- `\bw/` banned shorthand — **0 hits**.

The only raw `gh` commands present are **reads** inside carried sub-agent prompts (the fitness audit's
`gh issue view` / `gh api …/comments` self-fetch, the review-loop's `gh pr view --comments` /
`gh api …/reviews` resume-hint read, the retry-ladder's `gh issue list` known-issue triage) and the
sanctioned draft→ready flip `gh pr ready <N>` (a PR-state toggle at the last-phase handoff, the same
executor the evaluator uses). None is a persist/gather-envelope write.

## Operator-gate + judgment coverage (S10 DoD box 4)

Every operator gate and judgment step in [resolver.md](../resolver.md) is present in the v2 skill (or
PRD-justified as absent). The gated-row card and the OQ refusal are called out explicitly.

### Operator gates ([resolver.md](../resolver.md) "Operator gates")

| S1-spec gate | v2 home |
|---|---|
| Ambiguous issue/repo (step 1) | prep's `AMBIGUOUS`/`MARKER_AMBIGUOUS` decision → SKILL.md §1 decision-card rule |
| Epic branch, multiple matches | prep `_discover_epic_branch` → `AMBIGUOUS` decision → SKILL.md §1 |
| Parent epic, multiple matches (Story flow) | prep `_search_parent_epic` → `AMBIGUOUS` decision → SKILL.md §1 |
| §4.5 audit BLOCKER exit | spine S2 (`header: "Audit"`: Revise via drafter / Override with reason / Abort) |
| §4.6 missing plan on non-trivial issue | spine S3 plan gate (freeform: run the planner / `proceed without a plan`) |
| §6 doc-conflict | spine S3 doc grounding (`header: "Doc conflict"`: Update the doc / Reshape issue / Override) |
| Step 5 — open PR by someone else, actively worked | **the gated-row card** — SKILL.md §1 "Gated-row card" (`vector.gate`, `header: "Open PR"`: Review it / Leave a comment / Wait) |
| Step 5 — stale PR by someone else | the gated-row card (`vector.gate`, `header: "Stale PR"`: Take it over / Start fresh) |
| Conflict handling (epic rectification) | epic.md S2 → `epic-flow.md` "Conflict handling" (`header: "Rectify epic"`: Apply all / Apply some / Abort — manual) |
| Retry-ladder escalation | spine S5 §8 gate → `retry-ladder.md` Escalation (`header: "Tests red"`: Push with reds / Defer / Restructure) |
| §10 iteration cap reached | spine S5.1 step 4 (`header: "Iter cap"`: Continue / Accept current / Abort) |
| §10 sub-agent `deadlock` guard rail | spine S5.1 step 3 → `review-loop-sub-agent.md` (`kind: deadlock`, `header: "Review loop"`) |
| §10 sub-agent `architectural` guard rail | spine S5.1 step 3 → `review-loop-sub-agent.md` (`kind: architectural`, `header: "Decision"`) |
| §10 sub-agent `verification_failure` guard rail | spine S5.1 step 3 → `review-loop-sub-agent.md` (`kind: verification_failure`, `header: "Tests red"`) |
| §10 sub-agent `grounding_violation` guard rail | spine S5.1 step 3 → `review-loop-sub-agent.md` (`kind: grounding_violation`, `header: "Grounding"`) |
| §4.7 operator-phase-complete fallback | `dod-projection-rule.md` "Operator-phase hybrid detection" step 2 (`header: "Op phase <N> done?"`) |
| End-of-§10 follow-up checkpoint | spine S7 → `follow-up-tracking.md` "The end-of-loop checkpoint" (freeform batch-approval) |

**OQ hard refusal (S10 DoD box 3's subject).** `open_questions_gate.blocked` (or an open native
`blocked_by`) → prep sets `comment_only`, the router routes to `comment-only.md`, which posts the
refusal-with-reason naming each blocking `question` tracker `#N` and does **no** code work. This is a
hard gate, not an `AskUserQuestion` — it needs no operator choice, only the posted refusal. Covered by
SKILL.md §1 "OQ hard refusal" + `comment-only.md` S1/S2. Verified live in the box-3 scenario below.

### Judgment steps ([resolver.md](../resolver.md) "Judgment steps")

| S1-spec judgment | v2 home |
|---|---|
| §3 current-state determination | **state-distiller** `Explore` (spine S1, `references/state-distiller-prompt.md`) |
| §4 response-type classification | main loop, consuming the distiller's `## Classification` (spine S1) |
| §4.5 fitness-to-implement audit | **fitness audit** `Explore` (spine S2, `references/issue-audit-prompt.md`) |
| §4.6 plan-gate materiality judgment | main loop on the distiller/audit exception (spine S1/S3) |
| §4.7 multi-phase detection | main loop, `facts.phases` + the distiller's parsed phases (spine S4) |
| Step 6 doc grounding (no-plan path) | main loop against the read workspace (spine S3) |
| Step 8 "stick to the plan" gap-filling | main loop (spine S5, common-pitfalls' plan-deviation rules) |
| Epic conflict-resolution proposal | `general-purpose` sub-agent (epic.md S2 → `epic-flow.md` "Conflict handling") |
| §8/§10.6 test selection | **test-selection** `Explore` (spine S5 / S5.1, `references/test-selection-sub-agent.md`) |
| Retry-ladder research breakpoint | `Explore` sub-agent (`retry-ladder.md` "Research breakpoint requirements") |
| §10 review-verdict classification + action | **review-loop** `general-purpose` (spine S5.1, `references/review-loop-sub-agent.md`) |
| §11 outcome-rubric classification | main loop → `references/handoff-renderings.md` (SKILL.md §4) |
| §12 handoff `Why:` authorship | main loop (SKILL.md §4) |
| Follow-up filing type/urgency classification | main loop + `general-purpose` drafter-proxy (spine S7, `follow-up-tracking.md`) |

No gate/judgment's absence traces to a PRD § — all are present.

## Renderings diff evidence (S10 DoD box 2, offline half)

Per artifact the resolver writes (from [resolver.md](../resolver.md) "Artifacts written"), the v2
rendering location ↔ its S1 `docs/specs/examples/` capture, at the schema level (byte-compatible where
the capture is frozen):

| Artifact | v2 rendering | S1 capture | Diff result |
|---|---|---|---|
| DoD checkbox projection (3 ticked forms) | `references/dod-projection-rule.md` "Annotation format" | `examples/dod-annotations.md` (rows for "resolver §9") | **byte-identical** — the three forms `(closed by phase <N>, commit <short-sha>)` / `(closed by phase <N>, operator action <ISO-date>)` / `(closed by commit <short-sha>)` appear verbatim; asserted by `test_resolver_routing.py::ArtifactRenderingByteCompatTests` |
| `## Phase tracker` | spine S6 + `dod-projection-rule.md` worked examples | `examples/phase-tracker.md` | schema-identical — `- [x] Phase <N> — <title> (commit <short-sha>)` code form, `(operator action <ISO-date>)` operator form; 7-char SHAs |
| `## Handoff` (9 shapes) | `references/handoff-renderings.md` | `examples/handoff-resolver.md` (the "Forward — standard/story PR opened" shape) | schema-identical; the sole divergence is the next-command namespace (`github-pipeline:github-pr-evaluator` → `github-pipeline:evaluator`), the deliberate v1→v2 rename — a live invocation, not a persisted-artifact byte (S7 adjudication precedent) |
| Epic `Baseline established` / `Baseline override` | `references/epic-baseline.md` | none (spec's Artifacts-written table is the source) | byte-faithful to the spec's fixed bodies (`🤖 Baseline established` 4-field / `🤖 Baseline override` 3-field) |
| PR body sections (`## Doc grounding`, `## Plan`, `## Audit override`, `## Plan override`, `## Predecessor`, `## Follow-ups`, `## Known failures`) | spine S5/S7, `follow-up-tracking.md`, `retry-ladder.md` | no frozen capture (free-prose PR-body sections) | section names + triggers preserved verbatim from the spec's Artifacts-written table |
| Comment-only response | `comment-only.md` S2 | no frozen capture (free-prose comment) | staged-body write via `gh_persist.py comment`, per the spec's staging-discipline invariant |

## PR-create write path (S10 implementor-reported gap — resolved within S10)

`gh_persist.py create` supports only **issue** creation (`--title`/`--label`/`--blocked-by`/`--blocking`)
— v1's `gh-persist.sh create` was likewise `gh issue create` only, and v1 hand-rolled `gh pr create
--body-file` directly (a Rule-7 divergence the resolver spec's "Known bugs / gaps" flags). This step's
implementor pass first **reported** the resulting gap (the v2 write path had no PR-open op, yet the
resolver's central output is a PR) rather than patch `scripts/` outside the brief's authorization.

**Resolution.** The orchestrator authorized an **additive** extension to `gh_persist.py` within S10
(architecture.md §2: "if a needed operation has no script, extend a script" — the S6
labels/workspace precedent). Landed: a new `create-pr` subcommand —

```
gh_persist.py create-pr <repo> <body_path> --title <title> --base <ref> --head <ref> [--draft] [--dry-run]
```

mirroring `create`'s body-bearing-write shape exactly (staged-file-path convention, the leading
`_verify_body_file` empty-body gate → `EMPTY_BODY_FILE`, unconditional `body_bytes`/`body_sha256`
receipts, the `--dry-run` preview convention, `AUTH_REQUIRED` classification via the pipelib runner).
`--base`/`--head` are required and explicit (no ambient-cwd branch inference, architecture.md §6).
`--draft` is optional, confirmed needed by v1 citation (`skills/github-issue-resolver/SKILL.md:896`:
the multi-phase fresh-PR-open path passes `--draft`, flipped ready via the pre-existing sanctioned
`gh pr ready` toggle at the last-phase handoff). No native-dependency flags — issue dependencies are
not a PR construct. **Existing `gh_persist.py` ops/envelopes are byte-identical** — `create-pr` is a
new subcommand branch touching no existing code path (verified: `tests/run.py` green, 646 tests, up
from 627 — the delta is entirely new tests, zero existing-test edits).

**Tests.** `tests/test_gh_persist.py::CreatePrHappyPathTests` (14 cases: ready + `--draft` happy path,
a story-shaped base, dry-run preview + `--draft` in preview, `EMPTY_BODY_FILE` (missing/zero-byte,
+ the never-calls-gh proof), usage errors (missing `--title`/`--base`/`--head`), `AUTH_REQUIRED`
classification, a hard non-auth `gh` failure, explicit `--cwd` forwarding). `tests/test_resolver_routing.py::PrCreateContractTests`
(6 cases: the op's existence + required-flag contract, dry-run shapes for the standard/story/multi-phase-draft/epic-integration
PR-open invocations the playbooks actually specify, and a check that the playbooks name `create-pr`
rather than a fabricated flag set).

**Playbooks updated.** `playbooks/resolve-spine.md` §"Open or continue the PR" and `playbooks/epic.md`
§S4 now name the concrete `create-pr` invocation (base/head as explicit facts, `--draft` only for
multi-phase) in place of the earlier prose-only "route through the write path" description. No other
playbook content changed.

**Box-6 prerequisite resolved.** Scenarios 1, 2, and 4 (the code-shipping / PR-opening scenarios) are
**unblocked** — a resolver run can now reach a PR through the single write path. All four scenarios plus
the box-3 refusal remain operator-gated (a live sandbox run), per the Live parity section below.

---

## Live parity scenarios (operator-gated — TODO)

Run each per the [parity protocol](../../implementation.md) steps 1–5 on the sandbox: construct the
target state, run **v1** `github-issue-resolver` capturing every GitHub write / gate / handoff / turn
count, reset (or twin the parent subtree for the epic/story flows), run **v2** `resolver` on the same
state, then compare: persisted artifacts **schema-identical** (marker line, section/heading set + order,
structured fields; confirmed by cross-consumption), same genuine decisions gated, handoff validates
against the shared schema, startup ≤ one state-assembly call. List divergences; each must trace to a PRD
requirement or be a filed defect. **Unexplained divergence fails the run.** The PR-create write path
(above) is landed — no further prerequisite blocks these; they remain operator-gated on a live sandbox
run.

### Scenario 1 — Fresh bug-fix, end-to-end

Target: a filed, planned `bug` issue (base `main`, plan present, no prior PR → `vector.mode: fresh`,
single-phase). Expected v2: state-distiller runs, fitness audit runs (clean), plan consumed, code in the
work workspace, review loop to approval, PR opened against `main`, single-phase DoD projection onto the
issue body, forward handoff to `/github-pipeline:evaluator #<PR>`.

**Fixture (twins on `danwashusen/gh-pipeline-sandbox`).** A buggy `salute(name, title)` helper seeded on
`main@e61fd39` in two parallel modules (`src/salute_a.py`, `src/salute_b.py` — the `_a`/`_b` twin split
that lets both legs open PRs against shared `main` without colliding): the body returns `f"Dear {name},"`,
dropping the `title` honorific its docstring documents. Two identical `bug`+`planned` issues each carry a
single-phase `## Definition of done` (2 bullets) and a verified single-phase `<!-- implementation-plan:v1 -->`
plan comment (no `## Phases`; `## Coverage gap` = `(none)` — the `src/` surface has no mirrored test
harness, so the compileall fast-check is the mechanical gate): **#31** (twin-A → v1 `github-issue-resolver`)
and **#32** (twin-B → v2 `resolver`). Headless recipe per the run-journal (`claude -p
"/github-pipeline:<skill> <n>" --plugin-dir <this branch> --model opus --permission-mode bypassPermissions`,
fresh sandbox clone per run, backgrounded stream-json log). The resolver opens a PR but never merges, so
`main` stays `e61fd39` across both legs (confirmed post-run) and the twins never contend.

- [x] v1 run captured (writes / gates / handoff / turns) — #31 → **PR #33** (`Fix: salute(name, title)
      includes the title honorific (#31)`, base `main`, head `issue-31-salute-title`), body led by **`Fixes
      #31`** → `closingIssuesReferences: [31]`, with `## Plan`/`## Doc grounding`/`## Summary`/`## Verification`
      sections. `/review` → **APPROVE, 0 addressable items** (posted as a `--comment`, self-authored-PR
      downgrade). **0** operator gates. Forward `## Handoff` → `/github-pipeline:github-pr-evaluator #33`
      (`PR:` line `review: APPROVE at 1ec807f · health: not run · merge: not run`). 26 turns / $3.98 / ~9 min.
      **v1 did NOT project the single-phase DoD** — issue #31's two DoD bullets stayed `- [ ]` (see D1).
- [x] v2 run captured (prep facts / sub-agent dispatches / writes / handoff / one state-assembly call) —
      **startup = 1 `prep_resolver.py 32` call** (the sole state-assembly call ✓); judgment sub-agents =
      state-distiller + fitness-audit + test-selection (×2: §8 gate + §10.6) `Explore` + one review-loop
      `general-purpose` — none is state-assembly. PR opened via **`gh_persist.py create-pr … --base main
      --head 32-bug-salute-… `** (single write path, explicit base/head — D3). `/review` → **APPROVE, 0
      items**. **0** operator gates. Forward `## Handoff` → `/github-pipeline:evaluator #34`. 36 turns /
      $4.17 / ~11 min.
- [ ] Artifacts schema-identical (PR body sections, single-phase DoD projection `(closed by commit
      <short-sha>)`, forward handoff) — **PARTIAL.** *DoD projection:* v2 applied it correctly — issue #32
      both bullets `- [x] … (closed by commit 61bd8e3)`, byte-matching the frozen S1 capture form; v1
      produced **no** DoD artifact this run (D1), so the two legs' projections are not directly comparable.
      *PR body sections:* `## Summary`/`## Plan` (link to the plan comment)/`## Doc grounding`/`## Verification`
      present on both — schema-consistent. *Forward handoff:* both are valid forward `## Handoff` blocks
      (`Issue:` + `PR:` + `Next:` + `Why:`), diverging only in the expected `github-pr-evaluator` →
      `evaluator` next-command rename. **But the PR-body *closing keyword* diverges: v2 omits `Fixes/Closes
      #<issue>` → `closingIssuesReferences: []` (D2, a filed defect).**
- [ ] Cross-consumption confirmed (the evaluator reads the v2 PR + projected DoD; a v1-projected DoD is
      read by the v2 evaluator) — **blocked by D2.** The v2 evaluator resolves the issue via the PR's
      `closingIssuesReferences` (`evaluate-spine.md:24`); with `[]` on PR #34 it trips the `No
      closingIssuesReferences` gate (`evaluate-spine.md:35`) instead of reading the projected DoD, so
      end-to-end cross-consumption cannot be confirmed until D2 is fixed and the leg re-run.
- [x] Gates match; handoff schema-valid; ≤1 state-assembly call — **0 = 0** operator gates on both legs;
      both handoffs are schema-valid forward blocks; v2 startup = **1** `prep_resolver.py` call, 0
      sub-agents for state assembly (distiller/audit/test-selection are judgment).
- [x] Divergences (each traced to a PRD § or filed as a defect):
      - **D2 — v2 PR is not Closes-linked (FILED DEFECT, blocking).** v1's fresh standard-PR body leads with
        `Fixes #31` (mandated verbatim at [`skills/github-issue-resolver/SKILL.md:888`](../../../skills/github-issue-resolver/SKILL.md):
        "PR body must include `Fixes #<number>` (or `Closes #<number>`) so GitHub auto-links and auto-closes
        on merge") → `closingIssuesReferences: [31]`. v2's PR #34 body carries **no** closing keyword →
        `closingIssuesReferences: []`: the issue↔PR auto-link and auto-close-on-merge are broken, and the
        downstream evaluator's `closingIssuesReferences` dependency ([`evaluate-spine.md:24`](../../../skills/evaluator/playbooks/evaluate-spine.md))
        trips its `No closingIssuesReferences → ask "Issue link"` gate (line 35). **Root cause:** the v2 spine's
        S5 "Open or continue the PR" fresh-mode staging ([`resolve-spine.md:99-109`](../../../skills/resolver/playbooks/resolve-spine.md))
        lists the body sections (`## Doc grounding` + `## Plan` + overrides + tracker + predecessor) but never
        the `Fixes/Closes #<issue>` keyword, while spine `S6:158` keeps v1's *narrow* prohibition ("never add
        `Closes #N` **in reaction to shipping a phase**") — so v2 retained the multi-phase-tick guard but
        dropped the fresh-open mandate. This also fell through the S1 spec: the resolver spec's
        Artifacts-written table ([`docs/specs/resolver.md`](../../resolver.md)) has a closing-keyword row only
        for the *epic-integration* PR (`Fixes #<epic-number>`), none for the standard/story fresh PR. On this
        same-account default-base PR the keyword would have populated the ref cleanly (the S7 gotcha), so the
        empty ref is caused **solely** by the missing keyword. No PRD § relaxes the standard-PR close-link →
        **not an explained divergence; a v2 regression vs v1.** *Fix:* add to the spine's S5 fresh-mode
        staging "the PR body's first line is `Fixes #<issue>` (or `Closes #<issue>`)" and add the matching
        standard/story fresh-PR closing-keyword row to the S1 Artifacts-written table; keep the `S6:158`
        phase-tick prohibition unchanged.
      - **D1 — v1 skipped its own single-phase DoD projection (EXPLAINED; non-deterministic v1 miss; v2 is
        the faithful leg).** Both skills mandate single-phase DoD projection identically — v1
        [`SKILL.md:868`](../../../skills/github-issue-resolver/SKILL.md) ("Then project the phase's `closes-dod`
        onto the issue body … apply via `gh issue edit`") + its §4.7 re-entry reconciliation
        ([`SKILL.md:441-443`](../../../skills/github-issue-resolver/SKILL.md)), and v2
        [`dod-projection-rule.md`](../../../skills/resolver/references/dod-projection-rule.md) "Single-phase
        fallback" ("tick every top-level DoD bullet on the first push"). v2 executed it (`61bd8e3`); **v1's
        opus run silently omitted the §9 `gh issue edit`** (no explicit reasoning in the transcript — it went
        audit→implement→push→PR→review→handoff), leaving #31's bullets `- [ ]`. This is a non-deterministic
        model-execution miss of a step v1's own spec mandates, with §4.7 re-entry reconciliation as the
        designed backstop — **not** a skill-contract divergence and **not** a v2 defect (v2 is the more
        faithful executor). Consequence for this run: a clean *both-legs* comparison of the DoD-projection
        artifact would need a fresh v1 re-run (moot while D2 blocks the scenario). v2's projection form is
        already verified byte-identical to the S1 capture offline (`ArtifactRenderingByteCompatTests`).
      - **D3 — PR-open mechanism (EXPLAINED; known v1→v2 cutover).** v1 hand-rolls `gh pr create
        --body-file` (the Rule-7 divergence the resolver spec flags); v2 opens through the single write path
        `gh_persist.py create-pr` with explicit `--base main --head <branch>` (no cwd inference). Same
        artifact intent; the mechanism change was called out up front. Not a defect (and orthogonal to D2 —
        `create-pr` writes whatever body it is handed; the missing keyword is the *staging* gap, not the
        script).
      - **D4 — PR title convention (CHECKED — v1 mandates a title shape; FIXED).** v1's `--title "Fix:
        <summary> (#<issue-number>)"` is not free prose — it is the literal `gh pr create --title` argument
        every fresh-PR open takes ([`SKILL.md:885`](../../../skills/github-issue-resolver/SKILL.md)); v2 had
        echoed the issue title verbatim instead. **Fixed:** `resolve-spine.md` now mandates the same
        `Fix: <summary> (#<issue-number>)` title shape on fresh-PR open (both the prose and the
        `create-pr --title` invocation), so the evaluator's squash-subject derivation (which reads a
        Conventional-Commits-prefixed title) stays fed consistently. Not left as a cosmetic divergence.

**Fix landed (D2 + D4).** `resolve-spine.md`'s fresh-mode PR staging now mandates the body's first line
be `Fixes #<issue-number>` (or `Closes #<issue-number>`) and the `--title "Fix: <summary>
(#<issue-number>)"` shape, per v1 SKILL.md:885/888; the `S6` phase-tick guard (never add `Closes #N` in
reaction to shipping a phase) is unchanged. `docs/specs/resolver.md`'s Artifacts-written table gained
the missing standard/story closing-keyword row (the S1 capture gap D2's root-cause analysis found).
Regression-guarded by `tests/test_resolver_routing.py::PrCreateContractTests` (spine-mandate greps +
an end-to-end `create-pr --dry-run` proof). **Verdict pending an operator re-run of this scenario** —
this record does not self-certify a live PASS; re-run twin-B against the fixed spine and confirm
`closingIssuesReferences: [<issue>]` populates before flipping the verdict below. **→ Re-run completed
2026-07-10 (see the SUPERSEDING record below); verdict flipped to PASS.**

**SUPERSEDING re-run (post-`db2ca73`) — VERDICT: PASS.** Fresh twins on
`danwashusen/gh-pipeline-sandbox` (the consumed #31/#32/PRs #33/#34 were **not** reused): two new
buggy `salute(name, title)` copies `src/salute_c.py` / `src/salute_d.py` seeded on `main@ccfb9fb`
(the `_c`/`_d` twin split — same recipe as the original `_a`/`_b`), each with an identical `bug`+`planned`
issue carrying a 2-bullet single-phase `## Definition of done` and a verified single-phase
`<!-- implementation-plan:v1 -->` plan (`## Coverage gap` = `(none)`, no-harness carve-out): **#39**
(twin-A → v1 `github-issue-resolver`) and **#40** (twin-B → v2 `resolver`). Same headless recipe
(fresh sandbox clone per leg, `claude -p "/github-pipeline:<skill> <issue>" --plugin-dir <this branch>
--model opus --permission-mode bypassPermissions --output-format stream-json --verbose`). Neither leg
merges, so `main` stayed `ccfb9fb` across both (confirmed post-run) and the twins never contended.

- **v1** #39 → **PR #41** (`Fix: salute() now includes the title honorific (#39)`, base `main`, head
  `issue-39-salute-title`), body first line **`Fixes #39`** → `closingIssuesReferences: [39]`; **0**
  operator gates; audit clean (0 blockers); forward `## Handoff` → `/github-pipeline:github-pr-evaluator
  #41` (PR line `review: not run · health: not run · merge: not run`). **v1 again skipped its own
  single-phase DoD projection** (issue #39's two bullets stayed `- [ ]` — D1, the same non-deterministic
  miss as the original run). 29 turns / $5.25 / ~13 min.
- **v2** #40 → **PR #42** — **startup = 1 `prep_resolver.py 40` call** (the sole state-assembly call ✓);
  judgment sub-agents = state-distiller + fitness-audit + test-selection + one review-loop `general-purpose`
  — none is state-assembly. PR opened via `gh_persist.py create-pr … --base main --head
  40-bug-salute-…` (single write path, explicit base/head). **0** `AskUserQuestion` operator gates.

**D2 — GONE (the fix's purpose, verified live).** PR #42's body **first line is `Fixes #40`** →
`closingIssuesReferences: [40]` (populated) — the issue↔PR auto-link + auto-close-on-merge that the
pre-fix run dropped now work, and the downstream evaluator's `closingIssuesReferences` gate would no
longer trip. **D4 — GONE.** PR #42's title is `Fix: salute() includes the title honorific (#40)`, the
mandated `Fix: <summary> (#<issue-number>)` shape (v1 SKILL.md:885), no longer the verbatim issue
title. **DoD projection — v2 faithful.** Issue #40's two bullets both `- [x] … (closed by commit
f96cc39)`, byte-matching the frozen S1 capture form; v1 skipped it again (D1), so a clean both-legs DoD
comparison is again moot (v2 is the faithful leg, as offline `ArtifactRenderingByteCompatTests` already
proves). **Forward handoff — schema-valid.** `/github-pipeline:evaluator #42`, `Issue:`+`PR:`+`Next:`+
load-bearing `Why:`, PR line `review: not run · health: not run · merge: not run` (the contract-conformant
pre-evaluator rendering — Scenario 2 D1 ruling); diverges from v1 only in the expected
`github-pr-evaluator` → `evaluator` next-command rename. **Gates: 0 = 0** `AskUserQuestion` on both legs.
42 turns / $5.30 / ~14 min.

- **D5 — v2 fitness audit raised a dim-6 BLOCKER, auto-overridden (EXPLAINED; fixture-induced, not a
  defect; NEW this re-run).** v2's audit flagged that issue #40's body names `salute(name, title)` but no
  target module, and **four** identical buggy copies now exist on `main` (`src/salute_{a,b,c,d}.py`) —
  a genuine implementation-readiness ambiguity. It **overrode with reason** (the verified plan names
  `src/salute_d.py`; dimension-7 confirmed that file still carries the exact buggy shape) and emitted a
  `## Audit override` PR-body section (a documented section that renders "when it fires"). **Root cause is
  the fixture, not v2:** the original run left the consumed `salute_a`/`salute_b` on `main`, so this
  re-run's tree carries four identical copies instead of the intended two, widening the ambiguity surface
  past the blocker threshold (the original run had only `_a`/`_b` and a clean audit). v1's audit didn't
  flag it (the audit is a judgment sub-agent, non-deterministic on the borderline). **Honesty caveat:** in
  *interactive* mode this §4.5 BLOCKER would surface as one operator gate (Revise / Override / Abort);
  headless `bypassPermissions` auto-recorded the override, so the literal `AskUserQuestion` count is
  `0 = 0` but v2 encountered a gate condition v1 did not — a fixture artifact, orthogonal to D2/D4, and
  the PR was opened correctly against the plan-named file regardless. A maximally-clean re-run would drop
  the stale `_a`/`_b` copies to isolate the audit path; it would not change the D2/D4 certification.

**Verdict: PASS (re-run, post-`db2ca73`).** The re-run's sole purpose — confirm the D2/D4 fix live — is
met unambiguously: v2's PR is `Fixes`-linked (`closingIssuesReferences: [40]`), correctly titled, projects
the single-phase DoD byte-faithfully, emits a schema-valid forward handoff, runs on **1** state-assembly
call, and fires **0** operator gates. Remaining divergences are all explained and none is a v2 defect: D1
(v1's own non-deterministic DoD-projection miss; v2 faithful), D3 (the known `create-pr` mechanism
cutover), and D5 (the fixture-induced audit override above).

**Prior verdict (pre-fix, superseded by the re-run above):** **FAIL — blocked on D2 (filed defect).**
The v2 leg reproduced v1 on every judgment/gate dimension (clean audit, plan consumed, one-line fix,
`/review` APPROVE with 0 items, **0 = 0** operator gates, ≤1 state-assembly call, schema-valid forward
handoff) **and was the more faithful leg on the DoD projection** (it applied `(closed by commit
61bd8e3)`; v1's run skipped it — D1). But v2's central output, the PR, was **not Closes-linked**
(`closingIssuesReferences: []`) because the v2 spine dropped the `Fixes/Closes #<issue>` keyword v1
mandates. D1 is an explained v1 non-determinism (v2 faithful); D3 is the known mechanism cutover; D4
is now fixed rather than left cosmetic (see above).

### Scenario 2 — Continue-mode re-entry

Target: an in-flight PR from a prior resolver run (`continue #<PR>` → `vector.mode: continue`,
`prior_pr` = your own open/draft PR, `workspace.reused`), multi-phase with the next phase unshipped.
Expected v2: the distiller runs, the S2 audit is **skipped** (continue mode), the existing PR's
`## Phase tracker` is the routing signal, the next phase ships + projects its `closes-dod`, the PR stays
draft (non-final phase) → re-route handoff `/github-pipeline:resolver #<N>` (or last-phase → flip ready +
forward to the evaluator).

**Fixture (twins on `danwashusen/gh-pipeline-sandbox`).** Scenario 1's twins are single-phase bug-fixes,
so this scenario seeds **fresh** twins in the in-flight multi-phase state a prior resolver run would leave
(the parity doc doesn't chain it off Scenario 1). A 3-phase (`format_currency` → `format_percent` →
`format_date`) planned `bug`+`planned` issue over `src/formatter_{a,b}.py` (the `_a`/`_b` twin split; buggy
stubs seeded on `main@d92dc12`), each with a 3-bullet `## Definition of done` and a verified 3-phase
`<!-- implementation-plan:v1 -->` plan (`## Phases`, one `closes-dod` bullet each; `## Coverage gap` =
`(none)` — the `src/` surface has no test harness, so the `compileall` fast-check is the mechanical gate).
**Phase 1 is pre-shipped** to simulate the prior run: per twin a branch carries the phase-1
`format_currency` fix, an **open draft PR** (base `main`, `Fixes #<issue>` first line, `## Phase tracker`
with Phase 1 `- [x] (commit <sha>)` / Phases 2–3 `- [ ]`, `## Plan` link, `## Doc grounding`) sits on it,
and the issue body's DoD bullet 1 is projected `(closed by phase 1, commit <sha>)`. **#35** (twin-A → v1
`github-issue-resolver`, branch `35-formatter-helpers-a`, draft **PR #37**, phase-1 seed `b03ee51`) and
**#36** (twin-B → v2 `resolver`, branch `36-formatter-helpers-b`, draft **PR #38**, phase-1 seed `55df1e6`).
Headless recipe per Scenario 1 (`claude -p "/github-pipeline:<skill> <issue>" --plugin-dir <this branch>
--model opus --permission-mode bypassPermissions`, fresh sandbox clone per run). The resolver never merges,
so `main` stays `d92dc12` and the two draft PRs sit on independent branches (no contention).

**Pre-flight (the continue-mode crux).** `prep_resolver.py 36` (one call) returned `status: ok`,
`vector.type: standard`, `vector.mode: **continue**`, `vector.prior_pr_row: **draft**`, `prior_pr` = **PR
#38** (draft, `author: danwashusen` = me, `headRefName: 36-formatter-helpers-b`), `suggested_playbook:
standard.md`, `phases` = 3, `audit_ref: main`, `open_questions_gate.blocked: false`, and the
`distiller_bundle` staged paths. Critically `workspace.branch: **36-formatter-helpers-b**` (the PR head
branch — **not** a fresh `<issue>-<slug>` name; the `branch` fresh-mode fact is `null` in continue mode)
at `workspace.sha: 55df1e6` (**the existing PR head, not `main`**) — proving the 7-row table drove
`continue` and that the existing branch is reused at the PR head, not recreated. `prior_pr_row` is `draft`
rather than `open-pr-yours` because a genuine in-flight multi-phase PR *is* a draft — both are the two
`_CONTINUE_ROWS` (`prep_resolver.py:225`) and both yield `mode: continue`, so the expected outcome holds
(see D-row on the row nuance).

- [ ] v1 run captured — #35 → **PR #37** (draft, base `main`, head `35-formatter-helpers-a`). Continue mode
      (in-flight PR; "plan already consumed and binding"); **audit skipped**. Read PR #37's `## Phase
      tracker`, shipped **Phase 2 — Fix `format_percent`** (`return "%d%%" % round(ratio * 100)`) as commit
      **`17e07eb`** onto the existing branch (no new branch, no PR create). §8 gate: `compileall` green,
      test-selection `(none)`. Ticked Phase 2 in PR #37's tracker; projected issue #35 DoD bullet 2 `(closed
      by phase 2, commit 17e07eb)`. `/review` **APPROVE, 0 addressable items** (iter 1). **0** operator
      gates. PR stayed **draft**. Re-route `## Handoff` → `/github-pipeline:github-issue-resolver #35`
      (`multi-phase: 2 of 3 phases shipped`; PR line `review: ✓ at 17e07eb · health: ✓ at 17e07eb · merge:
      not run`). 32 turns / $4.58 / ~9 min. Sub-agents: `github-ops` (`GATHER_ISSUE`) + test-selection
      `Explore` + review-loop `general-purpose` (state distilled **inline** in the main loop — no separate
      distiller sub-agent).
- [ ] v2 run captured (audit skipped on continue mode; phase-tracker read as the routing signal) —
      **startup = 1 successful `prep_resolver.py 36` call** (the sole state-assembly call ✓; a first
      wrong-path guess errored with no facts — D4). Router confirmed `suggested standard.md`, read the shared
      spine; **S2 audit skipped** (`"continue mode"` / `"Audit skipped"` logged, **no fitness-audit
      sub-agent dispatched**). Judgment sub-agents = **state-distiller** `Explore` (`Distill issue #36 state`,
      fed from the `distiller_bundle` staged paths) + test-selection `Explore` + review-loop
      `general-purpose` — none is state-assembly. Read PR #38's `## Phase tracker`, shipped **Phase 2 — Fix
      `format_percent`** (`return "%d%%" % round(ratio * 100)`) as commit **`909005d`** onto the existing
      branch via `git push` (no `create-pr`, no `gh pr create`, no `gh pr ready`). §8 gate: `compileall`
      green, test-selection `(none)`. Writes = `gh_persist.py edit-body` ×2 (issue #36 DoD + PR #38 tracker,
      each self-confirmed with `body_sha256`). `/review` **APPROVE, 0 addressable items**. **0** operator
      gates. PR stayed **draft**. Re-route `## Handoff` → `/github-pipeline:resolver #36`. 52 turns / $4.50 /
      ~12 min.
- [ ] Artifacts schema-identical (per-phase DoD projection `(closed by phase <N>, commit <short-sha>)`,
      `## Phase tracker` tick, PR stays draft on a non-final phase) — **YES.** *DoD projection:* both ticked
      **only** bullet 2 as `- [x] … (closed by phase 2, commit <sha>)` (v1 `17e07eb`, v2 `909005d`),
      byte-matching the frozen S1 capture form; bullet 1 (phase 1) unchanged, bullet 3 left `- [ ]`
      (exact-coverage — no over-tick, no sticky-veto re-tick). *Phase tracker:* both are `- [x] Phase 1 …
      (commit <sha>)` / `- [x] Phase 2 … (commit <sha>)` / `- [ ] Phase 3 …` on the PR body. *Draft state:*
      both PRs `isDraft: true`, `OPEN`, same head branch, exactly **2 commits** (phase-1 seed + phase-2), and
      **no duplicate PR** (a `<issue> in:body` search returns only the one PR per twin). Divergence is on the
      *handoff PR-line markers* only (D1).
- [ ] Continue-mode is parameterization, not a fifth flow (same playbook, `vector.mode` drives it) — **YES.**
      v2 routed to `standard.md` → the shared `resolve-spine.md` (the same playbook a fresh standard issue
      loads); `vector.mode: continue` + `prior_pr` + the reused branch drove the continue behavior (audit
      skip, phase-tracker routing, push-onto-existing-branch) **inside** that playbook — no fifth flow, no
      `continue`-specific playbook read.
- [ ] Gates match; handoff schema-valid; ≤1 state-assembly call — **0 = 0** operator gates on both legs;
      both handoffs are valid **Re-route — multi-phase, non-final** `## Handoff` blocks (`Issue:` + `PR:` +
      `Next:` + `Why:`, `Next:` = `/github-pipeline:{github-issue-resolver|resolver} #<issue>`); v2 startup =
      **1** successful `prep_resolver.py` state-assembly call, 0 sub-agents for state assembly.
- [ ] Divergences (each traced to a PRD § / cutover, or filed as a defect):
      - **D1 — re-route handoff PR-line `review`/`health` markers diverge (FILED DEFECT, low severity).**
        v1 rendered `review: ✓ at 17e07eb · health: ✓ at 17e07eb`; v2 rendered `review: not run · health: not
        run`. The shared closed set ([`../../../skills/_shared/handoff-format.md:52-53`](../../../skills/_shared/handoff-format.md))
        is `review ∈ {APPROVE, COMMENT (soft-reject), …, not run}` and `health ∈ {✅ at <sha>, ❌ at <sha>,
        not run}` — **`✓` is off-vocabulary for both** (v1's glyph), so v1's markers are non-conformant, while
        v2's `not run` tokens are schema-valid but *under-report* (the resolver's `/review` loop **did**
        approve and the §8 health gate **did** pass at the phase-2 commit). **Root cause:** an ambiguity in
        v2's [`references/handoff-renderings.md`](../../../skills/resolver/references/handoff-renderings.md) —
        its intro (lines 10-12) says the `review`/`health`/`merge` markers are all `not run` "on a resolver
        **forward** exit" (forward-scoped), but the **Re-route — multi-phase, non-final** worked example
        (line 41) shows `review: ✓ at 40f1d36 · health: ✓ at 40f1d36`, using the off-closed-set `✓` glyph and
        contradicting the intro; the model followed the intro's rule and emitted `not run`. Neither leg
        rendered the intended `review: APPROVE at <sha> · health: ✅ at <sha>` (v1 SKILL.md:1011 prescribes
        `review: APPROVE at <sha>` from the refreshed `pr-state.json`). Cosmetic marker-level only — both
        re-route to the resolver, PR stays draft, Phase 2 projected — but it is a real, filed underspecification.
        *Fix:* scope the intro's "all `not run`" to the forward-to-evaluator exits, and correct the
        multi-phase-re-route example's PR line to the shared closed-set values `review: APPROVE at <sha> ·
        health: ✅ at <sha> · merge: not run` (populated because the review loop + §8 gate ran at that
        commit, per v1 SKILL.md:1011). **Verdict not self-certified as fixed** — record the divergence;
        re-run confirms the rendering after the doc fix.

        **RULING (post-observation, evaluated against the contract — original observation above left
        intact, not rewritten):** the sketch above ("populate `review: APPROVE at <sha> · health: ✅ at
        <sha>`") is **not** what the contract supports and was **not** implemented. Read
        `handoff-format.md`'s actual field definitions: `review:` is defined project-wide as the
        **evaluator's** posted GitHub review verdict (`APPROVE` / `COMMENT (soft-reject)` / …), and
        `health:` is the **evaluator's** branch-health gate result — not "did the resolver's own
        `/review` loop or §8 gate run." The resolver's own S1 capture makes this explicit and is frozen
        prior truth, not something authored for this fix:
        [`docs/specs/examples/handoff-resolver.md`](../examples/handoff-resolver.md) states "the
        `review:`/`health:`/`merge:` markers on the `PR:` line are all `not run` here because the
        resolver never runs the evaluator's checks itself — those fields populate only once the
        evaluator has acted" — and that rule is not forward-exit-scoped in the capture's own prose,
        only in v2's (buggy) intro paraphrase of it. A mid-phases re-route hasn't reached the evaluator
        either, so the identical rule applies: **v2's `review: not run · health: not run` was the
        conformant rendering all along; v1's `✓` is the true off-contract value**, not an "also valid,
        just glyph-wrong" stand-in for a real APPROVE/health-check value — v1 never ran the evaluator on
        that PR, so no evaluator verdict or health-cache SHA existed to legitimately populate those
        fields with. **Fix applied:** `handoff-renderings.md`'s intro is rewritten to state the `not
        run` rule unconditionally (forward exits *and* every re-route, explicitly including the
        mid-phases continue-mode case), and the off-closed-set `✓` glyph is removed from all three
        worked examples that carried it (the multi-phase non-final re-route, the terminal-with-action
        operator-phase shape, and — found by the same audit — the last-planned-phase-shipped *forward*
        shape, which had the identical bug independent of forward/re-route framing). `standard.md`'s
        Handoff section now states the same rule inline for its multi-phase bullet, closing the gap
        where a routed playbook depended entirely on the reference getting it right. **No closed-set
        value was added** — the fix is internal consistency (worked examples ↔ intro ↔ contract), not a
        contract change. **Scenario-4 guidance:** the operator's scenario-4 run (which emits the same
        re-route shape) should expect and confirm `review: not run · health: not run` on every
        resolver-authored `PR:` line pre-evaluator; that is the ruled-conformant rendering, not a
        regression to fix further. Regression-guarded by
        `tests/test_resolver_routing.py::ReRouteHandoffMarkerTests`.
      - **D2 — `prior_pr_row: draft` vs the scenario's `open-pr-yours` wording (EXPLAINED; not a defect).**
        The scenario target says `prior_pr = your own open/draft PR`; a genuine in-flight *multi-phase* PR is
        a **draft** (the resolver flips it ready only at the last phase), so prep classifies the row as
        `draft`, not `open-pr-yours`. Both are the two `_CONTINUE_ROWS` (`prep_resolver.py:225`) → both yield
        `mode: continue`; the row name only selects which (if any) gate card would show, and neither continue
        row gates. The expected outcome (continue mode, branch reused at PR head) holds exactly.
      - **D3 — state-assembly + write mechanism (EXPLAINED; known v1→v2 cutover).** v1 gathers via the
        `github-ops` `GATHER_ISSUE` sub-agent and writes via raw `gh issue edit` / `gh pr edit` / `git push`
        in its main loop; v2 assembles via the deterministic `prep_resolver.py` (one facts block) and writes
        via `gh_persist.py edit-body` staged-body writes (+ `git push`). Same artifacts (identical DoD tick,
        phase-tracker tick, phase-2 commit); the mechanism change is the documented cutover. Not a defect.
      - **D4 — distiller seam (EXPLAINED; known v1→v2 architecture).** v1 distills current state **inline** in
        the main loop (no separate sub-agent); v2 dispatches a dedicated **state-distiller** `Explore` fed
        from prep's `distiller_bundle` staged paths (`resolve-spine.md` S1). Both then classify and read the
        PR `## Phase tracker` as the routing signal. Architecture, not a defect.
      - **D5 — v2's first `prep_resolver.py` call used a wrong path (EXPLAINED; benign headless artifact).**
        v2's initial invocation was `…/skills/resolver/scripts/prep_resolver.py 36` (a `${CLAUDE_PLUGIN_ROOT}`
        path-construction fumble) → exit 1, **no facts assembled**; the model `find`-corrected and the second
        call to the real `…/scripts/prep_resolver.py 36` returned the `status: ok` facts block. Exactly **one
        successful state-assembly call** drove routing, so the ≤1-state-assembly criterion holds; the failed
        guess produced no state. A headless path-resolution artifact, not a skill-contract divergence.

**Verdict:** **PASS (both legs) — one filed low-severity defect (D1, handoff PR-line marker rendering).**
Both re-enter the in-flight multi-phase PR in `continue` mode, **skip the S2 audit**, read the existing PR's
`## Phase tracker` as the routing signal, ship the next planned phase (Phase 2 — `format_percent`) onto the
**existing branch at the PR head** (no new branch, no `create-pr`, no duplicate PR), project **only** that
phase's `closes-dod` bullet onto the issue body (`(closed by phase 2, commit <sha>)`; exact-coverage, bullet
3 untouched), tick it on the PR tracker, leave the PR **draft**, run **0 operator gates**, and emit a valid
**Re-route — multi-phase, non-final** `## Handoff` back to the resolver. v2 confirmed the crux offline (`prep`
returned `mode: continue` from the `draft` continue row, `workspace.branch` = the PR head branch at the PR
head SHA) and startup = **1** successful state-assembly call. The sole persisted-handoff divergence (D1) is a
filed, low-severity marker-rendering underspecification — **ruled, and fixed, in D1's own annotation above:
v2's `not run` was the contract-conformant rendering; the underlying self-consistency bug in
`handoff-renderings.md` (not v2's behavior) is what needed fixing, and is fixed**. D2–D5 are
wording/cutover/architecture/environment, each explained. No unexplained divergence.

### Scenario 3 — Comment-only

Target: a `question`-shaped issue (or an issue the thread resolves with an answer, no code warranted).
Expected v2: prep sets `comment_only`, the router routes to `comment-only.md`, the distiller grounds the
answer, one comment staged + posted via `gh_persist.py comment`, terminal handoff (no PR line).

**Fixture (twins on `danwashusen/gh-pipeline-sandbox`).** Two identical `question` + `audience:architect`
issues carrying the question-issue schema (`## Question`/`## Audience`/`## Constraints`/`## Context`/
`## References`/`## Why this matters`/`## Tracked in`) and **no** `## Definition of done` — so the
correct outcome is a posted answer, not code: **#29** (twin-A → v1 `github-issue-resolver`) and **#30**
(twin-B → v2 `resolver`). Headless recipe per the [handback](../../run-journal.md) (`claude -p
"/github-pipeline:<skill> <n>" --plugin-dir <this branch> --model opus --permission-mode
bypassPermissions`, fresh sandbox clone per run). The refusal mutates only by posting one comment (no
branch/PR/shared-parent), so independent twins keep each run's thread clean for the distiller.

**Pre-flight (the crux this scenario tests).** `prep_resolver.py 30` returns `status: ok`,
`vector.type: standard`, `vector.mode: fresh`, `comment_only: **false**`, `suggested_playbook:
**standard.md**`, `dod: []`, `open_questions_gate.blocked: false` — and eagerly ensures a **work
worktree**. Prep sets `comment_only` **only** on the OQ hard gate / native `blocked_by`
(`prep_resolver.py:1005`; that path is Scenario 5), never on an answer-only classification — the spec
assigns response-type classification (`bug/feature/question/…`) to the **main loop consuming the
distiller's `## Classification`** ([resolver.md](../resolver.md) §4, "Judgment steps" table), not to
prep. So v2's comment-only routing must come from the **router's §77 override on the `question`
label**, not from a prep fact. This is where the scenario's expected text ("prep sets `comment_only`")
is loose for the *answer-only* case — see Divergences.

- [x] v1 run captured — #29 classified **Question** → posted one free-prose recommendation comment
      ([#29 comment](https://github.com/danwashusen/gh-pipeline-sandbox/issues/29#issuecomment-4930081450),
      `## Recommendation …` + `### Why …`/`### When inlining …`/`### Concrete shape`/`### One honesty note`),
      **no worktree, no PR**; terminal `## Handoff` (`Issue:` line + a `**Audience:** audience:architect`
      line, `plan:` marker **omitted**, no `PR:` line, `Next: (terminal — no follow-up skill)`).
- [x] v2 run captured (comment-only route; no PR opened; no spine read) — prep = **one**
      `prep_resolver.py` call (`suggested standard.md`); the router **overrode to `comment-only.md`**,
      logging verbatim *"Prep suggested `standard.md`, but the state-distiller classified this `type:
      question` / `plan: absent` … an answer-only classification the prep script couldn't make — so I
      overrode the route"* (SKILL.md §77). The **spine was not read**. Distiller ran (a *judgment*
      sub-agent grounding the answer, not state-assembly). Posted one comment
      ([#30 comment](https://github.com/danwashusen/gh-pipeline-sandbox/issues/30#issuecomment-4930115450))
      via `gh_persist.py comment`; **no PR, no origin branch** (prep's local `.worktrees/30-…` was created
      but never used and discarded with the clone — see D2).
- [x] Artifact schema-identical (staged-body comment; terminal handoff with the `Issue:` line + no PR
      line + `(terminal — no follow-up skill)`) — **comment:** both are a single free-prose answer posted
      via the staged-body write path (no frozen marker/section schema for a comment-only answer per the
      Renderings table; prose differs, as the protocol allows). **Handoff:** both are terminal `## Handoff`
      blocks with `## Handoff` + `Issue:` (`#N — <title> · <state> · question`) + **no** `PR:` line +
      `Next: (terminal — no follow-up skill)` + load-bearing `Why:`. One structured-field divergence on the
      `Issue:` line — see D1.
- [x] Gates match (0 code-work gates); handoff schema-valid; ≤1 state-assembly call — **0** operator
      gates fired on either leg (comment-only = no audit/plan/PR gates); both handoffs are valid terminal
      `## Handoff` blocks; **v2 startup = 1 `prep_resolver.py` call, 0 sub-agents for state assembly**
      (the distiller is judgment, not assembly).
- [x] Divergences (each traced to a PRD § or filed as a defect):
      - **D1 — terminal `Issue:`-line rendering on a `question` (FILED DEFECT, low severity; FIXED).** v1
        rendered the question-type Issue line per [`../../../skills/_shared/handoff-format.md`](../../../skills/_shared/handoff-format.md)
        line 33 — `research:`/`plan:` markers **omitted** + a `**Audience:** audience:architect` line; v2
        rendered `· plan: ✗` and **omitted** the `Audience:` line, following its generic
        [`references/handoff-renderings.md`](../../../skills/resolver/references/handoff-renderings.md)
        "Terminal — non-PR resolution" shape (whose worked example is a *feature*-typed issue). **Fixed**
        by adding a dedicated question-type variant — a new "## Terminal — question-type issue" shape in
        `handoff-renderings.md` (no `plan:`/`research:` marker, `**Audience:**` line, per the existing
        `_shared` contract — `_shared` itself is untouched) — and by making `comment-only.md`'s Handoff
        section dispatch on the issue's own type (`question` → the new shape; any other type → the
        pre-existing "Terminal — non-PR resolution" shape, corrected to a non-question worked example so
        the two shapes are no longer conflated). Regression-guarded by
        `tests/test_resolver_routing.py::QuestionTypeHandoffVariantTests` (asserts the rendered example
        omits `plan:` and carries `Audience:`, and that the playbook dispatches by type). Cosmetic
        marker-level only — did not change the outcome (comment-only, no PR, terminal) — but no longer
        left open; **verdict pending an operator re-run to confirm the live rendering.**
      - **D2 — prep eagerly builds an unused work worktree (EXPLAINED; benign; architecture, not defect).**
        Because prep is judgment-free deterministic state-assembly ([prd.md §9.2](../../prd.md)), it
        cannot make the answer-only call and so ensures a work worktree for the `standard`/`fresh` vector;
        the router then overrides to comment-only and never uses it. v1 (which classifies before touching a
        worktree — v1 SKILL.md:79) creates none. In this run the worktree was local-only, unpushed, and
        discarded with the throwaway clone. Candidate low-severity cleanliness improvement (a real,
        non-clone run would leave one stray unused worktree), **not** run-failing.
      - **D3 — comment write mechanism (EXPLAINED; expected v1→v2 cutover).** v1 posts via the
        `github-ops` sub-agent → `gh-persist.sh comment`; v2 posts directly via `gh_persist.py comment`
        (the `github-ops` indirection is removed in v2). Same staged-body write path, same artifact. Not a
        defect.

**Verdict:** **PASS (both legs) — one filed defect (D1, low severity).** Both classify the `question`
issue as answer-only, post exactly one free-prose comment via the staged-body write path, open **no
PR/branch**, run **0 code-work gates**, and emit a schema-valid terminal `## Handoff` (`Issue:` line, no
`PR:` line, `(terminal — no follow-up skill)`). v2 confirmed the crux: routing to comment-only is the
**router's §77 override on the `question` label**, not a prep fact — so the scenario's "prep sets
`comment_only`" expectation holds only for the OQ-gate case (Scenario 5); for the answer-only case it is
the router's judgment. The sole divergence in the persisted handoff (D1) is a filed, low-severity
contract-underspecification of the question-type terminal `Issue:` line; D2/D3 are architecture-traced.
No unexplained divergence.

### Scenario 4 — Multi-phase tick projection

Target: a multi-phase planned issue, fresh start. Expected v2: the fresh PR opens as **draft** carrying a
`## Phase tracker` mirroring the plan's `## Phases`; the first phase ships; only that phase's `closes-dod`
bullets flip on the issue body (`(closed by phase <N>, commit <short-sha>)`) — never a bullet the phase
doesn't claim, never a sticky-vetoed bullet; the PR stays draft; re-route handoff to the resolver for the
next phase.

- [ ] v1 run captured.
- [ ] v2 run captured (draft PR + `## Phase tracker`; exact-coverage projection).
- [ ] Artifacts schema-identical (`## Phase tracker` shape, per-phase DoD annotation, draft PR state).
- [ ] Projection is exact-coverage (`expected_set − (ticked ∪ rejected)`); no over-tick, no
      sticky-veto re-tick.
- [ ] Gates match; handoff schema-valid; ≤1 state-assembly call.
- [ ] Divergences.

**Verdict:** _TODO — operator-gated._

### Scenario 5 (box 3) — Seeded in-scope-blocked issue is refused with the gate (live)

Target: a build issue hard-gated by an unresolved `in-scope (blocked)` open question. Expected v2: prep's
`open_questions_gate.blocked` is true → the router refuses code work, routes to `comment-only.md`, and
posts the gate answer naming the blocking `question` tracker `#N`; **no PR, no code, no DoD tick**;
terminal handoff whose `Why:` names the blocking question.

**Seeding recipe** (per [`../../../skills/_shared/open-question-links.md`](../../../skills/_shared/open-question-links.md)):

1. File a `question`-type issue on the sandbox (label `question` + an `audience:*` label), leave it
   **open** — this is the tracker the gate cites. Call its number `#Q`.
2. File a `bug`/`feature` build issue whose body carries an `## Open questions` section:
   ```
   ## Open questions
   <!-- open-question-links:v1 -->
   - OQ: `OQ-1` (docs/prd.md §X) — gates: <one line of the in-scope work this OQ blocks>
     — disposition: in-scope (blocked)
     — question: #Q — audience: audience:product
   ```
3. Set the build issue's **native `blocked by` dependency** to `#Q` (`gh_persist.py link
   <owner/repo> <build-issue> --add-blocked-by <Q>`, or the Development panel if native deps are
   unavailable — then the prose `Related to #Q` fallback carries it). Confirm `blocked_by` shows `#Q`
   open on the build issue.
4. Give the build issue a normal `## Definition of done` so the refusal is visibly *not* a
   nothing-to-do case — the point is that buildable-looking scope is held.

Run **v1** `github-issue-resolver <build-issue>` and **v2** `resolver <build-issue>` on twins of this
fixture (the refusal mutates nothing, so two independent build issues sharing one open `#Q`, or a twinned
`#Q`, both work). Compare the refusal comment + terminal handoff.

- [x] Fixture seeded — open `#Q` = **#27** (`question` + `audience:architect`); build issue **#28** carries
      the `<!-- open-question-links:v1 -->` `in-scope (blocked)` entry (`OQ-1` → question `#27`) + native
      `blocked_by #27` (confirmed via `gh_gather.py`: `deps_available: true`, `blocked_by[0]` = #27 `OPEN`).
- [ ] v1 refusal captured — **not run this session.** Box 3 ("refused with the gate (live)") gates on the
      **v2** live refusal only; the full v1↔v2 schema-identical comparison is not a box-3 requirement.
- [x] v2 refusal captured — pre-flight `prep_resolver.py` from the run clone returned
      `open_questions_gate.blocked: true`, `suggested_playbook: comment-only.md`, `vector.comment_only: true`
      (blocking cites `#27` `OPEN`, `native_blocked: true`, `resolved: false`); the headless
      `resolver 28` run posted a comment-only refusal
      ([#28 comment](https://github.com/danwashusen/gh-pipeline-sandbox/issues/28#issuecomment-4929973301))
      naming `OQ-1` + tracker `#27`, opened **no PR**, created **no branch/worktree**, ticked **no** DoD
      bullet, and emitted a terminal `## Handoff` whose `Why:` names `#27`/`OQ-1` and omits the `PR:` line.
- [x] Issue left open + untouched — #28 still `OPEN`, all three `## Definition of done` bullets `- [ ]`,
      `blocked_by #27` intact; the run's clone stayed on `main` @ `a07eb90` with no worktree and a clean
      working tree. (Schema-identical-to-v1 not asserted — the v1 leg was not run this session.)
- [x] Divergences — none (v2 leg). No PRD-traced divergence, no defect filed.

**Verdict:** **PASS (v2 live refusal)** — S10 DoD box 3 closed. The seeded in-scope-blocked issue **#28** was
refused with the OQ hard gate: comment-only path, refusal comment naming blocking `#27`, no worktree, no PR,
no DoD tick, schema-valid terminal handoff. The v1 leg was not run this session — box 3 gates only the v2
live refusal; the full v1↔v2 schema-identical comparison is not a box-3 requirement.

## Go/no-go (S-step input)

- [ ] All four parity scenarios + the box-3 live refusal pass with **zero unexplained divergences**.
- [ ] Result summary (accepted / blocking finding + remediation step): _TODO._ **No outstanding
      prerequisite** — the PR-create write path (`gh_persist.py create-pr`) landed within S10, so all
      four scenarios plus the box-3 refusal are runnable once a live sandbox session is available.
