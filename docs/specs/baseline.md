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

## 5. S8 pilot retro & pattern lock

> Produced by [implementation.md](../implementation.md) step **S8** ("Pilot retro & pattern lock"),
> after the S6 evaluator prep (`prep_evaluator.py`) and the S7 evaluator cutover + parity run made
> the shared patterns concrete against exactly one skill. The audience is a later cutover author
> (S9–S19): the corrections below are already landed, so the six remaining cutovers inherit the
> corrected patterns rather than rediscovering them. S8's goal is precisely "correct the shared
> patterns **while exactly one skill uses them**."

### 5.1 Composition-API friction → the adopted lock

**Friction (S6).** The executors reached S6 with **uneven composition surfaces.** `parse.py`
exposed pure `parse_*() -> data` cores (with `run_*`/`main` as thin emit wrappers), and
`gh_gather.run(..., stream=None)` returned `(exit, envelope)` while honoring a provided stream — both
composable. But `gh_pr_gather.run`, every `workspace.py` subcommand, and `config_block.py`'s `run_*`
functions **emitted-and-exited with no returnable core**: their only way to produce a result was to
`emit_ok`/`emit_needs_decision`/`sys.stdout.write` onto real stdout. Composing them in-process from a
prep therefore meant their envelope would land on the prep's own stdout, breaking the §3 "exactly one
JSON envelope" invariant. The S6 pilot bridged this with `contextlib.redirect_stdout` into an
`io.StringIO` buffer that the prep parsed and never re-emitted — a working stopgap, but a shim every
later prep would otherwise have to re-implement.

**The lock (shipped in S8).** Every executor now exposes a **pure, non-emitting core** —
`build_*(...) -> (payload, notices, decision | None)` — and `main()`/`run_*` is a thin emit wrapper
over it. The type-level distinction the retro asked for rides in the return tuple:

- `decision is None` → success; the caller uses `payload` + `notices`.
- `decision is not None` → a `needs_decision` outcome (a `pipelib.decisions` code dict, e.g.
  `MARKER_AMBIGUOUS`, `AUTH_REQUIRED`, `ROOT_DIRTY`, `BRANCH_IN_USE`); the caller propagates it to
  its single envelope.
- a **partial-but-honest** degradation rides in `notices` (or, for `ensure --work`'s setup-hook
  failure, in the `payload` itself as `setup.succeeded: false`), distinct from a **hard error**,
  which still exits non-zero with stderr and no envelope (§3 exit-code contract — unchanged).

Files retrofitted: `scripts/gh_pr_gather.py` (`build_pr_facts`), `scripts/workspace.py` (per
subcommand: `_build_ensure_work` / `_build_ensure_read` / `_build_remove_work` / `_build_gc` /
`_build_root_status` / `_build_lint`), and `scripts/config_block.py` (`build_read` / `build_list` /
`build_upsert` / `build_remove`). `parse.py` and `gh_gather.run(stream=)` are the **reference shapes**
and were left untouched. `prep_evaluator.py` was rewired to call the new cores directly; its
`contextlib` / `io` imports and every `redirect_stdout` / `io.StringIO` capture block are removed. The
sole remaining stream use is `gh_gather.run(stream=...)`, the accepted-reference emit-through-a-stream
executor — its emit is routed to a trivial discard sink, not captured.

