# v1 baseline — line counts, contract-token census, artifact cross-reference

> Produced by [implementation.md](../implementation.md) step **S1** as the measurable parity baseline
> (prd.md §9.5 "Behavior parity", §10 "Success metrics"). Companion to the nine per-skill specs in
> this directory and the verbatim artifact examples under [`examples/`](examples/).

## 1. v1 line counts

### SKILL.md, per v2 skill name

The denominator for the [prd.md §10](../prd.md) success metric: "prompt text a pipeline session
loads (router + the one playbook) is at most half of the v1 `SKILL.md` line count for that skill."
Counts are `wc -l` against the v1 file, labelled by the v2 name each spec in this directory uses.

| v2 skill name | v1 `SKILL.md` path | Lines |
|---|---|---:|
| `drafter` | `skills/github-issue-drafter/SKILL.md` | 576 |
| `researcher` | `skills/github-issue-researcher/SKILL.md` | 289 |
| `planner` | `skills/github-issue-planner/SKILL.md` | 503 |
| `resolver` | `skills/github-issue-resolver/SKILL.md` | 1169 |
| `evaluator` | `skills/github-pr-evaluator/SKILL.md` | 971 |
| `setup` | `skills/github-pipeline-setup/SKILL.md` | 338 |
| `question-sweep` | `skills/open-questions/SKILL.md` | 147 |
| `question-resolver` | `skills/question-resolver/SKILL.md` | 185 |
| `doc-reviewer` | `skills/doc-reviewer/SKILL.md` | 144 |
| **Total** | | **4322** |

Command: `wc -l skills/<v1-dir>/SKILL.md` run once per row above; the total is
`cat <all nine SKILL.md paths> | wc -l` = 4322, confirmed to equal the column sum.

### Reference-file line counts, per skill

Every file under each skill's `references/` directory, subtotaled per skill. `doc-reviewer` has no
`references/` directory (confirmed: `ls skills/doc-reviewer/` shows only `SKILL.md`) — its
deterministic-and-reference surface is zero, which its own spec's "Deterministic steps" section
calls out explicitly.

| v2 skill name | Reference file | Lines |
|---|---|---:|
| `drafter` | `references/handoff-renderings.md` | 86 |
| | `references/issue-reviewer-prompt.md` | 131 |
| | `references/issue-templates.md` | 127 |
| | **subtotal** | **344** |
| `researcher` | `references/research-validator-prompt.md` | 128 |
| | **subtotal** | **128** |
| `planner` | `references/handoff-renderings.md` | 160 |
| | `references/plan-reviewer-prompt.md` | 178 |
| | `references/plan-schema.md` | 139 |
| | `references/revise-reconciliation.md` | 70 |
| | **subtotal** | **547** |
| `resolver` | `references/common-pitfalls.md` | 57 |
| | `references/dod-projection-rule.md` | 49 |
| | `references/epic-flow.md` | 146 |
| | `references/follow-up-tracking.md` | 64 |
| | `references/handoff-renderings.md` | 168 |
| | `references/issue-audit-prompt.md` | 161 |
| | `references/retry-ladder.md` | 92 |
| | `references/review-loop-sub-agent.md` | 204 |
| | `references/state-distiller-prompt.md` | 88 |
| | `references/test-selection-sub-agent.md` | 163 |
| | **subtotal** | **1192** |
| `evaluator` | `references/handoff-renderings.md` | 131 |
| | `references/test-selection-sub-agent.md` | 131 |
| | **subtotal** | **262** |
| `setup` | `references/block-authoring.md` | 490 |
| | **subtotal** | **490** |
| `question-sweep` | `references/question-status-reader-prompt.md` | 79 |
| | **subtotal** | **79** |
| `question-resolver` | `references/constraint-audit-prompt.md` | 71 |
| | **subtotal** | **71** |
| `doc-reviewer` | *(no `references/` directory)* | 0 |

