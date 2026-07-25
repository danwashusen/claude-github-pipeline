# Example — `<!-- epic-delivery-log:v1 -->` delivery log (schema definition)

> Artifact: the `<!-- epic-delivery-log:v1 -->` epic delivery log comment (prd.md §7, row 3).
> Source: `skills/_shared/epic-delivery-log.md:18-23` (the "Format" section) — the single source of
> truth for this artifact's format, per that file's own header.
> This is a **schema/template definition**, not a worked instance — the canonical example is this
> template block, verbatim, exactly as `github-pr-evaluator` (sole writer) posts it and
> `github-issue-planner` (sole reader) parses it.

```
<!-- epic-delivery-log:v1 -->
**Epic delivery log** — #<epic-N> <title>
- #<story> — delivered: <actual contract shape, as merged> @ `<commit-sha>` (PR #<M>, merged <ISO-8601 date>)
- ...
```

One line per shipped story, in merge order. `<actual contract shape>` is the public surface the
story actually merged (the new/changed type, service, or API signature) — recorded from the merged
diff, **not** copied from the plan's pinned contract, so a divergence between pinned and shipped is
visible here (`skills/_shared/epic-delivery-log.md:25`).

## Corroborating citation from the writer's own spec

`skills/github-pr-evaluator/SKILL.md:737` describes the same per-line shape in its own prose
(paraphrased there, not fenced — the schema authority is `_shared/epic-delivery-log.md` above):
"one `- #<story> — delivered: <actual shape> @ `<commit-sha>` (PR #<pr-number>, merged <ISO-date>)`
line per shipped story… Idempotent: if a `#<story>` line already exists (a re-run), update it in
place rather than duplicating." This confirms the writer (`github-pr-evaluator`) and the shared
contract agree on the format and the idempotency rule.
