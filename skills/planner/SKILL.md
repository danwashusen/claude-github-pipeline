---
name: planner
model: opus
effort: xhigh
description: Plan *how* to build an already-filed GitHub issue (or an entire Epic and its stories) before any code is written, and post a durable, verified implementation plan onto the issue. A specialized multi-step workflow that writes to GitHub — not a quick inline answer: it researches the approach, grounds every decision in codebase precedent and the project docs (`docs/prd.md`, `docs/architecture.md`, `docs/constitution.md`, `CLAUDE.md`, plus any the repo provides), surfaces deviations for the user to approve, optionally ingests updated external docs, validates the plan with an isolated review sub-agent, then posts it as an `<!-- implementation-plan:v1 -->` comment. It is the planning step **between** the drafter (files the issue) and the resolver (writes the code). Trigger whenever someone, referencing an issue number, wants the design / approach / architecture / layering / file-level changes / test strategy / sequencing settled and verified up front — "develop an implementation plan for #N", "work out the layering and file changes for #N", "how should we implement/build #N — figure out the design first", "before anyone writes code for #N, write the approach up on the issue", "plan this epic and its stories", or revising a stale plan ("update the plan on #N", "re-plan #N against the new docs"). Treat "implement", "build", or "step-by-step" as planning when the goal is settling strategy ahead of coding. Do NOT use for: filing a new issue (that's the drafter), writing or fixing the code (that's the resolver), reviewing a diff or PR or choosing a merge strategy (that's the evaluator), or answering a documentation question.
---

# planner — router

The design stage of the pipeline: a filed issue in → a verified, durable `<!-- implementation-plan:v1 -->`
comment (locking approach, layer assignments, file-level changes, data-model impact, test strategy,
sequencing) plus a `## Handoff` out. One planning attempt, one session; a fresh session on every
re-entry (nothing survives between runs except what is persisted to GitHub). Read this router, run
prep, route to exactly one playbook, then hand off. Scripts own the mechanical work; your judgment is
the classification, the grounding, the gates, the drafting, the review verdicts, and the handoff `Why:`.

## 1. Prep

Assemble the entire starting state in **one** call — `<issue>` from the user, a URL, or the branch:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/prep_planner.py <issue> <owner/repo>
```

It returns one JSON **facts block** (`architecture.md §4`): `target` (number/title/state/labels/
`blocked_by`/`blocking`), `vector` (`type` × `mode` × `plan_ref_row`), `suggested_playbook`, `plan_ref`
(a **bare** branch name), `plan` (present/SHA/comment-id/url — a present plan is the **revise**
trigger), `research` (dossier present + staged path), `grounding_docs` (present at `plan_ref`),
`open_questions` + `open_question_candidates` (the Bug (a) tracker search), `read_workspaces.grounding`
(the ONE read workspace this skill gets — detached at `plan_ref`, its `sha` the footer records),
`epic`/`story` (stories + state; parent epic + plan + delivery log), `revise` (prior-plan SHA vs
grounding SHA + any open PR's `## Phase tracker`), `sections` (spilled issue-body/thread/plan-marker
paths), and `attention`. Consume every fact as **data** — never re-derive the type, the mode, the
`plan_ref`, the row, or the tracker candidates in prose; prep already did.

**Decision card rule.** If prep exits with `status: needs_decision`, render its `decision` as one
`AskUserQuestion` card (per [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md)), act on
the answer, and re-run prep (`--refresh` for volatile facts). This is the single universal handler for
every closed-set code (`AUTH_REQUIRED`, `MARKER_AMBIGUOUS`, `ROOT_*`, `AMBIGUOUS`, …).

