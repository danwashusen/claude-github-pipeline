---
name: workspace-open
disable-model-invocation: true
description: Open the work workspace for a GitHub issue — create or adopt the issue's linked branch (the native "create a branch for this issue"), create or reuse its worktree under `.worktrees/`, run the repo's worktree-setup hooks, and print the path to start the next session in. The resolver and evaluator sessions run INSIDE this worktree and only assert it. Explicit-invocation only — run it as `/github-pipeline:workspace-open <issue>`. Not a pipeline stage; it never plans or resolves anything itself.
---

# workspace-open — router

The operator-side opener of the v3 workspace lifecycle: **open → work → evaluate → close**. One
call derives the branch (linked-first — an existing GitHub-linked branch is adopted verbatim,
never re-derived), links it to the issue, creates or reuses `.worktrees/<branch>` under the main
checkout, and runs the consuming repo's `<!-- worktree-setup -->` hooks. It ends with a plain
summary telling the operator **where to start the next session** — it never proceeds into
planning or resolution itself.

## 1. Prep

One call (resolve the repo first — `gh repo view --json nameWithOwner -q '.nameWithOwner'`);
the call **is** the action:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/prep_workspace_open.py <issue> <owner/repo> [--root <path>]
```

Returns one **facts block** (`architecture.md §4`): `target`, `vector` (`type` / `mode` /
`prior_pr_row`, plus `gate` on a gated row), `branch` (`name` / `base` /
`source: computed|linked|pr-head|epic-discovered|epic-bootstrap` / `collided_with`), `link`
(`attempted` / `created` / `existing`), `plan.present`, `workspace` (the create/reuse receipt:
`path` / `branch` / `base_ref` / `sha` / `reused` / `dirty` / `unpushed_commits` / `setup`),
`attention`, `notices`. Consume as **data**. A `needs_decision` (`AUTH_REQUIRED`,
`TARGET_IS_PR`, `MARKER_AMBIGUOUS`, `ROOT_NOT_ON_MAIN` / `ROOT_DIRTY` / `ROOT_DIVERGED`,
`BRANCH_IN_USE`, `AMBIGUOUS` on multiple linked branches) — render it as one `AskUserQuestion`
card and stop.

## 2. Route — one linear flow

No mode fork: open (the prep call) → render the receipt → summary with the next step. A **gated
row** (`vector.gate` — a foreign open/draft PR) is a fact gate inside the one flow, not a route:
prep created nothing; render the gate card verbatim and stop on "wait"-shaped answers.

| Facts | Playbook |
|---|---|
| any open run | [`playbooks/open-flow.md`](playbooks/open-flow.md) |

## 3. Invariants

- **Operator-invoked only; opens, never proceeds.** This tool ends at the summary — it never
  plans, resolves, or evaluates, and never invokes another skill.
- **No tracked-file edits, no doc writes.** The only GitHub write is the issue↔branch link the
  prep's `gh issue develop` creates (script-internal — never run `gh issue develop` yourself).
  Where linking is unsupported (`ISSUE_LINK_UNSUPPORTED` notice), the branch exists locally only
  — say so in the summary.
- **Setup-hook failure is fail-fast and reported verbatim** (`workspace.setup.first_failure`):
  the worktree exists but is not ready — the summary must lead with that, not bury it.
- **Faithful reporting.** `reused: true` means the worktree already existed (a re-open is safe
  and idempotent); `collided_with` means the fresh name took a `-vN` suffix — both are stated
  plainly, never silently.

## 4. Summary — not a `## Handoff`

End with a plain **summary**: the branch (and its `source`), the link outcome, the worktree path,
hook results — then the copy-paste next step. **Next-step routing (plan-before-open):**

- `plan.present` true → "start the next session **in `<workspace.path>`** and run
  `/github-pipeline:resolver #<issue>`".
- `plan.present` false → "no implementation plan exists yet — run `/github-pipeline:planner
  #<issue>` from a `main` checkout (standard issue) or the parent-epic worktree (story) first,
  then start the resolver session in `<workspace.path>`". Never route the operator into the
  just-opened worktree to *plan*.
