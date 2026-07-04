# Example — worked `## Handoff` (researcher)

> Artifact: one worked `## Handoff` sample for the pipeline skill `github-issue-researcher`
> (prd.md §7, row 10 — schema owned by `skills/_shared/handoff-format.md`; this is the researcher's
> worked rendering).
> Source: `skills/github-issue-researcher/SKILL.md:234-244` (Step 10 "Handoff", "Dossier posted."),
> quoted verbatim. The researcher has **no** `references/handoff-renderings.md` file — unlike the
> other four pipeline skills, its worked handoff renderings live directly in `SKILL.md`'s own
> Step 10, confirmed by inspection of `skills/github-issue-researcher/` (only `SKILL.md` +
> `references/research-validator-prompt.md` exist).

```
## Handoff

**Issue:** #142 — Migrate to <dependency> v<X> · open · feature · research: ✓ (https://github.com/owner/repo/issues/142#issuecomment-XXXXX)

**Next:** plan the approach in a fresh session; the planner ingests the dossier.

    /github-pipeline:github-issue-planner #142

**Why:** the dossier captures the current, fetched behaviour of <dependency> v<X> with provenance. The planner grounds its decisions in it and records the sources in its plan's `## External sources consulted`.
```

This is the researcher's clean-exit shape after posting a dossier — forward to the planner. The
`research: ✓` marker carries the dossier comment's URL in parentheses, per the shared handoff
schema's rule that "when the marker carries a URL (the researcher's clean exit), append it in
parentheses" (`skills/_shared/handoff-format.md`). SKILL.md's Step 10 also gives a second rendering
("Nothing to research (step 4 declined)") for the decline-gate outcome, still forwarding to the
planner but with `research: ✗` and no dossier posted.
