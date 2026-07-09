# Resolve spine — shared across the standard and story routes

The code-shipping flow both `standard.md` and `story.md` run: distill state → audit → plan-gate →
doc grounding → code in the workspace → review loop → per-phase push + DoD projection → hand back to
the routed playbook for its handoff. Type differences here are **facts** (`audit_ref`, the work
workspace's `base_ref`, the handoff shape), never branches — the routed playbook (`standard.md` /
`story.md`) reads this spine first, then emits its own handoff shape.

All facts named below come from the prep facts block (SKILL.md §1). All GitHub writes go through
`${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py` with a staged body path (SKILL.md §3). The run scratch
dir is `facts.scratch`. Your workspace is `facts.workspace.path`.

## S1 — Distill the current state (thread + plan)

Dispatch the **state-distiller** `Explore` sub-agent per
[`../references/state-distiller-prompt.md`](../references/state-distiller-prompt.md), substituting the
`distiller_bundle` staged paths (`issue_body_path`, `thread_path`, `plan_marker_path`), `facts.target`
labels, and `facts.audit_ref` as the informational integration-target name. It reads only the issue's
own text (never code), and returns `## Current state` + `## Effective plan` + `## Classification`, or a
typed exception (`THREAD_SUPERSEDED_PLAN` / `PHASES_MALFORMED` / `AMBIGUOUS`). Print the distilled
state. Act on an exception per SKILL.md §1's decision-card rule: `THREAD_SUPERSEDED_PLAN` → re-route to
the planner (the thread moved past a locked decision); `AMBIGUOUS` → read the raw thread yourself and
proceed; `PHASES_MALFORMED` → re-route to the planner. Lift the distiller's `## Doc grounding` citations
verbatim — that is your S3 grounding, so the main loop never re-reads project docs.

**Continue mode** (`vector.mode == continue`, `prior_pr` present, `workspace.reused`): you are
resuming an in-flight PR. The distiller still runs (the thread may have moved), but the PR's own
`## Phase tracker` — re-read from the existing PR body — is the authoritative record of which phases
shipped; reconcile the issue-body DoD ticks against it per S6 before shipping the next phase. Skip the
S2 audit on continue mode (the audit is a fresh-implementation-start gate, not a per-push gate).

## S2 — Fitness-to-implement audit (fresh start only)

Skip this section entirely in `continue` mode. On a fresh implementation start, dispatch the **fitness
audit** `Explore` sub-agent per [`../references/issue-audit-prompt.md`](../references/issue-audit-prompt.md).
It reads code and docs from the **read workspace** (`facts.read_workspaces.audit.path`, a detached
checkout at the audit ref — never a raw ref, never the root cwd) and the issue/siblings/plan it
self-fetches; it returns `## Audit summary` + `## Findings` (each BLOCKER/SUGGESTION/NIT with
evidence). Which dimensions run: 1–4 + 6 always; 5 (cross-issue contract drift) for a story under an
open epic or an epic-as-target; 7 (plan-vs-code currency) only when a plan exists. Print the summary.

