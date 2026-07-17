# Research dossier schema — `<!-- issue-research:v1 -->`

Read at the spine's `S-synth`. Author the dossier against this schema **verbatim** — it is the
[prd.md §7](../../../docs/prd.md)-frozen artifact the planner ingests, so its section set and the
literal footer/body provenance strings are a **byte-compatibility contract** (the planner's `startswith`
marker lookup and its `## External sources consulted` fold-back both match these bytes). The marker is
**always the first line** — any character before it makes the dossier undiscoverable. Omit optional
sections when empty; never pad. Fill the `<placeholders>` from this run's fetched, dated findings.

```
<!-- issue-research:v1 -->
**Research dossier** — #<N> <title> — researched <ISO-8601 UTC>, sources fetched <date(s)>

**What this is:** research input for whoever plans/implements this issue — current guidance from
the listed sources, collected and synthesized against this project's actual stack. Every cited page
was fetched on the dates shown; nothing here is from model memory. This is **not** an implementation
plan; `github-issue-planner` consumes it and owns the design decisions.

**Stack context the research was filtered against:** <the one-line stack summary from step 3>

## Questions researched
- <question> — <answered | partial | no authoritative source found>

## Consensus across sources
<what the credible sources agree on — the durable, low-risk findings>

## Findings by source
### <source name> — <primary/official | standards baseline | secondary (flagged)>
<the specific claim, the version it applies to, and the fetch date>

## Implications mapped to the issue's Definition of Done      (omit if the issue has no DoD)
- <DoD bullet> → <what the research means for satisfying it>

## Tensions for the planner to resolve
<open tensions / tradeoffs / conflicts the research surfaces — stated as questions for the planner,
 NOT decided here. A finding that contradicts the project's governing docs goes here, framed as a
 tension, never as a recommendation to override the docs.>

## Strawman draft (NOT final — planner/implementer owns the real call)      (optional)
<a concrete starting point a reader can react to, explicitly marked non-binding>

## Sources
- <url> — <tier> — fetched <date> — <what it informed>

_Authored by `github-issue-researcher`. Re-run that skill to refresh — do not hand-edit. The planner
records the provenance above in its plan's `## External sources consulted`._
```

The `researched` header takes an ISO-8601 stamp; a date-only stamp (`<date>T00:00Z`) is fine when only
the date is available — the fetch dates on the individual sources carry the currency guarantee.
