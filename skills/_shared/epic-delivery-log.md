# Epic delivery log — shared contract

The **epic delivery log** is a single durable comment on an epic issue that records what each child story **actually delivered** as it lands. It is the cross-skill bridge between story implementation and the just-in-time planning of later stories.

This file is the single source of truth for its format and ownership. Both consumers cite it: `github-pr-evaluator` (writer) and `github-issue-planner` (reader).

## Ownership

- **Writer — `github-pr-evaluator` (sole writer).** When it merges a story PR (§13) it appends an entry recording what that story delivered, creating the comment lazily on the first story merge. Recording **every** story here — including the last — is what keeps the log complete.
- **Reader — `github-issue-planner`.** During "Just-in-time story planning" it reads the log to (a) reconcile the epic plan's pinned `## Story contracts` against what actually shipped, and (b) feed Dimension 8's "consumes only what's shipped" check. The planner never writes it.

Keeping the log in its own comment — not inside the verified `<!-- implementation-plan:v1 -->` plan — is deliberate: the plan is verified and immutable, while this record changes on every merge.

## Format

The `<!-- epic-delivery-log:v1 -->` marker is always the **first line** of the comment body (every reader locates it with a `startswith` match — anything before it makes the log undiscoverable):

```
<!-- epic-delivery-log:v1 -->
**Epic delivery log** — #<epic-N> <title>
- #<story> — delivered: <actual contract shape, as merged> @ `<commit-sha>` (PR #<M>, merged <ISO-8601 date>)
- ...
```

One line per shipped story, in merge order. `<actual contract shape>` is the public surface the story actually merged (the new/changed type, service, or API signature) — recorded from the merged diff, **not** copied from the plan's pinned contract, so a divergence between pinned and shipped is visible here.

## Writing it (evaluator)

Go through the single write path — never hand-roll `gh` (Rule 7; a raw `gh api`/`Write`+`gh` assembly re-opens the #626/#627 empty-body race). Stage the full updated body (marker line first) to the run's scratch dir, then:

> `PERSIST_COMMENT(target=issue, id=<epic-N>, repo=<owner/repo>, body_path=<staged-body>, delete_marker_id=<existing log comment id, if any>)`

A plain create when the comment is absent; a delete-and-repost when it exists (the same mechanic the planner uses for its plan comment in revise mode and the evaluator uses for its §5.6 health cache). There is no in-place edit op — append by re-staging the full body and reposting. Idempotent: if a line for `#<story>` already exists, update it in place in the staged body rather than duplicating.

## Reading it (planner)

Fetch the `<!-- epic-delivery-log:v1 -->` comment (`(none yet)` if absent). A `Consumes:` claim in a story's `## Epic contract` must name a contract already recorded here, **with a matching shape**; a divergence between a recorded shape and the epic plan's pinned `## Story contracts` is the planner's signal to re-plan the epic before grounding later stories on a stale contract.
