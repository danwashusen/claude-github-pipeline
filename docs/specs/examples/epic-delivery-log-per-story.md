# Example — `<!-- epic-delivery-log:v2:story:<N> -->` per-story delivery-log entry (schema definition)

> Artifact: one epic-delivery-log **entry** comment (prd.md §7). Supersedes the single-comment shape
> for everything written from 4.8.0 onward; `docs/specs/examples/epic-delivery-log.md` stays unedited
> as the record of the shape that preceded it, which is still read forever as the legacy tier.
> Source: `skills/_shared/epic-delivery-log.md`, § "Format" — the single source of truth for this
> artifact's format, per that file's own header. Cited by **section anchor, not line numbers**: the
> older example pinned `:18-23`, which any insertion above line 18 silently rots, and a frozen record
> must not carry a citation that decays.
> This is a **schema/template definition**, not a worked instance — the canonical example is this
> template block, verbatim, exactly as the evaluator (sole writer) posts it and the planner (sole
> reader) parses it.

```
<!-- epic-delivery-log:v2:story:<N> -->
- #<story> — delivered: <actual contract shape, as merged> @ `<commit-sha>` (PR #<M>, merged <ISO-8601 date>)
```

Why the shape changed (#41): a single accumulating comment is bounded by GitHub's 65,536-character
body cap, which an epic reaches by construction — one observed epic held 37,478 characters across 9
entries with 14 stories still open. Past the cap the write returns `BODY_TOO_LONG` and no merge can be
recorded at all. One comment per story makes growth O(1) per artifact instead of O(n).

Two properties of this template are load-bearing and must not be "tidied":

- **`<N>` in the marker is the story's issue number**, and it is what preserves the
  one-marker-one-comment invariant every reader relies on. Two comments bearing the same
  `:story:<N>` marker are a genuine duplicate (`MARKER_AMBIGUOUS`); a marker shared across entries
  would make "N entries" and "one entry duplicated N times" indistinguishable. `:story:15 -->` is not
  a prefix of `:story:150 -->` — the trailing ` -->` terminates the match.
- **The entry line is byte-identical to the legacy tier's**, so one parser serves both tiers and a
  tier migration never becomes a parser migration. There is deliberately no per-comment epic header:
  repeated on every comment it would be N copies of a fact the epic issue already states.
