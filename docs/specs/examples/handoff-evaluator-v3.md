# Example — worked `## Handoff` (evaluator, v3 workspace model)

> Artifact: the evaluator's standard-terminal `## Handoff` rendering under the v3 operator-owned
> workspace model (workspace-open / workspace-close). **Supersedes**
> [`handoff-evaluator.md`](handoff-evaluator.md) as the byte-compatibility pin
> (`tests/test_evaluator_routing.py`); the v1 capture stays in place, unedited, as the frozen v2
> historical record. Source: `skills/evaluator/references/handoff-renderings.md`
> ("Standard PR clean merged — terminal."), quoted verbatim.

```
## Handoff

**Issue:** #142 — Add CSV export · closed · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · merged · base main · review: APPROVE · health: ✅ at abc1234 · merge: squash → main@def5678
**Cleanup:** scratch dir purged; worktree retained — release with workspace-close

**Next:** pipeline terminal — release the workspace:

    /github-pipeline:workspace-close 142-add-csv-export

**Why:** the PR satisfied every dimension cleanly and merged into main. The issue is closed by GitHub's auto-close; no follow-up skill is required for this issue.
```

The v3 deltas from the superseded capture, both deliberate: the `Cleanup:` value records that the
worktree is **retained** (the evaluator runs inside it and never removes its own checkout), and the
terminal fence carries the one housekeeping command — `/github-pipeline:workspace-close <branch>` —
instead of the bare `(terminal — no follow-up skill)` literal (which remains the drafter's
question-terminal form). Everything else — the Issue/PR lines, the closed-set markers, the `Why:` —
is unchanged from the v2 shape.
