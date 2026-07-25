# Example — worked `## Handoff` (planner)

> Artifact: one worked `## Handoff` sample for the pipeline skill `github-issue-planner`
> (prd.md §7, row 10 — schema owned by `skills/_shared/handoff-format.md`; this is the planner's
> worked rendering).
> Source: `skills/github-issue-planner/references/handoff-renderings.md:11-22` ("Single-issue plan
> posted."), quoted verbatim.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓ (https://github.com/owner/repo/issues/142#issuecomment-XXXXX)
**Grounding:** read at origin/main@a1b2c3d · docs/architecture.md §3 (service layer), §7 (export pipeline); docs/constitution.md §6 (logging) · external: RFC 4180 CSV spec (fetched 2026-06-20) · full detail in the plan's ## Doc grounding

**Next:** implement the plan in a fresh session.

    /github-pipeline:github-issue-resolver #142

**Why:** the plan locks architecture, file-level changes, layer assignments, and test strategy. The resolver executes against it and opens the PR; if implementation reveals a locked decision is wrong, it will re-route back here in revise mode.
```

This is the planner's most common clean-exit shape — a single-issue plan posted, forwarding to the
resolver. `Grounding:` is planner-only and only appears on clean exits that posted a plan: it names
the `<plan-ref>@<short-sha>` the docs were read at (here `origin/main@a1b2c3d`), the project docs
cited (with §refs), and — when present — the external sources from `## External sources consulted`
(here "RFC 4180 CSV spec (fetched 2026-06-20)"). The file's other renderings compose the Epic,
story-under-epic, and Open-questions axes on top of this same base shape.
