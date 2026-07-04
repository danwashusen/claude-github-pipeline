# Example — worked `## Handoff` (drafter)

> Artifact: one worked `## Handoff` sample for the pipeline skill `github-issue-drafter`
> (prd.md §7, row 10 — schema owned by `skills/_shared/handoff-format.md`; this is the drafter's
> worked rendering).
> Source: `skills/github-issue-drafter/references/handoff-renderings.md:9-19` ("Single issue filed
> (the common case)."), quoted verbatim.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✗

**Next:** plan the implementation in a fresh session.

    /github-pipeline:github-issue-planner #142

**Why:** the planner will research the approach, ground it in docs + codebase precedent, post a verified `<!-- implementation-plan:v1 -->` comment, and lock the decisions the resolver needs.
```

This is the drafter's most common clean-exit shape — a single non-Epic, non-question issue filed
with no open questions attached — forwarding to the planner. The drafter's `plan: ✗` marker is
always present here since the drafter never posts a plan itself; other renderings in the same file
add an `Open questions:` line, an Epic/`Stories:` shape, or the terminal question-issue shape.
