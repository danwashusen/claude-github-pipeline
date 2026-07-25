# research spine — shared across broad / targeted / revise

The gather-and-verify-and-post backbone every mode runs, after its variant has produced the question set. The
variant reads this spine and runs it end to end; the mode differences here are **facts** (`facts.revise` present
⇒ delete-and-repost + diff show), never branches. Hold the input-not-authority boundary throughout.

## S-gather — Gather current truth (fetch, don't recall)

`Read` [`../references/gather-tactics.md`](../references/gather-tactics.md) and gather per it: the credibility
tiers, the `deep-research` escalation, the JS-rendered-doc fetch tactic, and the absolute rule that **every
claim traces to a page fetched this run, with its fetch date** — no recall.

## S-synth — Synthesize the dossier

`Read` [`../references/dossier-schema.md`](../references/dossier-schema.md) and author against that schema —
the `<!-- issue-research:v1 -->` marker is **always the literal first line**. Omit optional sections when empty;
never pad; keep findings tight and attributed (the planner needs facts with provenance). A finding contradicting
a governing doc goes under `## Tensions for the planner to resolve`, never a recommendation to override it.

## S-validate — Validate (isolated review loop, ≤3 passes)

Before showing the dossier, hand it to an isolated validation sub-agent — you synthesized it holding the
conversation and search notes, none of which appear in the posted comment. Spawn an `Explore` sub-agent
with [`../references/research-validator-prompt.md`](../references/research-validator-prompt.md), filling
its `<<placeholders>>` (`dossier_body`, `mode`, `issue_number`, `repo_owner`/`repo_name`, `repo_root` =
`facts.root.path`, `dimensions`), and run the ≤3-pass loop it defines (drop evidence-less findings;
blockers always, suggestions by default, nits never; exit clean / circular / at cap). Apply findings to
your own dossier — a citation-integrity or scope BLOCKER you can't fix by fetching a real source or
trimming overreach means the claim shouldn't be there (drop it, or downgrade to "no authoritative source
found"). On a cap/circular exit, show a short "Validation notes" block before posting.

## S-persist — Persist the dossier

On a clean exit, show the user the dossier — the **full body** in broad/targeted mode, a **diff** when
`facts.revise` is present — then stage and post. Write the full body (marker-first) to
`facts.scratch/research.md`, then:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py comment <owner/repo> issue <N> facts.scratch/research.md \
  [--delete-marker-id <facts.revise.dossier.comment_id>]   # revise mode only
```

`--delete-marker-id` (present only when `facts.revise` is) posts the new comment **before** deleting the
old — a crash must never leave zero dossiers. Capture the returned URL; on `EMPTY_BODY_FILE`, re-write the
file and re-run. Then apply the `researched` label (idempotent, low-stakes — log-and-continue on failure).
A user who says "research but don't post yet" is honoured — pause after showing the dossier, before posting.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py edit-labels <owner/repo> <N> --add researched
```

## S-handoff — Handoff

`Read` [`../references/handoff-renderings.md`](../references/handoff-renderings.md) immediately before
composing this and emit the matching shape verbatim — copy it, substitute only the data (issue number,
title, state, dossier URL), never rename a field or restructure it. Dossier posted → `research: ✓` with
the URL; the decline exit (broad only) → `research: ✗`. Both forward to the `planner`.