**Newly-detected OQ lookup.** When grounding surfaces an open question the issue body does **not**
already record (so prep's body-driven `open_question_candidates` never searched it), run the tracker
de-dup search before recording it `(not filed)` — one authorized call, never a raw `gh issue list`:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/prep_planner.py <issue> <owner/repo> --oq-query "<OQ topic>"
```

## 2. Route

Prep proposes `suggested_playbook`; confirm it against this table, keyed on `vector`. Read **exactly
one** playbook.

| `vector` | Playbook | Flow |
|---|---|---|
| `type: story` + open parent epic (any `mode`) | `playbooks/story-jit.md` | just-in-time story plan against epic HEAD; bootstraps the epic plan inline when absent |
| `mode: revise` (standalone issue or epic) | `playbooks/revise.md` | reconcile old-vs-new plan + projected DoD; SOFT/HARD gate; `## Predecessor` |
| `type: epic` (fresh) | `playbooks/epic.md` | epic-level plan (`## Story breakdown`/`## Story contracts`/`## Integration strategy`); stop before per-story fan-out |
| everything else fresh (`type: standard`, or a story with no open parent epic) | `playbooks/single.md` | single-issue plan; `## Phases` when multi-phase |

Every playbook opens by reading the shared spine `playbooks/plan-spine.md` (S1–S8, classify through
persist). The routed playbook supplies only what **differs in actions**: the schema sections it fills,
the reviewer dimension set it passes, its pre-draft reconnaissance, and its handoff shape. Type
differences the spine consumes (`plan_ref`, the dimension set, which schema sections, `off-ramp` —
whether the seam gate offers the epic off-ramp) are **facts / values**, never branches.

**Override rule** (`architecture.md §5`): honor `suggested_playbook` unless the thread carries evidence
the script could not see (e.g. the thread supersedes the labels' type). State the reason when you
override. Do **not** interleave type branches inside a playbook body — the route *is* the branch; one
route per session.

## 3. Invariants

Universal across every route:

- **Grounding is read-only, one workspace.** The planner never gets a work workspace and writes no
  code (`architecture.md §6`). Every doc/precedent Read/Grep/Explore targets
  `facts.read_workspaces.grounding.path` (a detached checkout at `plan_ref`) by absolute path. No
  `git show <ref>:path`, no `git grep <ref>` — the workspace is already at the right ref, and its
  `sha` is the footer's `@<short-sha>` (`architecture.md §6` "no ref arithmetic in prompts"). The
  project root is the read-only `main` vantage — never branch, commit, or stash there.
- **Marker is always the comment's first line.** Every consumer (resolver, drafter, this skill's own
  revise lookup) locates the plan by matching `<!-- implementation-plan:v1 -->` with `startswith` — any
  character before it makes the plan invisible. For a story, the `**Epic:**` backlink goes on the line
  *immediately after* the marker, never above it.
- **Footer/handoff record the branch, never elide it.** `<plan-ref>@<short-sha>` is also the resolver's
  PR base — `origin/main` for the default branch, the **bare, un-truncated** `epic/<N>-<slug>` or PR
  `headRefName` otherwise; `@<short-sha>` is `facts.read_workspaces.grounding.sha` (rendering rule in
  `plan-spine.md` S5 + [`references/handoff-renderings.md`](references/handoff-renderings.md)).
- **Staged-body writes.** Every GitHub write goes through
  `${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py` via Bash: stage the verbatim body to
  `facts.scratch` (`/tmp/gh-planner-<issue>/…`) and pass the **path**. The script verifies the
  round-trip hash, returns `body_sha256`, and gates empty bodies (`EMPTY_BODY_FILE`) — the #626/#627
  race fix. Never re-serialize a body across the prompt boundary; never hand-roll a persist/gather `gh`
  call. The planner has **no** scriptless raw-`gh` executor.
- **Successful write is self-confirming.** A zero exit with a URL *is* the confirmation; never re-read it.
- **Gates only for genuine decisions** (per [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md)):
  latest-decision-direction, external sources, the seam-disposition gate, the deviation gate, the
  decision gate, review-notes disposition, show-before-post (opt-in), revise reconciliation. Never to
  confirm a fact prep derived.
  A judgment sub-agent (the plan reviewer, an `Explore` precedent search) never calls
  `AskUserQuestion`; it returns its result to this loop, which asks.
- **A tracked open question is a human's call** — never resolved from precedent or the decision gate.
  Record it in `## Open questions`; if the whole plan is gated, re-route rather than post a hollow plan.
- **Handoff on clean exit** (§4). One `## Handoff` block ends every clean run — the seam gate's
  epic-shaped abort included (comment posted, no plan, no label); it replaces any bullet-list summary.

## 4. Handoff

Every clean run ends with a single `## Handoff` block — the only bridge to the next session. The
schema, omission rules, and closed-set state-marker vocabulary are owned by
[`../_shared/handoff-format.md`](../_shared/handoff-format.md); the planner's per-outcome shapes,
the `Grounding:` and `**Open questions:**` lines, the footer rule, and the bug-(b) composite
epic+story worked example are in [`references/handoff-renderings.md`](references/handoff-renderings.md).
**Read that reference before composing the handoff** and match the run's outcome to a shape (forward to
the resolver; epic plan → first story or drafter; just-in-time story → resolver; re-route to researcher
or answer-the-question; epic-shaped abort → drafter; revise refreshed). Fill the snapshot from data in
hand; the `Next:` action and `Why:` line are judgment. The `**Open questions:**` line renders in
**every** shape whose posted plan carries an `## Open questions` section — including a composite
epic+story session — never dropped because the structural shape matched a different example first.
Next-command skills are namespaced `/github-pipeline:<name>`. A re-route points `Next:` at another
pipeline skill but does **not** invoke it via the `Skill` tool — the handoff is the only signal; the
user runs the command in a fresh session (session-per-skill is the context-isolation choice).
