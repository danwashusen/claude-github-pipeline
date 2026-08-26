# Epic delivery-log rendering — `<!-- epic-delivery-log:v2:story:<N> -->`

The story route's Action 3 stages and posts **one comment per shipped story** on the parent epic. Its
format and the writer/reader ownership are owned by
[`../../_shared/epic-delivery-log.md`](../../_shared/epic-delivery-log.md); this rendering is
byte-compatible with that contract and with `docs/specs/examples/epic-delivery-log-per-story.md`.
Render exactly this shape, stage it to `<facts.scratch>/delivery-log-entry.md`, and post it per the
write arms below. The marker is always the **first line**, and `<N>` is the story's own issue number —
the same story the entry line names (every reader locates entries with a `startswith` match, so
anything before the marker makes an entry undiscoverable).

```
<!-- epic-delivery-log:v2:story:<N> -->
- #<story> — delivered: <actual contract shape, as merged> @ `<commit-sha>` (PR #<M>, merged <ISO-8601 date>)
```

Rules (from the shared contract):
- **One entry per comment, and no epic header.** A header repeated on every comment is N copies of a
  fact the epic issue already states. The entry line's grammar is identical to the legacy tier's, so
  one parser serves both.
- **`<actual contract shape>`** is the public surface the story actually merged (the new/changed type,
  service, or API signature) — recorded from the **merged diff**, not copied from the plan's pinned
  contract, so a divergence between pinned and shipped is visible here. There is no pressure to
  compress it: an entry has a whole 65,536-character budget to itself.
- **Idempotent, per story.** A story has exactly one record. Take the arm matching
  `facts.epic.delivery_log.story_recorded_in`:
  - `null` — no record yet → `gh_persist.py comment <owner/repo> issue <epic> <staged-entry>`.
  - `entries` — this story already has its own comment → `gh_persist.py edit-comment <owner/repo>
    <facts.epic.delivery_log.entry.comment_id> <staged-entry>`, a single atomic `PATCH` that keeps the
    comment URL stable.
  - `legacy` — this story's line lives in the legacy comment → update that line inside a re-staged
    legacy body (from `facts.epic.delivery_log.legacy.body` / `body_path`) and repost it with
    `comment … --delete-marker-id <facts.epic.delivery_log.legacy.comment_id>`. Never leave one story
    recorded in both tiers.
- **Ids are REST numeric ids**, never a thread comment's GraphQL node id (#34) — prep hands them
  already in the right id space, so never re-fetch a comment to get one.
- The evaluator is the **sole writer**; the planner is the sole reader. Recording every story —
  including the last — is what keeps the log complete for just-in-time story planning.

## The legacy tier — `<!-- epic-delivery-log:v1 -->` (read and update in place; never created)

Epics whose log predates per-story comments carry **one** comment holding every entry. This shape is
never created again; it is read forever, and a story already recorded here is updated here (the
`legacy` arm above) so no story ends up with two records. There is no backfill.

```
<!-- epic-delivery-log:v1 -->
**Epic delivery log** — #<epic-N> <title>
- #<story> — delivered: <actual contract shape, as merged> @ `<commit-sha>` (PR #<M>, merged <ISO-8601 date>)
- ...
```

## When `facts.epic.delivery_log.ambiguous` is true

Two comments record the *same* story (or the epic carries two legacy comments), so there is no single
record to update: post **nothing**, and report the duplicate `comment_urls` plus the recovery (delete
the stale one, re-run this evaluation to record this story's entry). Writing over an ambiguous record
would add a third copy. Note this is now story-scoped: a duplicate for one story no longer blocks
recording any other.

## When `facts.epic.delivery_log.story_number` is null

The PR closes zero or several issues, so which story this entry belongs to is not derivable from the
PR. Name the story you recorded in the summary, and record the entry against the issue whose
`## Epic contract` this evaluation actually judged.
