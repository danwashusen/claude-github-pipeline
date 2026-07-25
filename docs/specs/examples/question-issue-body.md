# Example — `question`-issue body schema (schema definition)

> Artifact: the `question`-issue body schema + `audience:*` labels (prd.md §7, row 9).
> Source: `skills/_shared/question-issue.md:12-33` (the "Body template" section), quoted verbatim.
> This is a **schema/template definition**, not a worked instance — the canonical example is this
> template block, exactly as both `github-issue-drafter` and the `open-questions` sweep file it.

```markdown
## Question
<the decision or answer needed, phrased for the target audience(s) — a business stakeholder, an architect, and a developer should each be able to read it in their own terms>

## Audience
<who needs to answer. When more than one audience is named, add a one-line "what we need from you" per audience so each knows their part.>

## Constraints
<hard limits the answer must respect that are outside the audience's control — regulation, legal/compliance, insurance, contractual/SLA obligations, or third-party-platform limits. State each as *what is fixed* + *the external force that fixes it*, so the reader sees why it's non-negotiable without inferring it from the references; cite the doc. Example: "Consult must be real-time (phone or video both qualify) — AHPRA/Medical Board telehealth guidance forbids prescribing off a questionnaire-only path (`PRD-OQ-20`/`PRD-TH-01`)." This separates what's already fixed from the part that's genuinely the audience's call. Omit the section when the decision is unconstrained; don't pad it with product preferences or scope choices — those are the decision itself, not an external constraint on it.>

## Context
<enough background that the reader can answer without the conversation that produced the question — the same cold-read bar the rest of the skill applies>

## References
<the docs (with §/heading), code paths, epics, or issues that ground the question. Omit a row that doesn't apply; omit the section if the question stands alone.>

## Why this matters
<what this question gates — the work, decision, or doc that's blocked until it's answered>

## Tracked in
<external tracker id + location when the question comes from a tracked-questions list, e.g. `docs/prd.md → Open Questions → PRD-OQ-06b`. When this question was spun off as a companion to a build issue, ALSO name the build issue # it gates — both pointers, so the loop closes from either end. Omit if neither applies.>
```

A question is filed for a human to answer, not for the pipeline to build, so it carries **no**
Definition of done or Acceptance criteria (`skills/_shared/question-issue.md:35-38`).

## Title convention

`<tracker-id> — <question topic>` when a tracker id exists — e.g. `PRD-OQ-06b — Which billing model
for v1?`; otherwise just the question topic phrased as a question
(`skills/_shared/question-issue.md:42-44`).

## Audience labels

A question routes to the people who can answer it, so its target audience(s) become labels — one
per audience, namespaced: `audience:business`, `audience:architect`, `audience:developer`,
`audience:ux`, and so on (`skills/_shared/question-issue.md:48-50`). Audience labels don't count
against the three-label cap. Unlike type/priority labels, a missing audience label is created as
part of filing (`skills/_shared/question-issue.md:63-77`):

```bash
gh label create "audience:business" --description "Question for business stakeholders" --color BFD4F2 2>/dev/null || true
```
