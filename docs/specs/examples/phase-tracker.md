# Example — `## Phase tracker` PR-body section (worked instance)

> Artifact: the `## Phase tracker` section on multi-phase issues (prd.md §7, row 8).
> Source: `skills/github-issue-resolver/SKILL.md:900-905` (the fresh-PR-open path, "Multi-phase
> issues open as draft and carry a `## Phase tracker` block").
> This is a **worked instance** (the resolver's own worked example of a freshly-opened multi-phase
> PR body, mid-way through a 4-phase plan) rather than an abstract template — the source itself
> presents it as one. In the source it is nested 4 spaces deep inside a bullet list; the content
> below is that same fenced block's interior, captured verbatim with the incidental list-nesting
> indent stripped (the fence markers themselves carried no content of their own beyond the
> indentation).

```
## Phase tracker
- [x] Phase 1 — substrate (commit abc1234)
- [ ] Phase 2 — harness
- [ ] Phase 2-measurement (operator)
- [ ] Phase 3 — decision write-up
```

Added to the PR body at fresh-PR-open for multi-phase issues (`SKILL.md:898`), mirroring the plan's
`## Phases`, with the phase just shipped already ticked (every later phase still `- [ ]`). Ticked
entries carry the code-shipping form `(commit <short-sha>)`; an eventual operator/decision-only
phase tick instead reads `(operator action <ISO-date>)` per the DoD-annotation forms
(`skills/_shared/dod-annotations.md`). The tracker is updated via `gh pr edit` on every subsequent
phase push (`SKILL.md:866,908`) and is the **primary routing signal** the resolver reads on
re-entry to decide which phase to ship next — the issue-body DoD ticks are a downstream projection
of it, never read for routing (`SKILL.md:1046`).
