# Example — `<!-- implementation-plan-shipped:v1:phase:<N> -->` shipped-phase record (schema definition)

> Artifact: one shipped-phase record comment (prd.md §7), written by the planner on a revise and read
> by the resolver and evaluator. Source: `skills/_shared/plan-shipped-phases.md`, § "Format" — the
> single source of truth for this artifact's format. Cited by **section anchor, not line numbers**, so
> an insertion above the fence cannot rot the citation.
> This is a **schema/template definition**, not a worked instance — the canonical example is this
> template block, verbatim.

```
<!-- implementation-plan-shipped:v1:phase:<N> -->
**Shipped on:** #<PR> · Phase <N> — <phase title, as in ## Phases>

## Changes (file-level)
- <entries moved verbatim from the main plan>

## Data model / schema impact
- <entries moved verbatim — omit the section when the phase moved none>

## Test plan
- <entries moved verbatim>
```

Why it exists: a story or single-issue plan only grows on revise, and a shipped phase cannot be
retired from it because the evaluator judges the whole PR against these three sections. #690's
seven-phase plan went 53.6k → 63.9k characters against the 65,536-character cap in one revise. One
record per shipped phase keeps that detail binding without it costing the plan comment anything.

Three properties of this template are load-bearing and must not be "tidied":

- **The marker is a separate family.** `<!-- implementation-plan-shipped:` never starts with
  `<!-- implementation-plan:v1 -->`, so no plan `startswith` lookup can match a record and make the
  plan `MARKER_AMBIGUOUS`. `:phase:1 -->` is not a prefix of `:phase:10 -->`.
- **Line 2 carries the PR.** The key is (PR, phase): a Start-fresh closes the PR and its records go
  inert with no delete.
- **The entries are verbatim.** A record is a move of reviewer-verified text, never a re-authoring,
  and it is never edited once posted.
