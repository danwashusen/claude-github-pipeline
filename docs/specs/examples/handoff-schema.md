# Example — `## Handoff` schema + closed-set state markers (schema definition)

> Artifact: the `## Handoff` schema + closed-set state markers (prd.md §7, row 10).
> Source: `skills/_shared/handoff-format.md:9-21` (the "Schema" section's fenced block) and
> `:45-54` (the "State-marker vocabulary (closed sets)" table), both quoted verbatim.
> This is a **schema/template definition** — the five worked per-skill handoff samples this task
> also produces (`handoff-drafter.md`, `handoff-researcher.md`, `handoff-planner.md`,
> `handoff-resolver.md`, `handoff-evaluator.md`) are the corresponding worked instances.

## Schema

```
## Handoff

**Issue:** #N — <title> · <state> · <type> · research: <✓ | ✗ | stale> · plan: <✓ | ✗ | stale>
**Grounding:** read at <plan-ref>@<short-sha> · <docs the plan was built on, with §refs> · external: <sources> · full detail in the plan's ## Doc grounding
**PR:** #M — <title> · <state> · base <ref> · review: <verdict | not run> · health: <✅/❌ at <short-sha> | not run> · merge: <strategy → <ref>@<short-sha> | skipped (<reason>) | not run>
**Cleanup:** <one-line worktree / branch / scratch summary>

**Next:** <one-line description of what the fresh session will do>.

    /<next-skill> [<args>]

**Why:** <one line — for forward routes, what the next session will accomplish; for re-routes, the specific finding that triggered the regression and what the user should confirm>
```

The block is always present on a clean exit. Lines are omitted (not blanked, not stubbed) when
they don't apply.

## State-marker vocabulary (closed sets)

Use these exact words. Don't invent synonyms.

| Field | Values |
|---|---|
| Issue `state` | `open`, `closed` |
| Issue `type` | `bug`, `feature`, `incomplete`, `story`, `epic`, `question` |
| Issue `research` | `✓` (dossier posted), `✗` (none / judged not needed), `stale` (posted but superseded by an issue or source change) |
| Issue `plan` | `✓` (posted), `✗` (none), `stale` (posted but superseded) |
| PR `state` | `draft`, `open`, `merged`, `closed` |
| PR `review` | `APPROVE`, `COMMENT (soft-reject)`, `APPROVE (operator)`, `COMMENT (operator: needs-revision)`, `COMMENT (operator: reject)`, `not run` |
| PR `health` | `✅ at <short-sha>`, `❌ at <short-sha>`, `not run` |
| PR `merge` | `squash → <ref>@<short-sha>`, `merge → <ref>@<short-sha>`, `skipped (<reason>)`, `not run` |

`<short-sha>` is a 7-character hex prefix. `<ref>` is the merge target (`main` for standard PRs and
Epic integration PRs, `epic/<N>-<slug>` for story PRs).

## Terminal-ending shape

`skills/_shared/handoff-format.md:90-93`, quoted verbatim — some clean exits end the pipeline for
this issue; drop the fenced command block and keep everything else:

```
**Next:** (terminal — no follow-up skill)

**Why:** the PR satisfied every dimension cleanly and merged into main. The issue is closed by GitHub's auto-close; no follow-up skill is required for this issue.
```
