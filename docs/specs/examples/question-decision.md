# Example — `<!-- question-decision:v1 -->` recorded decision (schema definition)

> Artifact: the `<!-- question-decision:v1 -->` decision comment (prd.md §7, row 4).
> Source: `skills/question-resolver/SKILL.md:125-139` (Step 6 "Record the decision (the answer)").
> This is a **schema/template definition**, not a worked instance — the canonical example is this
> template block, verbatim, exactly as `question-resolver` (sole writer) posts it and the tiered
> status read (`skills/_shared/open-question-links.md` §"Status is the tracker's") short-circuits on.

```markdown
<!-- question-decision:v1 -->
## Decision
<the decision, stated plainly — what was decided>

## Rationale
<why — the reasoning, the option chosen over the alternatives>

## Constraints respected
<the binding constraints the decision honors, each cited — `constitution §N`, `PRD §N`, `path/to/file:NN`>

## Unblocks
<the build issues this answer unblocks (from the native `blocking` list), or "none">

## Caveats
<any coverage gap, provisional edge, or follow-up the decision leaves open — or omit if none>
```

The `<!-- question-decision:v1 -->` marker is always the **first line** of the comment body — this
is the durable, machine-readable resolution the tiered status read's Tier 1 short-circuits on
(`skills/question-resolver/SKILL.md:120-121`; contract in
`skills/_shared/open-question-links.md` §"Status is the tracker's": "The question is **resolved**
if either the issue is `closed` **or** it carries a `<!-- question-decision:v1 -->` comment").
