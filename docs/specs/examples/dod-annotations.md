# Example — Definition-of-done checkbox annotations (closed set)

> Artifact: Definition-of-done checkbox annotations (prd.md §7, row 6).
> Source: `skills/_shared/dod-annotations.md:9-16` (the "Annotation shapes (closed set)" table),
> quoted verbatim.
> This is a **closed-set schema definition** — there is no single "worked instance" file since each
> annotation form appears scattered across live issue bodies; the table below (copied cell-for-cell)
> is the canonical, exhaustive enumeration every consumer (`github-issue-resolver`,
> `github-pr-evaluator`, `github-issue-planner`) parses against.

| Form | Tick state | Authored by | Meaning |
|---|---|---|---|
| `- [ ] <text>` | unticked, no annotation | — | bullet not yet shipped |
| `- [x] <text> (closed by phase <N>, commit <short-sha>)` | ticked, code-phase | resolver §9 | code-shipping phase `<N>`'s commit `<short-sha>` satisfies the bullet (per the plan's `closes-dod`) |
| `- [x] <text> (closed by phase <N>, operator action <ISO-date>)` | ticked, operator-phase | resolver §9 | operator/decision-only phase `<N>` was completed on `<ISO-date>`; bullet claimed by that phase's `closes-dod` |
| `- [x] <text> (closed by commit <short-sha>)` | ticked, single-phase fallback | resolver §9 | the plan has no `## Phases` section; the single push's commit satisfies the bullet (single-phase fallback rule) |
| `- [ ] <text> (resolver claimed phase <N>, commit <short-sha>; evaluator rejected: <one-line reason>)` | unticked with rejection annotation | evaluator §6 | the evaluator's per-phase verification judged the attributed diff fails to satisfy the bullet; **sticky veto** — the resolver respects this and does not re-tick on subsequent pushes |
| `- [ ] <text> (previously claimed by phase <N>, commit <short-sha> on closed PR #<M>)` | unticked with predecessor annotation | planner revise (HARD path) | the previous PR was closed during a re-plan that started fresh; the bullet was ticked under that closed PR but the new plan needs new work to satisfy it |

All `<short-sha>` values are 7-char (matching the `## Phase tracker` and
`_shared/handoff-format.md` conventions). `<ISO-date>` is `YYYY-MM-DD`.

## Recognition regex (informal)

`skills/_shared/dod-annotations.md:33`, quoted verbatim:

```
bullet line:  ^([ ]*)-[ ]+\[([ xX])\][ ]+(.+?)(?:[ ]+\((closed by|resolver claimed phase|previously claimed by) (.+)\))?$
```

## Who reads, who writes

`skills/_shared/dod-annotations.md:61-65`, quoted verbatim:

| Skill | Reads | Writes |
|---|---|---|
| `github-issue-resolver` | all forms (to detect rejections / predecessors before projecting) | `closed by phase / commit` ticks (projection on push, reconciliation on re-entry — never un-ticks) |
| `github-pr-evaluator` | `closed by` forms (per-phase verification input); writes `resolver claimed ... evaluator rejected: ...` on clear semantic mismatch | `resolver claimed ... evaluator rejected: ...` un-ticks (sticky vetoes) |
| `github-issue-planner` | all forms (revise-mode reconciliation reads the current body to compute the body-edit diff) | re-attribution edits during SOFT-path reconciliation; `previously claimed by ... on closed PR #<M>` un-ticks during HARD-path "Start fresh" |
