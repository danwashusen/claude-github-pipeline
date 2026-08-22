# Epic delivery-log rendering — `<!-- epic-delivery-log:v1 -->`

The story route's Action 3 stages and posts this comment on the parent epic. It is a **prd.md
§7-frozen artifact**; its format and the writer/reader ownership are owned by
[`../../_shared/epic-delivery-log.md`](../../_shared/epic-delivery-log.md) — this rendering is
byte-compatible with that contract and the S1 baseline
(`docs/specs/examples/epic-delivery-log.md`). Render exactly this shape, stage it to
`<facts.scratch>/delivery-log.md`, and post it via `gh_persist.py comment … issue <epic>` (with
`--delete-marker-id` when a prior log comment exists). The marker `<!-- epic-delivery-log:v1 -->` is
always the **first line** (every reader locates it with a `startswith` match — anything before it
makes the log undiscoverable).

```
<!-- epic-delivery-log:v1 -->
**Epic delivery log** — #<epic-N> <title>
- #<story> — delivered: <actual contract shape, as merged> @ `<commit-sha>` (PR #<M>, merged <ISO-8601 date>)
- ...
```

Rules (from the frozen contract):
- **One line per shipped story, in merge order.** `<actual contract shape>` is the public surface the
  story actually merged (the new/changed type, service, or API signature) — recorded from the **merged
  diff**, not copied from the plan's pinned contract, so a divergence between pinned and shipped is
  visible here.
- **Idempotent.** If a `#<story>` line already exists (a re-run), update it in place rather than
  duplicating. There is no in-place edit op — re-stage the full body and repost (plain create when the
  comment is absent; delete-and-repost via `--delete-marker-id` when it exists). The prior comment's
  body and its numeric id both come from `facts.epic.delivery_log` — the id `--delete-marker-id` takes
  is the REST comment id, never a thread comment's GraphQL node id (#34).
- The evaluator is the **sole writer**; the planner is the sole reader. Recording every story here —
  including the last — is what keeps the log complete for the planner's just-in-time story planning.
