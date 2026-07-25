# Example — `<!-- open-question-links:v1 -->` section (schema + dispositions)

> Artifact: the `<!-- open-question-links:v1 -->` `## Open questions` build-issue body section
> (prd.md §7, row 5).
> Source: `skills/_shared/open-question-links.md:46-53` (the "Format" section's schema block) and
> `:61-71` (the "Stack-neutral examples" block, which is a worked multi-entry instance, not another
> template).
> The schema block is a **template definition**; the stack-neutral block below it is the closest
> thing v1 has to a worked instance, and is captured too since it demonstrates all three closed-set
> dispositions in one place.

## Schema (template)

```
## Open questions
<!-- open-question-links:v1 -->
- OQ: `<oq-id>` (<source-doc> <§/register-location>) — gates: <one line of the scope this OQ blocks>
  — disposition: scoped-out | in-scope (blocked) | provisional-default
  — question: #<N> | (not filed) — audience: <comma-separated audience:* labels, or (unknown)>
  — [provisional-default only] default: <the provisional choice built on> — retires-when: <#N answered>
```

The `## Open questions` heading is the human anchor; `<!-- open-question-links:v1 -->` is the
**first line inside the section** (readers locate the registry with a `startswith` match on that
line). Omit the whole section when no OQ gates the issue.

## Worked stack-neutral example (all three dispositions)

```
## Open questions
<!-- open-question-links:v1 -->
- OQ: `PRD-OQ-05` (docs/prd.md §12 Open questions) — gates: which payment methods ship at launch
  — disposition: scoped-out — question: #211 — audience: audience:business, audience:developer
- OQ: `OQ-08` (docs/ui-design.md §5 register) — gates: consult-modality copy on the next-consult tile
  — disposition: in-scope (blocked) — question: #212 — audience: audience:clinical
- OQ: `DESIGN-Q-3` (docs/design/notes.md "Open decisions") — gates: default sort order of the results list
  — disposition: provisional-default — question: #213 — audience: audience:ux
  — default: newest-first — retires-when: #213 answered
```

`disposition` is a closed set of exactly three values (`skills/_shared/open-question-links.md:55`):

- **`scoped-out`** — the drafter's default. The gated part is removed from this build issue's scope;
  it **MUST** have a matching line in `## Out of scope` naming the same OQ. No native dependency.
- **`in-scope (blocked)`** — the part stays in the DoD but cannot complete until the question
  answers. **Requires** a companion question to exist — the issue **MUST** be set natively
  `blocked by` it.
- **`provisional-default`** — built now on a stated provisional choice; not blocked. **MUST** carry
  `default:` and `retires-when: <#N answered>`.
