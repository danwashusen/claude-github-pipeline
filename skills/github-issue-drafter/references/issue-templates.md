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

**Question template:** the `question`-issue body schema (`## Question / ## Audience / ## Constraints / ## Context / ## References / ## Why this matters / ## Tracked in`), the no-DoD rule, the title convention, and the audience-label rule are [`../../_shared/question-issue.md`](../../_shared/question-issue.md) — the single source of truth; don't restate them here.

**Open questions on a build issue.** Any build template above (Bug, Incomplete, New-feature, Epic, Story) may carry an optional `## Open questions` section when the issue was drafted from a source with unresolved open questions — placed after `## Related issues`, omit if none. Its per-entry schema, the disposition set, and the native-`blocked by` rule live in [`../../_shared/open-question-links.md`](../../_shared/open-question-links.md) (don't restate them here); the drafter writes it at Step 4 from the Step 3.5 dispositions.

**About the "Out of scope" section:** Omit it by default. Only include it when one of these is true:

1. **The user explicitly excluded something** — e.g., "but I don't want to deal with X right now," "let's not bother with Y." Capture what they said, don't extrapolate.
2. **The title or capability is genuinely ambiguous about something a reader would reasonably assume is included.** For example, a feature titled "Add export to PDF" might reasonably make a reader assume bulk export is included; if it's not, that's worth calling out. The bar is high — only flag this when the ambiguity is real, not speculative.
3. **A part was `scoped-out` because an open question gates it** (Step 3.5). Write one line per scoped-out OQ, naming the OQ id so it cross-references the `## Open questions` entry — this is what keeps the gated part cleanly out-of-scope (and out of the DoD), not an in-scope deferral. Only OQ-driven scope-outs are auto-added; trigger 1's anti-extrapolation rule still governs everything else.

Default to omitting. Acceptance criteria already define what's in scope; don't pad the issue with speculative exclusions. Inventing out-of-scope items the user never mentioned is a form of hallucination — resist it.

If you find yourself wanting to write "Out of scope" but can't point to either trigger above, leave it out.
