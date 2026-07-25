# Example — worked `## Handoff` (resolver)

> Artifact: one worked `## Handoff` sample for the pipeline skill `github-issue-resolver`
> (prd.md §7, row 10 — schema owned by `skills/_shared/handoff-format.md`; this is the resolver's
> worked rendering).
> Source: `skills/github-issue-resolver/references/handoff-renderings.md:11-22` ("Forward — standard
> or story PR opened / updated"), quoted verbatim.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · open · base main · review: not run · health: not run · merge: not run

**Next:** evaluate the PR in a fresh session.

    /github-pipeline:github-pr-evaluator #287

**Why:** the evaluator runs the branch-health gate, checks the diff against the issue's acceptance criteria + the plan's locked decisions, posts a formal review, and on a clean APPROVE auto-merges (standard / story PRs) or asks for the merge mode (Epic integration).
```

This is the resolver's default code-change outcome — a standard or story PR opened or updated,
forwarding to the evaluator. For a story PR under an open epic, the `Issue:` line is replaced with
`Story:` and an `Epic:` line is added, per the shared handoff schema's Epic-variant rules. The
`review:`/`health:`/`merge:` markers on the `PR:` line are all `not run` here because the resolver
never runs the evaluator's checks itself — those fields populate only once the evaluator has acted.
