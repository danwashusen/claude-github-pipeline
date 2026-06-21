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

**About the "Out of scope" section:** Omit it by default. Only include it when one of these is true:

1. **The user explicitly excluded something** — e.g., "but I don't want to deal with X right now," "let's not bother with Y." Capture what they said, don't extrapolate.
2. **The title or capability is genuinely ambiguous about something a reader would reasonably assume is included.** For example, a feature titled "Add export to PDF" might reasonably make a reader assume bulk export is included; if it's not, that's worth calling out. The bar is high — only flag this when the ambiguity is real, not speculative.

Default to omitting. Acceptance criteria already define what's in scope; don't pad the issue with speculative exclusions. Inventing out-of-scope items the user never mentioned is a form of hallucination — resist it.

If you find yourself wanting to write "Out of scope" but can't point to either trigger above, leave it out.
