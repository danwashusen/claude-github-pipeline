# Issue templates

Fallback issue-body templates for when the repo provides no issue template of its own (Step 2 checks). Use the section shapes verbatim; omit any section whose guidance says "omit if none."

**Bug template:**

```markdown
## Description
<one-paragraph summary of the bug>

## Steps to reproduce
1. <step>
2. <step>
3. <step>

## Expected behavior
<what should happen>

## Actual behavior
<what actually happens, including any error messages>

## Environment
- <OS / browser / version / etc., if relevant>

## Related issues
<only if user referenced other issues — see "Detecting related issues" above. Omit section if none.>

## Additional context
<screenshots, logs, anything else — omit section if none>
```

**Incomplete feature template:**

```markdown
## What exists today
<what currently works>

## What's missing
<the specific gap>

## Definition of done
- [ ] <criterion>
- [ ] <criterion>

## Context
<why this was left incomplete, if known>

## Related issues
<only if user referenced other issues. Omit section if none.>
```

**New feature template (user story):**

```markdown
## User story
As a **<persona>**, I want **<capability>** so that **<benefit>**.

## Background
<why this matters — the underlying motivation>

## Acceptance criteria
- [ ] <criterion>
- [ ] <criterion>

## Related issues
<only if user referenced other issues. Omit section if none.>
```

**Epic template:**

```markdown
## Goal
<one paragraph: what this epic delivers, what problem it solves>

## Background
<why now — what prompted this work; reference PRD/architecture sections where relevant>

## Stories
- [ ] <Story 1 title>
- [ ] <Story 2 title>

## Definition of done
- [ ] All stories above are closed
- [ ] <any epic-level acceptance bar, e.g. "5 UI flows green in CI">

## Related issues
<only if user referenced other issues. Omit section if none.>

## PRD impact
<only if applicable. Omit otherwise.>
```

**Story template:**

```markdown
**Epic:** #<epic-#> — <Epic title>

## What exists today
<what currently works in this area, and what limitation prompted this story>

## What's missing
<the specific gap this story closes; reference architecture/PRD sections where relevant>

## Definition of done
- [ ] <criterion>
- [ ] <criterion>

## Context
<optional — dependencies, constraints, why this was deferred>

## Related issues
<only if user referenced other issues. Omit section if none.>
```

**Question template:**

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
<the docs (with §/heading), code paths, epics, or issues that ground the question — reuses "Detecting related issues". Omit a row that doesn't apply; omit the section if the question stands alone.>

## Why this matters
<what this question gates — the work, decision, or doc that's blocked until it's answered>

## Tracked in
<external tracker id + location when the question comes from a tracked-questions list, e.g. `docs/prd.md → Open Questions → PRD-OQ-06b`. When this question was spun off as a companion to a build issue, ALSO name the build issue # it gates — both pointers, so the loop closes from either end. Omit if neither applies.>
```

A question is filed for a human to answer, not for the pipeline to build, so it carries **no** Definition of done or Acceptance criteria — `## Context` + `## References` exist to make the question *answerable*, which is the only bar that matters here. Don't invent context, options, or a recommended answer the user didn't give; a thin-but-honest question beats a confidently-framed wrong one.

**Open questions on a build issue.** Any build template above (Bug, Incomplete, New-feature, Epic, Story) may carry an optional `## Open questions` section when the issue was drafted from a source with unresolved open questions — placed after `## Related issues`, omit if none. Its per-entry schema, the disposition set, and the native-`blocked by` rule live in [`../../_shared/open-question-links.md`](../../_shared/open-question-links.md) (don't restate them here); the drafter writes it at Step 4 from the Step 3.5 dispositions.

**About the "Out of scope" section:** Omit it by default. Only include it when one of these is true:

1. **The user explicitly excluded something** — e.g., "but I don't want to deal with X right now," "let's not bother with Y." Capture what they said, don't extrapolate.
2. **The title or capability is genuinely ambiguous about something a reader would reasonably assume is included.** For example, a feature titled "Add export to PDF" might reasonably make a reader assume bulk export is included; if it's not, that's worth calling out. The bar is high — only flag this when the ambiguity is real, not speculative.
3. **A part was `scoped-out` because an open question gates it** (Step 3.5). Write one line per scoped-out OQ, naming the OQ id so it cross-references the `## Open questions` entry — this is what keeps the gated part cleanly out-of-scope (and out of the DoD), not an in-scope deferral. Only OQ-driven scope-outs are auto-added; trigger 1's anti-extrapolation rule still governs everything else.

Default to omitting. Acceptance criteria already define what's in scope; don't pad the issue with speculative exclusions. Inventing out-of-scope items the user never mentioned is a form of hallucination — resist it.

If you find yourself wanting to write "Out of scope" but can't point to either trigger above, leave it out.