On **any BLOCKER**, gate (`header: "Audit"`): **Revise via drafter** (default — re-route to
`/github-pipeline:drafter revise #<N>`, quoting the finding's evidence in the `Why:`) / **Override with
reason** (record `Audit override: <reason>` for the PR body's `## Audit override` section and continue)
/ **Abort** (stop the run). SUGGESTIONs/NITs are surfaced, never gating. A skip-by-override records
"Audit skipped by user override" for the same section.

## S3 — Plan gate + doc grounding

**Plan gate.** `facts.plan.present` says whether a `<!-- implementation-plan:v1 -->` plan exists.
- Plan present → consume it: implement its **locked decisions** (`## Architecture decisions`,
  `## Changes`, `## Data model / schema impact`, `## Test plan`), do not re-derive the approach. If the
  fitness audit's dimension 7 flagged plan-vs-code drift, or the distiller raised
  `THREAD_SUPERSEDED_PLAN`, re-route to the planner in revise mode rather than patching around
  staleness. A `## Plan` link (`Implements the plan on #<N>: <plan-comment-url>`) goes in the PR body.
- No plan on a **non-trivial** issue → stop and ask (freeform): run
  `/github-pipeline:planner #<N>`, or reply `proceed without a plan`. On the override, record
  `Plan override: <reason>` for the PR body's `## Plan override` section. Trivial fixes are exempt.

**Doc grounding.** Use the distiller's lifted `## Doc grounding` citations (plan-present path). With no
plan, ground the implementation yourself against the docs in the **read workspace** — `docs/prd.md`,
`docs/architecture.md`, `docs/constitution.md`, `CLAUDE.md` read-if-present, bounded to the implicated
slices — and stage a `## Doc grounding` section for the PR body. On a **clear** doc conflict the body
can't be reconciled against, gate (`header: "Doc conflict"`): **Update the doc** / **Reshape issue**
(re-route to the drafter) / **Override with reason**.

## S4 — Detect phases

Use `facts.phases` (prep parsed the plan's `## Phases`). Single-phase (empty or one entry with no
`closes-dod`) → one push closes the DoD via the single-phase fallback. Multi-phase → the PR opens as a
**draft** carrying a `## Phase tracker`, one phase ships per session, and the PR flips to ready only on
the last-planned-phase-shipped handoff. On continue mode, the current phase is the first unticked entry
in the existing PR's `## Phase tracker` whose `depends-on` is satisfied. An operator/decision-only
phase (`kind: operator | decision-only`) ships no commits — surface it via the operator-phase handoff
rather than running it.

## S5 — Do the work + the review loop

Read [`../references/common-pitfalls.md`](../references/common-pitfalls.md) before any code or
review work (anti-patterns extracted so they don't consume the load budget). Implement the current
phase's `ships` in the workspace, iterating at unit-test granularity locally.

**§8 pre-push verification gate** (mandatory before the **first** push of the run — the only test
invocation before the PR exists; `review` runs no tests). Run static checks (`facts.config.static_checks`,
in order, first-failure short-circuit), then dispatch the **test-selection** `Explore` sub-agent per
[`../references/test-selection-sub-agent.md`](../references/test-selection-sub-agent.md) (inputs:
`facts.workspace.path`, `facts.audit_ref` as the integration target, `facts.config.test_target_raw`);
print its `RATIONALE:` verbatim, then run its `COMMAND:` in the workspace (skip on `(none)`). **If the
command begins with `xcodebuild`** (or a wrapper that runs it), delegate to the
`apple-platform-build-tools:builder` sub-agent, bounded to "run this exact command in this exact cwd,
report pass/fail + first error; do NOT edit source, re-run with modified flags, or investigate." The
gate is capped at 3 runs with a forced research breakpoint per
[`../references/retry-ladder.md`](../references/retry-ladder.md); on escalation, ask (`header: "Tests
red"`): **Push with reds** (`## Known failures` in the PR body) / **Defer the tests** (file follow-ups,
skip) / **Restructure** (re-route to the planner). Never run the **full** canonical suite at this gate
— targeted selection is the whole cost model (the full suite runs only in the epic baseline flow, in
CI, and in the evaluator).

**Open or continue the PR + push the phase.** Fresh-mode first push: stage the body to
`<facts.scratch>/pr.md` — carrying `## Doc grounding` + the `## Plan` link + `## Audit
override`/`## Plan override` when they fired + a `## Phase tracker` for multi-phase + a
`## Predecessor` when the branch is a `-vN` (predecessor PR detected) — and open the PR through the
single write path:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py create-pr <owner/repo> "<facts.scratch>/pr.md" \
  --title "<title>" --base "<facts.workspace.base_ref>" --head "<facts.branch.name>" \
  [--draft]   # only for a multi-phase issue (S4); omit for single-phase
```

`--base`/`--head` are always explicit facts from the workspace (never inferred from cwd). Continue-mode:
push onto the existing branch (no PR create). Then run the **review loop** (S5.1).

### S5.1 — Review loop

Loop until `review` approves with zero Addressable / Cheap-fix-override items:

1. Run `Skill(skill="review")` **in this main conversation** (the built-in command is unreachable from
   inside an `Agent`-dispatched sub-agent — that design consistently failed on PR #607, forcing prose
   instead of a real verdict). Write its verdict text to `<facts.scratch>/review-verdict.md`.
2. Dispatch **one** review-loop `general-purpose` sub-agent per iteration per
   [`../references/review-loop-sub-agent.md`](../references/review-loop-sub-agent.md) (it classifies per
   the rubric there, addresses Addressable + Cheap-fix items, runs the §10.6 pre-push gate = the same
   retry ladder as §8, commits, pushes, replies on the PR, returns JSON). "Approved" is **not** the
   exit condition — the sub-agent re-classifies every listed item; soft politeness ("not blocking")
   does not move an item out of Addressable.
3. Act on its JSON: `iteration_complete` with no items → exit the loop; `iteration_complete` with items
   addressed → re-run step 1; `needs_decision` → render its `decision_request` as one `AskUserQuestion`
   (guard rails: `deadlock`/`architectural`/`verification_failure`/`grounding_violation`), then
   re-dispatch a fresh sub-agent with the answer in its `prior_decisions` input (same verdict-file path).
   A **grounding-violation** item is never filed as a follow-up — the hard block exists to stop the ship.
4. After `review`'s verdict text lands, your next emissions are **operational tool calls**, not more
   prose — stopping at the verdict text is the PR #416/#653 missing-handoff failure mode. Cap the outer
   loop; on the cap ask (`header: "Iter cap"`): **Continue** (free-text count) / **Accept current** /
   **Abort**.

## S6 — DoD projection on the push that shipped the phase

On every push that ships a phase (and on re-entry reconciliation), project the shipped phase's
`closes-dod` onto the issue body's `## Definition of done` per
[`../references/dod-projection-rule.md`](../references/dod-projection-rule.md). Compute
`expected_set − (currently_ticked_set ∪ rejected_set)` from the PR's `## Phase tracker` (ticked
entries) × each ticked phase's `closes-dod`; apply only the diff. Write the three ticked forms only —
`(closed by phase <N>, commit <short-sha>)` / `(closed by phase <N>, operator action <ISO-date>)` /
`(closed by commit <short-sha>)` (single-phase fallback) — per
[`../../_shared/dod-annotations.md`](../../_shared/dod-annotations.md); 7-char SHAs. Stage the corrected
body to `<facts.scratch>/issue-body-projected.md` and apply it:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py edit-body <owner/repo> <issue> \
  "<facts.scratch>/issue-body-projected.md"
```

Then update the PR's `## Phase tracker` (stage + `edit-body` on the PR). Never tick a bullet the
phase's `closes-dod` doesn't claim (the resolver projects the planner's declaration, it doesn't infer).
Never re-tick a bullet the evaluator rejected (`… evaluator rejected: …` is a **sticky veto** —
resolve it by re-planning or a new phase, never by silent re-ticking). Never mark a multi-phase PR
ready except at the last-phase handoff, and never add `Closes #N` in reaction to shipping a phase — both
are the evaluator's judgment. Projection failure does **not** abort the run (re-entry reconciliation is
the backstop); log it and continue.

## S7 — Follow-ups

File `file-now` follow-ups (retry-ladder deferrals, review-deferred items) in-flight so `// TODO(#NNN)`
markers carry real numbers. Batch `file-at-checkpoint` items at the end of the loop and confirm before
filing, per [`../references/follow-up-tracking.md`](../references/follow-up-tracking.md); every filed
issue routes through the drafter proxy in [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md)
— never hand-craft a `gh issue create` body. Weave URLs into the PR body's `## Follow-ups` section, the
`// TODO` markers, and the handoff.

## Return to the routed playbook

Multi-phase last-planned-phase shipped: flip the PR draft → ready with
`gh pr ready <N> --repo <owner/repo>` **immediately before** the handoff (without the flip the
evaluator's draft-PR guard deadlocks the handoff). Then continue in the routed playbook (`standard.md`
/ `story.md`) for its handoff shape. On a re-route exit (audit blocker → drafter, plan drift →
planner, doc conflict → drafter), skip straight to the routed playbook's re-route handoff.