**Rule for S9+.** A prep composes the executor cores **directly** and acts on each core's returned
`decision` channel. **No new prep may reintroduce stdout capture** (`redirect_stdout` /
`io.StringIO` around another script's emit). Envelope output is byte-identical across the retrofit:
the S6 fixtures were untouched and `python3 tests/run.py` stays fully green.

### 5.2 Facts-schema gaps (closed pilot findings, for the record)

Two shared-layer defects the S6 pilot surfaced, both **already landed** — recorded here as
pilot findings, not open work:

- **`gh_pr_gather` `labels` omission.** v1's PR fetch referenced escalation labels but never fetched
  the PR's own `labels`, so the evaluator's escalation-label matching could never fire. v2's
  `GATHER_PR` field set adds `labels` (surfaced as a list of label-name strings on the same
  `gh pr view` call — no extra round-trip), and `prep_evaluator` carries it through to
  `target.labels`.
- **`workspace ensure --work` existing-branch bug.** The original create path checked out `main`
  (the `--base`) even when the requested branch already existed on the remote, so an evaluator
  ensuring the PR **head** branch got `main`, not the PR head. `_build_ensure_work` now picks the
  checkout source by branch existence, landing the worktree at the branch's own head, so the
  recorded `sha` fact is the head SHA, never `main`'s.

### 5.3 Playbook-granularity / router-shape confirmations (from S7)

The S7 evaluator cutover **held** the §5 routing bar and the size metrics, so they carry forward as
the validated template for the six remaining cutovers:

- **Routing bar held.** Shared spine + thin post-verdict variants, **zero PR-type conditionals** in
  the router or playbooks (no `if epic … else if story …` interleaving; a difference in *values* is a
  fact, not a branch — §5 "Parameterize before you playbook"). Router ≤150 lines and router+largest
  playbook ≤ half the v1 `SKILL.md` line count (§1's parity denominator) both met.

The §1 baseline census's recorded distinct-token count (79, frozen at S1) grew to 81 at S7 — the
evaluator cutover's own additions, with zero drops — so a downstream cutover author diffing the
census command's output against the §1 table should read that delta as expected growth, not a
stale-baseline error.

**Three S7 gate-interpretation adjudications, recorded as precedent** (they recur across the
remaining pipeline skills):

- **(a) Artifact-footer provenance string.** An emitted artifact's footer keeps the literal
  `github-pr-evaluator` provenance string. This is a **byte-compatibility contract token** (a v1
  artifact reader / cross-consumer matches it verbatim), **not** a skill name to be renamed to the
  v2 `evaluator` — the skill rename does not propagate into the persisted artifact bytes.
- **(b) Scriptless raw-`gh` executors.** `gh pr merge` and `gh pr ready --undo` are **sanctioned**
  raw-`gh` executors in `skills/`: no `gh_persist.py` op covers them (they are not body-bearing
  writes on the write path), and the behaviors they implement — merge execution and the soft-reject
  draft-flip on Needs Revision / Reject — are spec'd in `docs/specs/evaluator.md`. The §10 raw-`gh`
  validator is narrowed accordingly (see §5.4).
- **(c) `git show <end>` vs ref arithmetic.** A single-commit diff view — `git show <commit>` — is
  legitimate and permitted; only `git show <ref>:<path>` (ref-arithmetic path extraction) and
  `git grep <ref>` are banned. The §10 `git`-ref validator is narrowed to the ref-arithmetic form
  (see §5.4).

(b) and (c) are the drivers of the S8 architecture amendments (§2 pure-core pattern, §10 validator
narrowings, §12 consistency qualifier) — content-only, all `## §N` anchors stable.

### 5.4 Go/no-go (S8 box 3), recorded — not decided

The operator's decision, recorded in `docs/specs/parity/evaluator.md`'s "Go/no-go (S8 input)" block,
is **Accepted — go.** S8 only *records* it here; it does not make it. The three go criteria and their
status:

1. **S7 parity recorded with zero unexplained divergences — met.** All four scenarios PASS
   (1 standard approve+merge, 2 story merge / delivery-log + epic checkbox, 3 red-CI rejection,
   4 `ask`-policy merge gate + operator override). Every recorded divergence traces to a PRD §
   (§8.3 / §9.1 / §9.2), a GitHub behavior, the deliberate v1→v2 rename, free prose within the shared
   schema, or a run-time environment substitution — none unexplained.
2. **Architecture amendments landed — met.** The §2 / §10 / §12 amendments (§5.3 (b)+(c) above) are
   applied, anchors stable.
3. **Validators + census green — met.** compileall, `tests/run.py`, shellcheck, and the contract-token
   census are green; the orchestrator re-runs them at acceptance.

**No blocking finding.**

## 6. S20 final census — the v2-only re-baseline

> Produced by [implementation.md](../implementation.md) step **S20** ("v1 removal & repo truth"),
> after the eight skill cutovers and the removal of every v1 surface. §2 above stays **frozen** as
> the S1 record; this section is the diff against it and the **new going-forward baseline**. The
> S19 reviewer's note is the reason it exists: the pre-removal count (88) double-counted the
> coexisting v1 and v2 trees, so only a v2-only set is a usable reference for a future editor.

### 6.1 Command

`agents/` no longer exists (the v1 executor sub-agent prompt was its only occupant), so the census
scope narrows to `skills/` — otherwise the command is unchanged from §2:

```
grep -roE '<!-- [a-z0-9:-]+ -->|§P?[0-9]+(\.[0-9]+)?|GATHER_[A-Z]+|PERSIST_[A-Z]+|github-pipeline:[a-z-]+' skills/ | sed 's/^[^:]*://' | sort -u | wc -l
```

Output: **44** distinct contract tokens (S1 baseline: 79).

### 6.2 The v2-only baseline (token — total occurrences)

This is what a future edit diffs against. A count drop is expected only when that edit deliberately
removes the last user of a token; a **token** disappearing is the thing to explain.

```
     4  <!-- claude-code-stack-profile -->        11  §1
     3  <!-- drafter-open-question-markers -->     2  §10
    14  <!-- epic-delivery-log:v1 -->              1  §10.4
     1  <!-- github-pipeline-config -->           13  §10.6
    19  <!-- implementation-plan:v1 -->            3  §12
     5  <!-- issue-research:v1 -->                 8  §2
     3  <!-- issue-resolver-canonical-suite -->   23  §3
     1  <!-- issue-resolver-fast-checks -->        1  §3.2
     3  <!-- issue-resolver-test-target -->       19  §4
     6  <!-- open-question-links:v1 -->           11  §5
     3  <!-- pr-evaluator-escalation-labels -->    4  §5.5
     4  <!-- pr-evaluator-health-cache:v1 -->     10  §6
     1  <!-- pr-evaluator-merge-policy -->         3  §6.5
     4  <!-- pr-evaluator-static-checks -->       10  §7
     6  <!-- pr-evaluator-test-target -->         32  §8
    10  <!-- question-decision:v1 -->              2  §8.1
     3  <!-- worktree-setup -->                    9  §8.2
     4  <!-- worktree-teardown -->                 6  §9
     1  github-pipeline:doc-reviewer
    13  github-pipeline:drafter
     7  github-pipeline:evaluator
    27  github-pipeline:planner
     3  github-pipeline:question-resolver
     3  github-pipeline:question-sweep
     2  github-pipeline:researcher
    31  github-pipeline:resolver
```

**All 18 `<!-- … -->` markers from §2's "must survive verbatim" category are present** — every
`:v1` durable marker (`implementation-plan`, `issue-research`, `epic-delivery-log`,
`question-decision`, `open-question-links`, `pr-evaluator-health-cache`) and every consuming-repo
config-block marker (`issue-resolver-*`, `pr-evaluator-*`, `drafter-open-question-markers`,
`worktree-setup`/`-teardown`, `claude-code-stack-profile`, `github-pipeline-config`). The
compatibility contract ([prd.md §7](../prd.md)) is intact.

### 6.3 The diff against S1's 79

79 − 44 dropped + 9 added = 44. Every dropped token is on the deliberate-retirement list below;
the additions are the v2 skill-invocation namespace and three new anchors.

**Added (9):** `github-pipeline:drafter`, `github-pipeline:evaluator`, `github-pipeline:planner`,
`github-pipeline:question-sweep`, `github-pipeline:researcher`, `github-pipeline:resolver` (the
renamed pipeline stages + the renamed sweep — `github-pipeline:doc-reviewer` and
`github-pipeline:question-resolver` were already in the S1 set, their names unchanged); and `§6.5`,
`§8.1`, `§8.2` (the planner spine's decision gate, and prd.md §8.1/§8.2 citations in the standalone
tools' landing-gate prose).

**Dropped (44), by class — each on §2's "v1-only tokens expected to retire" list:**

| # | Class | Tokens | Retired at | Why it is not a loss |
|---:|---|---|---|---|
| 1 | v1 executor op names | `GATHER_EPIC`, `GATHER_ISSUE`, `GATHER_PR`, `PERSIST_BODY`, `PERSIST_CLOSE`, `PERSIST_COMMENT`, `PERSIST_CREATE`, `PERSIST_ISSUE`, `PERSIST_LINK`, `PERSIST_REOPEN` (10) | the executor sub-agent + the v1 skill dirs at S20; the last citations (in `_shared/handoff-format.md`, `epic-delivery-log.md`, `open-question-links.md`) were rewritten to the script invocations that replaced them | The ops are gone as a *protocol*: skills call `gh_gather.py` / `gh_pr_gather.py` / `gh_persist.py` directly ([architecture.md §7](../architecture.md)'s rule-by-rule mapping; [prd.md §9.1](../prd.md) "no intermediary agent"). |
| 2 | v1 skill-namespace strings | `github-pipeline:github-issue-drafter`, `…-researcher`, `…-planner`, `…-resolver`, `github-pipeline:github-pr-evaluator`, `github-pipeline:open-questions`, `github-pipeline:github-ops` (7) | each at its own cutover (S15/S16/S13/S10/S7/S18) — the last two stragglers (a drafter handoff pointer and a drafter playbook pointer at `github-pipeline:open-questions`) at S20 | Replaced 1:1 by the six added v2 names above. The `github-ops` namespace has no successor by design — there is no executor sub-agent. |
| 3 | resolver-local `§P` IDs | `§P1`, `§P2`, `§P3`, `§P3.1`, `§P3.2`, `§P3.3`, `§P3.4`, `§P4`, `§P5`, `§P6` (10) | S10 for the resolver itself; the last citation (`_shared/follow-up-filing.md`'s `§P5`) at S20 | The scheme existed because the v1 resolver was one 1169-line reorder-prone file ([architecture.md §9](../architecture.md): "the resolver-local `§P-ID` scheme is retired"). The router + playbook split removed the need; no v2 skill defines or cites one, and the per-skill grep gates now *forbid* `§P[0-9]`. |
| 4 | v1 skill-internal `§N` anchors | `§4.5`, `§4.6`, `§4.7`, `§5.1`, `§5.2`, `§5.3`, `§5.4`, `§5.6`, `§7.5`, `§10.3`, `§10.7`, `§11`, `§12.0`, `§13`, `§14`, `§15` (16) | with the v1 `SKILL.md`/`references` files that defined them (S7/S10/S13/S15/S16/S18); the handful cited from surviving `_shared` and `setup/references` files were retargeted at S20 | These were the **v1** resolver/evaluator/planner section numbers. §2's reading guide flags a bare-`§N` drop as "a cross-reference break to investigate" — the investigation is recorded here: every one was a citation *into a v1 skill body*, and each surviving citation was rewritten to name the behavior instead of the number (e.g. `_shared/epic-delivery-log.md`'s "(§13)" → "when it merges a story PR"; `_shared/handoff-format.md`'s "§14's worktree teardown" → "the post-merge workspace teardown … sequence"; `block-authoring.md`'s "the evaluator's merge step (its §12) … the §12.0 operator decision gate" → "its operator decision gate"). Zero dangling anchors remain. |
| 5 | Legacy config marker (**form change, not a retirement**) | `<!-- pr-evaluator-health-checks -->` (1) | — | The marker **still exists** and is still handled: `skills/setup/playbooks/setup-flow.md` and `skills/setup/references/block-authoring.md` name it as the bare marker argument the split/migration reads and removes (`read pr-evaluator-health-checks` … `remove pr-evaluator-health-checks`), and `prep_evaluator.py` / `prep_resolver.py` still read it as the legacy fallback. The census regex only matches the `<!-- … -->` *comment* form, which the v2 prose no longer needs to spell. Fixture-tested by `tests/test_setup_routing.py::LegacyHealthChecksMigrationTests` and `tests/test_prep_setup.py::…test_legacy_health_checks_detected`. |

Classes 1–4 are exactly §2's three expected-retirement buckets (with class 4 the "investigate"
bucket, investigated). Class 5 is the one row a reviewer should read carefully: it is a
**presentation** change in the prompt prose, verified against live behavior by the two test suites
named.

### 6.4 Surviving v1-labelled gate names (deliberate, not a miss)

The v2 resolver spine keeps `§8` (the pre-push verification gate) and `§10.6` (the review-loop
pre-push gate) as **labels carried from v1**, cited by `references/common-pitfalls.md`,
`retry-ladder.md`, `epic-flow.md`, and `test-selection-sub-agent.md`. That was an S10 decision
(`common-pitfalls.md`: "references name the v2 flow points"), not an oversight — the labels name
gates that exist in `playbooks/resolve-spine.md`. They are counted in the v2 baseline above.

### 6.5 Going forward

§2 (79 tokens over `skills/` + `agents/`) is the **historical** S1 baseline and is never re-run
green again — `agents/` is gone and no v1 dir exists. **§6.2 (44 tokens over `skills/`) is the
baseline every future edit diffs against.** The zero-old-name property is additionally committed as
a test (`tests/test_v1_retirement.py`), so a stale v1 reference fails the offline suite rather than
waiting for someone to re-run a grep.
