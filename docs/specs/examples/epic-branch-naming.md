# Example — `epic/<N>-<slug>` integration-branch naming (rule + worked examples)

> Artifact: the `epic/<N>-<slug>` integration-branch naming convention (prd.md §7, row 12).
> Source: `skills/github-issue-resolver/SKILL.md:459,471-486` ("Resolving the epic branch name" /
> "Computing a fresh slug (bootstrap only)"), quoted verbatim.
> This is a **rule + worked-example capture**, not a single schema fence — v1 has no fenced
> template for the naming rule itself (it's prose plus a numbered derivation plus three literal
> worked inputs/outputs), so this file quotes the governing paragraph, the six-step derivation, and
> all three worked examples verbatim.

## The discovery-first invariant (why a fresh slug is computed only on bootstrap)

`SKILL.md:459`, quoted verbatim:

> Both the epic-as-target flow and the story flow need to refer to the integration branch by name.
> The branch follows the pattern `epic/<N>-<slug>`, but the slug is derived from the epic title —
> and titles can shift, slugging conventions can be ambiguous, and two runs computing slugs
> independently have already produced divergent names (issue #102: run 1 picked
> `visual-redesign`, run 2 picked `daily-journal-visual-redesign`, which would have orphaned the
> original branch). To prevent that class of bug, **discover the existing branch by prefix; only
> compute a fresh slug on the bootstrap path.**

Discovery command (`SKILL.md:463-464`):

```bash
git ls-remote --heads origin "epic/<N>-*"
```

## The six-step slug derivation (bootstrap only)

`SKILL.md:471,473-478`, quoted verbatim:

> **Computing a fresh slug (bootstrap only).** Used only when discovery returns zero matches and the
> epic flow is bootstrapping a new branch. The derivation is:
>
> 1. Take the epic issue title.
> 2. If it begins with `Epic:` (case-insensitive), strip that prefix and any leading whitespace.
> 3. Lowercase.
> 4. Replace every run of characters not in `[a-z0-9]` with a single `-`.
> 5. Strip leading and trailing `-`.
> 6. Truncate to at most 50 characters; if the truncation would land mid-word (the next character is
>    `[a-z0-9]`), keep truncating back to the previous `-`. Strip any trailing `-` left behind.

The full slug is preferred over a "short" version — "Subjective shortening is what produced the
divergent run-1/run-2 names on issue #102 — the algorithm has no manual shortening step"
(`SKILL.md:480`).

## Worked examples

`SKILL.md:482-485`, quoted verbatim:

> **Examples.**
> - `Daily Journal Visual Redesign` → `daily-journal-visual-redesign`
> - `Epic: Macro Radials Data` → `macro-radials-data`
> - `Auth/Token Refresh (Phase 2)` → `auth-token-refresh-phase-2`

A literal branch name from these examples, given an epic issue number: title `Epic: Macro Radials
Data` on issue `#87` → branch `epic/87-macro-radials-data`.
