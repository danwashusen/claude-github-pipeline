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
| `skills/resolver/playbooks/resolve-spine.md` (the shared spine — largest) | 177 |
| `skills/resolver/playbooks/epic.md` | 114 |
| `skills/resolver/playbooks/comment-only.md` | 48 |
| `skills/resolver/playbooks/story.md` | 33 |
| `skills/resolver/playbooks/standard.md` | 28 |
| **router + largest playbook (the loaded set)** | **305** |

**305 ≤ 584** ✅. Router **128 ≤ 150** ✅ (architecture.md §9 size bar). References are read on-demand
and are not part of the loaded-prompt metric; recorded for completeness: `common-pitfalls.md` 240,
`review-loop-sub-agent.md` 221 (carried from v1), `epic-flow.md` 220, `handoff-renderings.md` 195,
`test-selection-sub-agent.md` 178 (carried), `issue-audit-prompt.md` 177 (carried),
`retry-ladder.md` 181, `state-distiller-prompt.md` 106 (carried), `dod-projection-rule.md` 104,
`follow-up-tracking.md` 92, `epic-baseline.md` 45.

A standard/story session loads router (128) + `resolve-spine.md` (177) + one thin routed playbook
(28–33) = **≤ 338**; the DoD's metric is *router + largest playbook* = 305 (the +7/+4 vs. the initial
draft is the concrete `create-pr` invocation the write-path prose now names — see "PR-create write
path" below). An epic session loads router + `epic.md` (114) = 242; a comment-only session router +
`comment-only.md` (48) = 176. Each document fits one default `Read`.

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

- [ ] v1 run captured (writes / gates / handoff / turns).
- [ ] v2 run captured (prep facts / sub-agent dispatches / writes / handoff / one state-assembly call).
- [ ] Artifacts schema-identical (PR body sections, single-phase DoD projection `(closed by commit
      <short-sha>)`, forward handoff).
- [ ] Cross-consumption confirmed (the evaluator reads the v2 PR + projected DoD; a v1-projected DoD is
      read by the v2 evaluator).
- [ ] Gates match; handoff schema-valid; ≤1 state-assembly call.
- [ ] Divergences (each traced to a PRD § or filed as a defect).

**Verdict:** _TODO — operator-gated._

### Scenario 2 — Continue-mode re-entry

Target: an in-flight PR from a prior resolver run (`continue #<PR>` → `vector.mode: continue`,
`prior_pr` = your own open/draft PR, `workspace.reused`), multi-phase with the next phase unshipped.
Expected v2: the distiller runs, the S2 audit is **skipped** (continue mode), the existing PR's
`## Phase tracker` is the routing signal, the next phase ships + projects its `closes-dod`, the PR stays
draft (non-final phase) → re-route handoff `/github-pipeline:resolver #<N>` (or last-phase → flip ready +
forward to the evaluator).

- [ ] v1 run captured.
- [ ] v2 run captured (audit skipped on continue mode; phase-tracker read as the routing signal).
- [ ] Artifacts schema-identical (per-phase DoD projection `(closed by phase <N>, commit <short-sha>)`,
      `## Phase tracker` tick, PR stays draft on a non-final phase).
- [ ] Continue-mode is parameterization, not a fifth flow (same playbook, `vector.mode` drives it).
- [ ] Gates match; handoff schema-valid; ≤1 state-assembly call.
- [ ] Divergences.

**Verdict:** _TODO — operator-gated._

### Scenario 3 — Comment-only

Target: a `question`-shaped issue (or an issue the thread resolves with an answer, no code warranted).
Expected v2: prep sets `comment_only`, the router routes to `comment-only.md`, the distiller grounds the
answer, one comment staged + posted via `gh_persist.py comment`, terminal handoff (no PR line).

- [ ] v1 run captured.
- [ ] v2 run captured (comment-only route; no PR opened; no spine read).
- [ ] Artifact schema-identical (staged-body comment; terminal handoff with the `Issue:` line + no PR
      line + `(terminal — no follow-up skill)`).
- [ ] Gates match (0 code-work gates); handoff schema-valid; ≤1 state-assembly call.
- [ ] Divergences.

**Verdict:** _TODO — operator-gated._

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

- [ ] Fixture seeded (open `#Q`; build issue with `<!-- open-question-links:v1 -->` `in-scope (blocked)`
      entry + native `blocked_by #Q`).
- [ ] v1 refusal captured (comment naming `#Q`; no PR; no DoD tick; terminal handoff).
- [ ] v2 refusal captured (`prep_resolver` `open_questions_gate.blocked: true`; router → `comment-only.md`;
      comment naming `#Q`; no PR; no DoD tick; terminal handoff whose `Why:` names `#Q`).
- [ ] Refusal comments schema-identical; both leave the issue open and un-touched (no branch, no PR, no
      DoD projection).
- [ ] Divergences (each traced to a PRD § or filed as a defect).

**Verdict:** _TODO — operator-gated (S10 DoD box 3)._

## Go/no-go (S-step input)

- [ ] All four parity scenarios + the box-3 live refusal pass with **zero unexplained divergences**.
- [ ] Result summary (accepted / blocking finding + remediation step): _TODO._ **No outstanding
      prerequisite** — the PR-create write path (`gh_persist.py create-pr`) landed within S10, so all
      four scenarios plus the box-3 refusal are runnable once a live sandbox session is available.