Command: `wc -l skills/<v1-dir>/references/*.md` run once per skill directory that has one; a
skill's subtotal is the sum of its rows (cross-checked with `cat skills/<v1-dir>/references/*.md \|
wc -l`).

## 2. Contract-token census (command + verbatim output)

This is the **S1 baseline census** — every later cutover step
([S7](../implementation.md)/S10/S13/S15–S19/S20 in `docs/implementation.md`) re-runs the identical
command and diffs its output against the numbers recorded here. The global DoD's "for skill-cutover
steps the contract-token census is re-run against the S1 baseline" clause points at this section.

The baseline deliberately includes **v1-only tokens** that v2 will legitimately retire: the resolver's
`§P`-prefixed procedure IDs (`§P1`–`§P6`), the `github-ops` op names (`GATHER_*`/`PERSIST_*` — v2's
scripts replace the sub-agent), and the `github-pipeline:github-*` v1 skill-namespace strings (v2
skills are renamed per the drafter's addendum table, e.g. `github-pipeline:github-issue-planner` →
`github-pipeline:planner`). Recording them here means a later drop is an **accounted-for** retirement
a reviewer can diff against this table, not a silent loss the census would otherwise mask.

### Command

```
grep -roE '<!-- [a-z0-9:-]+ -->|§P?[0-9]+(\.[0-9]+)?|GATHER_[A-Z]+|PERSIST_[A-Z]+|github-pipeline:[a-z-]+' skills/ agents/ | sort | uniq -c
```

### Verbatim output

```
   1 agents/github-ops.md:<!-- implementation-plan:v1 -->
   2 agents/github-ops.md:GATHER_EPIC
   3 agents/github-ops.md:GATHER_ISSUE
   3 agents/github-ops.md:GATHER_PR
   7 agents/github-ops.md:PERSIST_BODY
   2 agents/github-ops.md:PERSIST_CLOSE
   5 agents/github-ops.md:PERSIST_COMMENT
   4 agents/github-ops.md:PERSIST_CREATE
   2 agents/github-ops.md:PERSIST_LINK
   2 agents/github-ops.md:PERSIST_REOPEN
   2 skills/_shared/dod-annotations.md:§6
   4 skills/_shared/dod-annotations.md:§9
   3 skills/_shared/epic-delivery-log.md:<!-- epic-delivery-log:v1 -->
   1 skills/_shared/epic-delivery-log.md:<!-- implementation-plan:v1 -->
   1 skills/_shared/epic-delivery-log.md:PERSIST_COMMENT
   1 skills/_shared/epic-delivery-log.md:§13
   1 skills/_shared/epic-delivery-log.md:§5.6
   1 skills/_shared/follow-up-filing.md:§10
   1 skills/_shared/follow-up-filing.md:§P5
   1 skills/_shared/handoff-format.md:GATHER_ISSUE
   1 skills/_shared/handoff-format.md:GATHER_PR
   1 skills/_shared/handoff-format.md:§12.0
   1 skills/_shared/handoff-format.md:§14
   1 skills/_shared/open-question-detection.md:<!-- drafter-open-question-markers -->
   1 skills/_shared/open-question-links.md:<!-- implementation-plan:v1 -->
   3 skills/_shared/open-question-links.md:<!-- open-question-links:v1 -->
   5 skills/_shared/open-question-links.md:<!-- question-decision:v1 -->
   2 skills/_shared/open-question-links.md:GATHER_ISSUE
   1 skills/_shared/open-question-links.md:PERSIST_LINK
   1 skills/_shared/open-question-links.md:github-pipeline:question-resolver
   1 skills/_shared/open-question-links.md:§12
   1 skills/_shared/open-question-links.md:§5
   1 skills/_shared/open-question-links.md:§7.5
   3 skills/_shared/subagent-decision-signal.md:§12
   1 skills/_shared/subagent-decision-signal.md:§4.6
   1 skills/_shared/subagent-decision-signal.md:§4.7
   3 skills/_shared/subagent-decision-signal.md:§P6
   2 skills/_shared/worktree-lifecycle.md:<!-- worktree-setup -->
   2 skills/_shared/worktree-lifecycle.md:<!-- worktree-teardown -->
   2 skills/doc-reviewer/SKILL.md:github-pipeline:doc-reviewer
   1 skills/github-issue-drafter/SKILL.md:<!-- drafter-open-question-markers -->
   1 skills/github-issue-drafter/SKILL.md:<!-- implementation-plan:v1 -->
   1 skills/github-issue-drafter/SKILL.md:GATHER_EPIC
   2 skills/github-issue-drafter/SKILL.md:GATHER_ISSUE
   5 skills/github-issue-drafter/SKILL.md:PERSIST_BODY
  11 skills/github-issue-drafter/SKILL.md:PERSIST_CREATE
   3 skills/github-issue-drafter/SKILL.md:PERSIST_LINK
   1 skills/github-issue-drafter/SKILL.md:github-pipeline:github-ops
   2 skills/github-issue-drafter/SKILL.md:github-pipeline:open-questions
   1 skills/github-issue-drafter/SKILL.md:§4
   1 skills/github-issue-drafter/references/handoff-renderings.md:<!-- implementation-plan:v1 -->
   4 skills/github-issue-drafter/references/handoff-renderings.md:github-pipeline:github-issue-planner
   1 skills/github-issue-drafter/references/issue-reviewer-prompt.md:<!-- drafter-open-question-markers -->
   1 skills/github-issue-drafter/references/issue-reviewer-prompt.md:§12
   1 skills/github-issue-planner/SKILL.md:<!-- drafter-open-question-markers -->
  11 skills/github-issue-planner/SKILL.md:<!-- epic-delivery-log:v1 -->
   8 skills/github-issue-planner/SKILL.md:<!-- implementation-plan:v1 -->
   2 skills/github-issue-planner/SKILL.md:<!-- issue-research:v1 -->
   1 skills/github-issue-planner/SKILL.md:<!-- open-question-links:v1 -->
   3 skills/github-issue-planner/SKILL.md:GATHER_EPIC
   5 skills/github-issue-planner/SKILL.md:GATHER_ISSUE
   2 skills/github-issue-planner/SKILL.md:PERSIST_BODY
   3 skills/github-issue-planner/SKILL.md:PERSIST_COMMENT
   2 skills/github-issue-planner/SKILL.md:github-pipeline:github-issue-planner
   1 skills/github-issue-planner/SKILL.md:github-pipeline:github-issue-researcher
   1 skills/github-issue-planner/SKILL.md:github-pipeline:github-ops
   1 skills/github-issue-planner/SKILL.md:§10
   1 skills/github-issue-planner/SKILL.md:§10.3
   1 skills/github-issue-planner/SKILL.md:§11
   1 skills/github-issue-planner/SKILL.md:§13
   2 skills/github-issue-planner/SKILL.md:§2
   2 skills/github-issue-planner/SKILL.md:§4.5
   1 skills/github-issue-planner/SKILL.md:§4.6
   2 skills/github-issue-planner/SKILL.md:§6
   1 skills/github-issue-planner/SKILL.md:§8
   2 skills/github-issue-planner/SKILL.md:§9
   2 skills/github-issue-planner/references/handoff-renderings.md:github-pipeline:github-issue-drafter
   5 skills/github-issue-planner/references/handoff-renderings.md:github-pipeline:github-issue-planner
   1 skills/github-issue-planner/references/handoff-renderings.md:github-pipeline:github-issue-researcher
   7 skills/github-issue-planner/references/handoff-renderings.md:github-pipeline:github-issue-resolver
   4 skills/github-issue-planner/references/handoff-renderings.md:§2
   3 skills/github-issue-planner/references/handoff-renderings.md:§3
   2 skills/github-issue-planner/references/handoff-renderings.md:§4
   4 skills/github-issue-planner/references/handoff-renderings.md:§5
   2 skills/github-issue-planner/references/handoff-renderings.md:§6
   3 skills/github-issue-planner/references/handoff-renderings.md:§7
   1 skills/github-issue-planner/references/handoff-renderings.md:§8
   2 skills/github-issue-planner/references/plan-reviewer-prompt.md:<!-- epic-delivery-log:v1 -->
   1 skills/github-issue-planner/references/plan-reviewer-prompt.md:§10
   2 skills/github-issue-planner/references/plan-reviewer-prompt.md:§2
   1 skills/github-issue-planner/references/plan-reviewer-prompt.md:§5
   1 skills/github-issue-planner/references/plan-reviewer-prompt.md:§6
   1 skills/github-issue-planner/references/plan-reviewer-prompt.md:§8
   3 skills/github-issue-planner/references/plan-schema.md:<!-- epic-delivery-log:v1 -->
   3 skills/github-issue-planner/references/plan-schema.md:<!-- implementation-plan:v1 -->
   1 skills/github-issue-planner/references/plan-schema.md:§5
   1 skills/github-issue-planner/references/plan-schema.md:§5.5
   1 skills/github-issue-planner/references/plan-schema.md:§8
   1 skills/github-issue-planner/references/revise-reconciliation.md:PERSIST_BODY
   2 skills/github-issue-planner/references/revise-reconciliation.md:github-pipeline:github-issue-resolver
   1 skills/github-issue-planner/references/revise-reconciliation.md:§6
   2 skills/github-issue-planner/references/revise-reconciliation.md:§9
   1 skills/github-issue-researcher/SKILL.md:<!-- implementation-plan:v1 -->
   4 skills/github-issue-researcher/SKILL.md:<!-- issue-research:v1 -->
   2 skills/github-issue-researcher/SKILL.md:GATHER_ISSUE
   2 skills/github-issue-researcher/SKILL.md:PERSIST_COMMENT
   2 skills/github-issue-researcher/SKILL.md:github-pipeline:github-issue-planner
   2 skills/github-issue-researcher/SKILL.md:github-pipeline:github-issue-researcher
   1 skills/github-issue-researcher/SKILL.md:github-pipeline:github-ops
   2 skills/github-issue-resolver/SKILL.md:<!-- implementation-plan:v1 -->
   1 skills/github-issue-resolver/SKILL.md:<!-- issue-resolver-canonical-suite -->
   4 skills/github-issue-resolver/SKILL.md:<!-- issue-resolver-fast-checks -->
   4 skills/github-issue-resolver/SKILL.md:<!-- issue-resolver-test-target -->
   1 skills/github-issue-resolver/SKILL.md:<!-- open-question-links:v1 -->
   1 skills/github-issue-resolver/SKILL.md:<!-- pr-evaluator-health-checks -->
   1 skills/github-issue-resolver/SKILL.md:<!-- worktree-setup -->
   2 skills/github-issue-resolver/SKILL.md:<!-- worktree-teardown -->
   8 skills/github-issue-resolver/SKILL.md:GATHER_ISSUE
   3 skills/github-issue-resolver/SKILL.md:PERSIST_COMMENT
   2 skills/github-issue-resolver/SKILL.md:github-pipeline:github-issue-planner
   2 skills/github-issue-resolver/SKILL.md:github-pipeline:github-issue-resolver
   1 skills/github-issue-resolver/SKILL.md:github-pipeline:github-ops
   1 skills/github-issue-resolver/SKILL.md:§1
  24 skills/github-issue-resolver/SKILL.md:§10
   6 skills/github-issue-resolver/SKILL.md:§10.4
  21 skills/github-issue-resolver/SKILL.md:§10.6
   9 skills/github-issue-resolver/SKILL.md:§10.7
  48 skills/github-issue-resolver/SKILL.md:§11
  14 skills/github-issue-resolver/SKILL.md:§12
   3 skills/github-issue-resolver/SKILL.md:§14
   1 skills/github-issue-resolver/SKILL.md:§15
   3 skills/github-issue-resolver/SKILL.md:§2
   8 skills/github-issue-resolver/SKILL.md:§3
   4 skills/github-issue-resolver/SKILL.md:§4
  18 skills/github-issue-resolver/SKILL.md:§4.5
  16 skills/github-issue-resolver/SKILL.md:§4.6
  19 skills/github-issue-resolver/SKILL.md:§4.7
   4 skills/github-issue-resolver/SKILL.md:§5
   1 skills/github-issue-resolver/SKILL.md:§5.5
   3 skills/github-issue-resolver/SKILL.md:§6
   6 skills/github-issue-resolver/SKILL.md:§7
  24 skills/github-issue-resolver/SKILL.md:§8
  12 skills/github-issue-resolver/SKILL.md:§9
   3 skills/github-issue-resolver/SKILL.md:§P1
   7 skills/github-issue-resolver/SKILL.md:§P2
   4 skills/github-issue-resolver/SKILL.md:§P3
   1 skills/github-issue-resolver/SKILL.md:§P3.1
   2 skills/github-issue-resolver/SKILL.md:§P3.2
   2 skills/github-issue-resolver/SKILL.md:§P3.3
   1 skills/github-issue-resolver/SKILL.md:§P3.4
   4 skills/github-issue-resolver/SKILL.md:§P4
   4 skills/github-issue-resolver/SKILL.md:§P5
  12 skills/github-issue-resolver/SKILL.md:§P6
   1 skills/github-issue-resolver/references/common-pitfalls.md:<!-- pr-evaluator-static-checks -->
   1 skills/github-issue-resolver/references/common-pitfalls.md:<!-- pr-evaluator-test-target -->
   7 skills/github-issue-resolver/references/common-pitfalls.md:§10
   2 skills/github-issue-resolver/references/common-pitfalls.md:§10.4
   4 skills/github-issue-resolver/references/common-pitfalls.md:§10.6
   2 skills/github-issue-resolver/references/common-pitfalls.md:§10.7
   6 skills/github-issue-resolver/references/common-pitfalls.md:§11
   1 skills/github-issue-resolver/references/common-pitfalls.md:§12
   1 skills/github-issue-resolver/references/common-pitfalls.md:§4.7
   9 skills/github-issue-resolver/references/common-pitfalls.md:§8
   1 skills/github-issue-resolver/references/common-pitfalls.md:§9
   1 skills/github-issue-resolver/references/common-pitfalls.md:§P2
   1 skills/github-issue-resolver/references/common-pitfalls.md:§P4
   2 skills/github-issue-resolver/references/dod-projection-rule.md:§10.6
   4 skills/github-issue-resolver/references/dod-projection-rule.md:§4.7
   2 skills/github-issue-resolver/references/dod-projection-rule.md:§9
   3 skills/github-issue-resolver/references/epic-flow.md:§10.6
   3 skills/github-issue-resolver/references/epic-flow.md:§7
   3 skills/github-issue-resolver/references/epic-flow.md:§8
   2 skills/github-issue-resolver/references/epic-flow.md:§P2
   2 skills/github-issue-resolver/references/epic-flow.md:§P3.1
   1 skills/github-issue-resolver/references/epic-flow.md:§P3.4
   4 skills/github-issue-resolver/references/follow-up-tracking.md:§10
   2 skills/github-issue-resolver/references/follow-up-tracking.md:§10.4
   6 skills/github-issue-resolver/references/follow-up-tracking.md:§11
   1 skills/github-issue-resolver/references/follow-up-tracking.md:§6
   2 skills/github-issue-resolver/references/follow-up-tracking.md:§7
   1 skills/github-issue-resolver/references/follow-up-tracking.md:§8
   1 skills/github-issue-resolver/references/follow-up-tracking.md:§P5
   2 skills/github-issue-resolver/references/handoff-renderings.md:github-pipeline:github-issue-drafter
   1 skills/github-issue-resolver/references/handoff-renderings.md:github-pipeline:github-issue-planner
   3 skills/github-issue-resolver/references/handoff-renderings.md:github-pipeline:github-issue-resolver
   3 skills/github-issue-resolver/references/handoff-renderings.md:github-pipeline:github-pr-evaluator
   1 skills/github-issue-resolver/references/handoff-renderings.md:§10.7
   2 skills/github-issue-resolver/references/handoff-renderings.md:§11
   1 skills/github-issue-resolver/references/handoff-renderings.md:§12
   1 skills/github-issue-resolver/references/handoff-renderings.md:§3
   1 skills/github-issue-resolver/references/handoff-renderings.md:§4
   2 skills/github-issue-resolver/references/handoff-renderings.md:§4.5
   3 skills/github-issue-resolver/references/handoff-renderings.md:§4.6
   1 skills/github-issue-resolver/references/handoff-renderings.md:§4.7
   1 skills/github-issue-resolver/references/handoff-renderings.md:§5
   2 skills/github-issue-resolver/references/handoff-renderings.md:§6
   3 skills/github-issue-resolver/references/handoff-renderings.md:§8
   1 skills/github-issue-resolver/references/issue-audit-prompt.md:<!-- implementation-plan:v1 -->
   1 skills/github-issue-resolver/references/retry-ladder.md:§10
   6 skills/github-issue-resolver/references/retry-ladder.md:§10.6
   2 skills/github-issue-resolver/references/retry-ladder.md:§10.7
   1 skills/github-issue-resolver/references/retry-ladder.md:§11
   5 skills/github-issue-resolver/references/retry-ladder.md:§8
   4 skills/github-issue-resolver/references/retry-ladder.md:§9
   3 skills/github-issue-resolver/references/review-loop-sub-agent.md:§10
   6 skills/github-issue-resolver/references/review-loop-sub-agent.md:§10.4
   5 skills/github-issue-resolver/references/review-loop-sub-agent.md:§10.6
   1 skills/github-issue-resolver/references/review-loop-sub-agent.md:§11
   1 skills/github-issue-resolver/references/review-loop-sub-agent.md:§4.5
   1 skills/github-issue-resolver/references/review-loop-sub-agent.md:§6
   1 skills/github-issue-resolver/references/state-distiller-prompt.md:<!-- implementation-plan:v1 -->
   1 skills/github-issue-resolver/references/state-distiller-prompt.md:§3.2
   1 skills/github-issue-resolver/references/state-distiller-prompt.md:§4
   1 skills/github-issue-resolver/references/state-distiller-prompt.md:§4.5
   1 skills/github-issue-resolver/references/state-distiller-prompt.md:§4.6
   1 skills/github-issue-resolver/references/state-distiller-prompt.md:§P6
   2 skills/github-issue-resolver/references/test-selection-sub-agent.md:<!-- issue-resolver-test-target -->
   1 skills/github-issue-resolver/references/test-selection-sub-agent.md:§10.6
   1 skills/github-issue-resolver/references/test-selection-sub-agent.md:§8
   1 skills/github-pipeline-setup/SKILL.md:github-pipeline:github-issue-drafter
   1 skills/github-pipeline-setup/SKILL.md:github-pipeline:github-issue-resolver
   2 skills/github-pipeline-setup/SKILL.md:§2
   4 skills/github-pipeline-setup/SKILL.md:§3
   2 skills/github-pipeline-setup/SKILL.md:§4
   1 skills/github-pipeline-setup/SKILL.md:§5
   1 skills/github-pipeline-setup/SKILL.md:§7
   3 skills/github-pipeline-setup/references/block-authoring.md:<!-- claude-code-stack-profile -->
   1 skills/github-pipeline-setup/references/block-authoring.md:<!-- github-pipeline-config -->
   3 skills/github-pipeline-setup/references/block-authoring.md:<!-- issue-resolver-canonical-suite -->
   1 skills/github-pipeline-setup/references/block-authoring.md:<!-- issue-resolver-fast-checks -->
   1 skills/github-pipeline-setup/references/block-authoring.md:<!-- issue-resolver-test-target -->
   3 skills/github-pipeline-setup/references/block-authoring.md:<!-- pr-evaluator-escalation-labels -->
   1 skills/github-pipeline-setup/references/block-authoring.md:<!-- pr-evaluator-merge-policy -->
   3 skills/github-pipeline-setup/references/block-authoring.md:<!-- pr-evaluator-static-checks -->
   3 skills/github-pipeline-setup/references/block-authoring.md:<!-- pr-evaluator-test-target -->
   1 skills/github-pipeline-setup/references/block-authoring.md:<!-- worktree-setup -->
   1 skills/github-pipeline-setup/references/block-authoring.md:<!-- worktree-teardown -->
   1 skills/github-pipeline-setup/references/block-authoring.md:§10.6
   1 skills/github-pipeline-setup/references/block-authoring.md:§12
   1 skills/github-pipeline-setup/references/block-authoring.md:§12.0
   3 skills/github-pipeline-setup/references/block-authoring.md:§3
   1 skills/github-pipeline-setup/references/block-authoring.md:§6
   1 skills/github-pipeline-setup/references/block-authoring.md:§7
   1 skills/github-pipeline-setup/references/block-authoring.md:§8
   1 skills/github-pipeline-setup/references/block-authoring.md:§P2
   1 skills/github-pipeline-setup/references/block-authoring.md:§P3.1
   3 skills/github-pr-evaluator/SKILL.md:<!-- epic-delivery-log:v1 -->
   3 skills/github-pr-evaluator/SKILL.md:<!-- implementation-plan:v1 -->
   1 skills/github-pr-evaluator/SKILL.md:<!-- open-question-links:v1 -->
   7 skills/github-pr-evaluator/SKILL.md:<!-- pr-evaluator-escalation-labels -->
   3 skills/github-pr-evaluator/SKILL.md:<!-- pr-evaluator-health-cache:v1 -->
   4 skills/github-pr-evaluator/SKILL.md:<!-- pr-evaluator-health-checks -->
   7 skills/github-pr-evaluator/SKILL.md:<!-- pr-evaluator-merge-policy -->
   9 skills/github-pr-evaluator/SKILL.md:<!-- pr-evaluator-static-checks -->
   7 skills/github-pr-evaluator/SKILL.md:<!-- pr-evaluator-test-target -->
   1 skills/github-pr-evaluator/SKILL.md:<!-- worktree-setup -->
   2 skills/github-pr-evaluator/SKILL.md:<!-- worktree-teardown -->
   6 skills/github-pr-evaluator/SKILL.md:GATHER_ISSUE
   8 skills/github-pr-evaluator/SKILL.md:GATHER_PR
   7 skills/github-pr-evaluator/SKILL.md:PERSIST_COMMENT
   3 skills/github-pr-evaluator/SKILL.md:PERSIST_ISSUE
   1 skills/github-pr-evaluator/SKILL.md:github-pipeline:github-ops
   4 skills/github-pr-evaluator/SKILL.md:§10
  17 skills/github-pr-evaluator/SKILL.md:§11
  29 skills/github-pr-evaluator/SKILL.md:§12
  36 skills/github-pr-evaluator/SKILL.md:§12.0
   5 skills/github-pr-evaluator/SKILL.md:§13
   9 skills/github-pr-evaluator/SKILL.md:§14
   6 skills/github-pr-evaluator/SKILL.md:§15
   8 skills/github-pr-evaluator/SKILL.md:§2
   8 skills/github-pr-evaluator/SKILL.md:§3
   2 skills/github-pr-evaluator/SKILL.md:§4.7
   3 skills/github-pr-evaluator/SKILL.md:§5
   2 skills/github-pr-evaluator/SKILL.md:§5.1
   3 skills/github-pr-evaluator/SKILL.md:§5.2
   4 skills/github-pr-evaluator/SKILL.md:§5.3
   3 skills/github-pr-evaluator/SKILL.md:§5.4
  14 skills/github-pr-evaluator/SKILL.md:§5.5
  10 skills/github-pr-evaluator/SKILL.md:§5.6
   6 skills/github-pr-evaluator/SKILL.md:§6
  13 skills/github-pr-evaluator/SKILL.md:§7
  10 skills/github-pr-evaluator/SKILL.md:§8
   1 skills/github-pr-evaluator/SKILL.md:§9
   1 skills/github-pr-evaluator/SKILL.md:§P2
   1 skills/github-pr-evaluator/references/handoff-renderings.md:github-pipeline:github-issue-planner
   3 skills/github-pr-evaluator/references/handoff-renderings.md:github-pipeline:github-issue-resolver
   2 skills/github-pr-evaluator/references/handoff-renderings.md:§10
   4 skills/github-pr-evaluator/references/handoff-renderings.md:§11
   6 skills/github-pr-evaluator/references/handoff-renderings.md:§12
  11 skills/github-pr-evaluator/references/handoff-renderings.md:§12.0
   3 skills/github-pr-evaluator/references/handoff-renderings.md:§13
   1 skills/github-pr-evaluator/references/handoff-renderings.md:§15
   2 skills/github-pr-evaluator/references/handoff-renderings.md:§2
   1 skills/github-pr-evaluator/references/handoff-renderings.md:§3
   2 skills/github-pr-evaluator/references/handoff-renderings.md:§5
   2 skills/github-pr-evaluator/references/handoff-renderings.md:§7
   2 skills/github-pr-evaluator/references/test-selection-sub-agent.md:<!-- pr-evaluator-test-target -->
   1 skills/github-pr-evaluator/references/test-selection-sub-agent.md:§5.5
   1 skills/open-questions/SKILL.md:<!-- drafter-open-question-markers -->
   3 skills/open-questions/SKILL.md:<!-- question-decision:v1 -->
   2 skills/open-questions/SKILL.md:GATHER_ISSUE
   1 skills/open-questions/SKILL.md:PERSIST_BODY
   1 skills/open-questions/SKILL.md:PERSIST_CREATE
   1 skills/open-questions/SKILL.md:github-pipeline:github-issue-planner
   1 skills/open-questions/SKILL.md:github-pipeline:github-ops
   1 skills/open-questions/SKILL.md:github-pipeline:open-questions
   1 skills/open-questions/references/question-status-reader-prompt.md:<!-- question-decision:v1 -->
   4 skills/question-resolver/SKILL.md:<!-- question-decision:v1 -->
   1 skills/question-resolver/SKILL.md:GATHER_ISSUE
   2 skills/question-resolver/SKILL.md:PERSIST_CLOSE
   2 skills/question-resolver/SKILL.md:PERSIST_COMMENT
   1 skills/question-resolver/SKILL.md:PERSIST_REOPEN
   1 skills/question-resolver/SKILL.md:github-pipeline:github-issue-planner
   1 skills/question-resolver/SKILL.md:github-pipeline:github-issue-resolver
   1 skills/question-resolver/SKILL.md:github-pipeline:github-ops
   1 skills/question-resolver/SKILL.md:github-pipeline:question-resolver
