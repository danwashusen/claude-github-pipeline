# DoD checkbox annotations — shared reference

Three GitHub-pipeline skills read and write annotations on the issue body's `## Definition of done` checkboxes: `github-issue-resolver` projects them as each phase ships (its §9 "DoD projection rule"), `github-pr-evaluator` verifies them at PR-readiness and un-ticks clear semantic mismatches (its §6 per-phase verification), and `github-issue-planner` reconciles them during revise mode (its "Re-plan reconciliation" subsection). This file is the single source of truth for the annotation shapes, parser, and invariants. The skills reference this file rather than restating the parser inline.

## Annotation shapes (closed set)

Each top-level `## Definition of done` bullet is one of:

| Form | Tick state | Authored by | Meaning |
|---|---|---|---|
| `- [ ] <text>` | unticked, no annotation | — | bullet not yet shipped |
| `- [x] <text> (closed by phase <N>, commit <short-sha>)` | ticked, code-phase | resolver §9 | code-shipping phase `<N>`'s commit `<short-sha>` satisfies the bullet (per the plan's `closes-dod`) |
| `- [x] <text> (closed by phase <N>, operator action <ISO-date>)` | ticked, operator-phase | resolver §9 | operator/decision-only phase `<N>` was completed on `<ISO-date>`; bullet claimed by that phase's `closes-dod` |
| `- [x] <text> (closed by commit <short-sha>)` | ticked, single-phase fallback | resolver §9 | the plan has no `## Phases` section; the single push's commit satisfies the bullet (single-phase fallback rule) |
| `- [ ] <text> (resolver claimed phase <N>, commit <short-sha>; evaluator rejected: <one-line reason>)` | unticked with rejection annotation | evaluator §6 | the evaluator's per-phase verification judged the attributed diff fails to satisfy the bullet; **sticky veto** — the resolver respects this and does not re-tick on subsequent pushes |
| `- [ ] <text> (previously claimed by phase <N>, commit <short-sha> on closed PR #<M>)` | unticked with predecessor annotation | planner revise (HARD path) | the previous PR was closed during a re-plan that started fresh; the bullet was ticked under that closed PR but the new plan needs new work to satisfy it |

All `<short-sha>` values are 7-char (matching the `## Phase tracker` and `_shared/handoff-format.md` conventions). `<ISO-date>` is `YYYY-MM-DD`.

## Indexing and parsing rules

- **Top-level bullets only.** Each line matching `^[ ]*-[ ]+\[[ x]\][ ]+` at the top level of the `## Definition of done` section counts. Sub-bullets (indented with two or more leading spaces beneath a top-level bullet) are detail, not DoD items.
- **1-based indexing.** The first top-level bullet is index 1. Indexes are stable within a single plan run — they only shift if bullets are added or removed from the body.
- **Case-insensitive on `x`.** `- [x]` and `- [X]` both read as ticked. Authors only write `- [x]`.
- **Section finder.** Locate the `## Definition of done` heading (case-insensitive on the section title). Read subsequent lines until the next `##` heading or EOF.
- **Annotation as suffix.** Annotations always appear at the end of the bullet line, inside `( ... )`. Bullet text itself ends immediately before the annotation's opening `(`. When no annotation is present, the bullet text runs to the end of the line.

## Recognition regex (informal)

Match the bullet line, then peel the annotation off the tail:

```
bullet line:  ^([ ]*)-[ ]+\[([ xX])\][ ]+(.+?)(?:[ ]+\((closed by|resolver claimed phase|previously claimed by) (.+)\))?$
```

Then dispatch on the prefix word:
- `closed by phase <N>, commit <sha>` → code-phase ticked
- `closed by phase <N>, operator action <date>` → operator-phase ticked
- `closed by commit <sha>` → single-phase fallback ticked
- `resolver claimed phase <N>, commit <sha>; evaluator rejected: <reason>` → sticky-veto unticked (note: the line starts `- [ ]` because the evaluator un-ticked it)
- `previously claimed by phase <N>, commit <sha> on closed PR #<M>` → predecessor unticked (line starts `- [ ]`)

The trailing `<reason>` in the evaluator-rejected form is a one-line free-text rationale; it does not need further structured parsing — it's audit text.

## Invariants

- **The bullet's checkbox state and its annotation form agree.** `- [x]` lines carry one of the three "closed by" forms or no annotation at all (legacy ticks that predate projection). `- [ ]` lines carry one of the two unticked-with-rationale forms or no annotation at all.
- **A bullet never carries two annotations stacked.** When an annotation is replaced (re-attribution during re-plan, predecessor demotion), the old annotation is overwritten in full — never appended after.
- **Annotations are attribution metadata, not part of the requirement.** The bullet's stated requirement is the text portion only. When the evaluator judges a bullet against the diff, it reads the text; the annotation tells it which diff to look at.
- **Index stability across runs.** When the resolver projects, it computes `closes-dod` indexes against the current body's bullets. If the body's top-level bullet count differs from the plan's max-referenced index, projection blocks for that run and re-routes to the planner (the body has drifted from the plan's understanding).

## Edge cases

- **No `## Definition of done` section in the body.** Skip projection silently; log to the calling skill's state summary.
- **Mixed annotation + checkbox-state inconsistency.** Example: `- [x] <text> (resolver claimed phase 2, commit abc; evaluator rejected: ...)`. Treat as un-tick-pending and warn: this shape indicates an in-flight evaluator un-tick that didn't complete, or a human edit that mismatched the checkbox to the annotation. The reading skill should re-derive the intended state from the annotation's prefix verb (`resolver claimed` → un-tick; `closed by` → tick) and surface the drift.
- **Annotation text contains parentheses.** The trailing-`(...)` rule consumes the last balanced parenthesized expression on the line. Annotations should not embed unescaped parentheses in their content; the evaluator-rejection reason should sanitize any `(` / `)` to `[` / `]` to keep the parser unambiguous.
- **Multiple bullets share identical text.** Indexing disambiguates — annotations are about position, not text — so duplicate-text bullets are not a parser hazard, only a UX one.

## Who reads, who writes

| Skill | Reads | Writes |
|---|---|---|
| `github-issue-resolver` | all forms (to detect rejections / predecessors before projecting) | `closed by phase / commit` ticks (projection on push, reconciliation on re-entry — never un-ticks) |
| `github-pr-evaluator` | `closed by` forms (per-phase verification input); writes `resolver claimed ... evaluator rejected: ...` on clear semantic mismatch | `resolver claimed ... evaluator rejected: ...` un-ticks (sticky vetoes) |
| `github-issue-planner` | all forms (revise-mode reconciliation reads the current body to compute the body-edit diff) | re-attribution edits during SOFT-path reconciliation; `previously claimed by ... on closed PR #<M>` un-ticks during HARD-path "Start fresh" |
