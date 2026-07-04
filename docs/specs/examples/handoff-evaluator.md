# Example — worked `## Handoff` (evaluator)

> Artifact: one worked `## Handoff` sample for the pipeline skill `github-pr-evaluator`
> (prd.md §7, row 10 — schema owned by `skills/_shared/handoff-format.md`; this is the evaluator's
> worked rendering).
> Source: `skills/github-pr-evaluator/references/handoff-renderings.md:24-34` ("Standard PR clean
> merged — terminal."), quoted verbatim.

```
## Handoff

**Issue:** #142 — Add CSV export · closed · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · merged · base main · review: APPROVE · health: ✅ at abc1234 · merge: squash → main@def5678
**Cleanup:** worktree removed; teardown ran; scratch dir purged

**Next:** (terminal — no follow-up skill)

**Why:** the PR satisfied every dimension cleanly and merged into main. The issue is closed by GitHub's auto-close; no follow-up skill is required for this issue.
```

This is the evaluator's terminal clean-exit shape — a standard PR merged with a clean APPROVE, the
pipeline ending here since the issue closes automatically. `review: APPROVE` is the `auto`-policy
shape (§12a); under the default `ask` policy the same terminal shape instead carries
`review: APPROVE (operator)` after the operator approved at the §12.0 gate — the merge / Cleanup /
terminal lines are identical either way. `Cleanup:` is evaluator-only and appears only after a
merge has run (§14's worktree teardown / removal / scratch-purge sequence).