```

### Distinct-token count

Command:

```
grep -roE '<!-- [a-z0-9:-]+ -->|§P?[0-9]+(\.[0-9]+)?|GATHER_[A-Z]+|PERSIST_[A-Z]+|github-pipeline:[a-z-]+' skills/ agents/ | sed 's/^[^:]*://' | sort -u | wc -l
```

Output: **79**

### Reading this table for a later cutover step

A cutover step re-runs the exact command above post-cutover and compares against this table
(grouped by `path:token`, so a moved token shows as a new path with the same token, and a
paraphrased or dropped token shows as a missing row). Three categories, by how the diff should
read:

- **Contract tokens that must survive verbatim, wherever they end up** — every `<!-- …:v1 -->`
  marker (e.g. `<!-- implementation-plan:v1 -->`, `<!-- epic-delivery-log:v1 -->`,
  `<!-- question-decision:v1 -->`), every consuming-repo config-block marker (`<!-- issue-resolver-*
  -->`, `<!-- pr-evaluator-* -->`, `<!-- drafter-open-question-markers -->`, `<!-- worktree-setup/-teardown
  -->`, `<!-- claude-code-stack-profile -->`, `<!-- github-pipeline-config -->`). These are the
  compatibility contract (prd.md §7) — a v2 skill must still read/write them by these exact strings.
- **v1-only tokens expected to retire, and where** — the `§P`-IDs (`§P1`–`§P6`, resolver-local per
  `CLAUDE.md`'s editing conventions — these do not roll out to other v2 skills), the `GATHER_*` /
  `PERSIST_*` op names (retire with the `github-ops` sub-agent once its scripts/prep-modules replace
  it — architecture §9.1's "no intermediary agent relays between a skill and its scripts"), and every
  `github-pipeline:github-*` v1 skill-namespace string (retire per-skill at that skill's own cutover
  step, replaced by the v2 name, e.g. `github-pipeline:github-issue-planner` →
  `github-pipeline:planner`). A drop in these three buckets at the right cutover step is the
  *expected* diff, not a regression.
- **Bare `§N` / `§N.N` anchors** (no `P` prefix) inside each `SKILL.md` and its `references/*.md` —
  these are the skill's own internal section anchors (`§1`–`§15` in the resolver and evaluator,
  `§2`–`§13` in the planner, etc.) and stay stable across a *content* rewrite per `CLAUDE.md`'s
  "§-anchors are stable" rule — a cutover step's rewritten router+playbook may renumber or restructure
  freely, but any *other* file that cites one of these anchors by name must still resolve, so a
  disappearing bare-`§N` row is a genuine cross-reference break to investigate, not an expected
  retirement.

## 3. §7 artifact ↔ skill cross-reference table

One row per [prd.md §7](../prd.md) persisted artifact (all 12), grounded by reading the nine
`docs/specs/<skill>.md` files in this directory — every Writer/Reader cell below cites the spec
section that names the artifact, not a guess.

| # | Artifact | Where it lives | Writer spec(s) | Reader spec(s) | Example file |
|---|---|---|---|---|---|
| 1 | `<!-- implementation-plan:v1 -->` plan comment | issue comment | `planner` (`docs/specs/planner.md` "Artifacts written" — every plan variant: single-issue, Epic, story-under-epic) | `resolver` (`docs/specs/resolver.md` "Artifacts read": "Implementation plan… fetched by `GATHER_ISSUE`'s `marker_prefix` lookup"); `evaluator` (`docs/specs/evaluator.md` "Artifacts read": "`## Architecture decisions`, `## Changes`… `## Epic contract` `Delivers:` line"); `drafter` (`docs/specs/drafter.md` "Artifacts read", revise mode only — reads the pointer but never edits the comment); `planner` (self, revise mode: `docs/specs/planner.md` "Artifacts read": "Prior plan comment (revise-mode trigger)") | `examples/implementation-plan.md` |
| 2 | `<!-- issue-research:v1 -->` dossier comment | issue comment | `researcher` (`docs/specs/researcher.md` "Artifacts written") | `planner` (`docs/specs/planner.md` "Artifacts read": "Research dossier… feeds `## Doc grounding` / `## Architecture decisions`"); `researcher` (self, revise mode: `docs/specs/researcher.md` "Artifacts read": "Existing research dossier (self, prior run)") | `examples/issue-research.md` |
| 3 | `<!-- epic-delivery-log:v1 -->` delivery log | epic issue comment | `evaluator` (`docs/specs/evaluator.md` "Artifacts written" — "evaluator is the **sole writer**, per `epic-delivery-log.md:9`") | `planner` (`docs/specs/planner.md` "Artifacts read": "per-story actually-delivered contract shapes… reconciled against the epic plan's *pinned* contracts before a story is grounded") | `examples/epic-delivery-log.md` |
| 4 | `<!-- question-decision:v1 -->` recorded decision | question issue comment | `question-resolver` (`docs/specs/question-resolver.md` "Artifacts written" — "the durable, machine-readable resolution the tiered status read short-circuits on") | `question-sweep` (`docs/specs/question-sweep.md` "Artifacts read": "Tier-1 status signal: presence… means the question is **resolved** without a reader dispatch"); `planner` (`docs/specs/planner.md` "Artifacts read": tiered status read via `open-question-links.md`); `drafter` (`docs/specs/drafter.md` "Artifacts read": "Companion question `state` (+ `<!-- question-decision:v1 -->` marker…)"); `question-resolver` (self, reentrancy check: `docs/specs/question-resolver.md` "Artifacts read": "Reentrancy signal…") | `examples/question-decision.md` |
| 5 | `<!-- open-question-links:v1 -->` section + closed disposition set | build-issue body | `drafter` (`docs/specs/drafter.md` "Artifacts written": "`## Open questions` section… from Step 3.5 dispositions"); `question-sweep` (`docs/specs/question-sweep.md` "Artifacts written": "missing-back-link" doc/issue-side patches) | `resolver` (`docs/specs/resolver.md` "Artifacts read": "Per-entry disposition… read for context only — never implemented as scope or DoD"); `evaluator` (`docs/specs/evaluator.md` "Artifacts read": "Read only via the native `blocked_by` relationship it sets — bullets themselves are **not** read as DoD/acceptance-criteria"); `planner` (`docs/specs/planner.md` "Artifacts read": "`question`-type tracker issues"); `drafter` (self, revise mode: `docs/specs/drafter.md` "Artifacts read": "Reconcile open questions") | `examples/open-question-links.md` |
| 6 | Definition-of-done checkbox annotations (closed set) | issue body | `resolver` (`docs/specs/resolver.md` "Artifacts written": "DoD checkbox projection"); `evaluator` (`docs/specs/evaluator.md` "Artifacts written": "DoD un-tick (sticky veto)"); `planner` (`docs/specs/planner.md` "Artifacts written": "Reconciled issue body… planner writes the SOFT-path re-attribution forms and the HARD-path… predecessor annotation") | `resolver` (self, re-entry reconciliation: `docs/specs/resolver.md` "Artifacts read": "read to detect prior rejections/predecessors before projecting"); `evaluator` (`docs/specs/evaluator.md` "Artifacts read": "`closed by` forms… drive per-phase verification"); `planner` (`docs/specs/planner.md` "Deterministic steps": "reconciliation reads the current body to compute the body-edit diff") | `examples/dod-annotations.md` |
| 7 | `<!-- pr-evaluator-health-cache:v1 -->` health-cache comment | PR comment | `evaluator` (`docs/specs/evaluator.md` "Artifacts written": "Every run of the §5 branch-health gate…") | `evaluator` (self — see note below) | `examples/pr-evaluator-health-cache.md` |
| 8 | `## Phase tracker` section (multi-phase issues) | PR body | `resolver` (`docs/specs/resolver.md` "Artifacts written": "added at fresh-PR-open for multi-phase issues; updated via `gh pr edit` on every subsequent phase push") | `resolver` (self, re-entry: `docs/specs/resolver.md` "Artifacts read" and "Judgment steps" §4.7 "consumes the state-distiller's parsed phases… it already read the plan's `## Phases` section" — resumption reads this PR-body tracker directly, not via the distiller); `evaluator` (`docs/specs/evaluator.md` "Artifacts read": "`- [x] Phase N — title (commit <sha>)` entries — the phase→commit mapping for per-phase verification") | `examples/phase-tracker.md` |
| 9 | `question`-issue body schema + `audience:*` labels | question issues | `drafter` (`docs/specs/drafter.md` "Artifacts written": "Filed `question`-type issue"); `question-sweep` (`docs/specs/question-sweep.md` "Artifacts written": "Companion `question` issue… per `skills/_shared/question-issue.md:12-33`") | `question-resolver` (`docs/specs/question-resolver.md` "Artifacts read": "Question-issue body + thread… labels (`question` + `audience:*`)"); `question-sweep` (`docs/specs/question-sweep.md` "Artifacts read": "`question`-type issue skeleton"); `planner` (`docs/specs/planner.md` "Artifacts read": "`question`-type tracker issues") | `examples/question-issue-body.md` |
| 10 | `## Handoff` schema + closed-set state markers | session output | `drafter`, `researcher`, `planner`, `resolver`, `evaluator` — all five pipeline specs' "Artifacts written" tables name it as their terminal Step's output, schema owned by `skills/_shared/handoff-format.md` | **the operator** — the shared contract states plainly this is "the only bridge between sessions"; the handoff has no *skill* reader in v1 at all (no skill parses another skill's handoff — the next session's *command line* is copy-pasted by a human). Recorded here explicitly, per this task's own instruction, rather than naming a skill that doesn't actually read it. | `examples/handoff-schema.md` (schema) plus five worked samples: `examples/handoff-drafter.md`, `examples/handoff-researcher.md`, `examples/handoff-planner.md`, `examples/handoff-resolver.md`, `examples/handoff-evaluator.md` |
| 11 | Config marker blocks (`issue-resolver-*`, `pr-evaluator-*`, `drafter-open-question-markers`, `worktree-setup`/`-teardown`, `claude-code-stack-profile`) | consuming repo `CLAUDE.md`/`COMMANDS.md` | `setup` (`docs/specs/setup.md` "Artifacts written" — "single writer of those blocks", all eleven rows, "the machine-parsed blocks plus `github-pipeline-config`") | `resolver` (`docs/specs/resolver.md` "Artifacts read": "Resolver-side config blocks", "Fallback config blocks"); `evaluator` (`docs/specs/evaluator.md` "Artifacts read": "Config: static checks / test target / escalation labels / merge policy", "Legacy config: health checks"); `drafter` (`docs/specs/drafter.md` "Artifacts read": "`<!-- drafter-open-question-markers -->` config block"); `planner` (`docs/specs/planner.md` "Artifacts read": inherits the same OQ-marker block via the shared open-question-detection contract, and reads the worktree/test blocks only indirectly through the resolver's plan-gate — recorded per this task's brief's own "readers: `resolver`, `evaluator`, `drafter`, `planner`" line) | `examples/config-blocks.md` |
| 12 | `epic/<N>-<slug>` integration-branch naming | consuming repo branches | `resolver` (`docs/specs/resolver.md` "Invariants": "**Discover the epic branch slug by prefix; only compute fresh on bootstrap**" — the resolver is the branch's sole creator, via the bootstrap sequence in `references/epic-flow.md`) | `resolver` (self — every subsequent epic-as-target and story-under-epic run discovers the branch by prefix to resume, per the same invariant); `evaluator` (`docs/specs/evaluator.md` "Deterministic steps": "PR-type classification — `headRefName`, `baseRefName`… → `epic-integration \| story \| regular`" — reads the branch name to classify the PR shape) | `examples/epic-branch-naming.md` |

**Notes on the tricky rows** (as the brief flags):

- **Row 10, `## Handoff`.** All five pipeline specs are writers; the reader is the **human
  operator**, reading cold across a session boundary — not a skill. No `docs/specs/<skill>.md`
  "Artifacts read" table names the `## Handoff` block as something it consumes, because
  `_shared/handoff-format.md` and every resolver/evaluator invariant table ("Re-routes never cross
  the session boundary — the handoff is the only signal") state explicitly that a skill never reads
  another skill's handoff programmatically. Recording the operator as reader (rather than
  stretching a skill into that role) keeps this table honest to what the specs actually say.
- **Row 7, the health-cache marker.** Writer and reader are **both** `evaluator` — it stamps the
  comment on one run (§5.6) and re-reads its own prior stamp on the next run against the same PR
  (§5.2, "cache-hit" path) to skip re-running the health gate when `HEAD_SHA` hasn't changed. This
  is a legitimate self-referential artifact, not a table error; `docs/specs/evaluator.md`'s own
  "Artifacts read" row for this marker says exactly this ("marker_comment_id`/`_url`/`_path`/`_bytes`
  or `marker_comment_present: false`, carried on the same `GATHER_PR` call").
- **Row 11, config marker blocks.** Writer is `setup` alone (`docs/specs/setup.md`: "setup is their
  single write path and reconciles each to canonical form on every run"); readers are `resolver`,
  `evaluator`, `drafter`, and `planner`, per the brief's own stated set — confirmed against each of
  those four specs' own "Artifacts read" sections above rather than assumed.
- **Row 12, `epic/<N>-<slug>` naming.** Writer is `resolver` (it creates the branch, both on
  bootstrap and via later rebase/merge rectification); readers are `resolver` (rediscovering the
  branch on every subsequent run against the same epic) and `evaluator` (classifying a PR's shape
  from `headRefName`/`baseRefName` matching the pattern). No other skill in the nine specs reads or
  writes this naming convention.

## 4. Fan-out note

S1 was produced by a **fan-out**: seven per-skill extraction passes (one Sonnet/high implementor
session per assigned `skills/<v1-dir>/SKILL.md` + its `references/`, run against the shared S1 brief
and this step's spec-schema template) each independently authored their assigned
`docs/specs/<skill>.md` file(s) — nine spec files in total, since one pass covered more than one
skill — followed by **this consolidation pass**, which produced `baseline.md` (this file) and every
file under `examples/` by reading all nine already-written specs plus the underlying v1 source files
directly, rather than re-deriving the per-skill content from scratch. This provenance matters for a
future reader: the per-skill specs and this consolidation file were authored in separate sessions
with separate context windows, so a discrepancy between a spec's prose and this file's
cross-reference table is a fan-out-seam bug to fix in whichever file is wrong — not evidence that
one of the nine specs is more authoritative than the other by construction. The DoD's "adversarial
re-read against its source `SKILL.md`" step closes exactly this class of seam.
