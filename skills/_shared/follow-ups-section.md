# `## Follow-ups` section — shared contract

The `## Follow-ups` section of a PR body records what the PR deferred: one line per **filed** issue,
plus any **procedural notes** the pipeline captured instead of filing. This file is the single source
of truth for its line format. Two skills write it — the `resolver` (its URL weave,
`resolver/references/follow-up-tracking.md`) and the `evaluator` (its residual filing after a merge) —
and one script reads it: `scripts/parse.py` `scan_follow_ups`, which `prep_evaluator` composes into an
epic-integration PR's `facts.epic.residue` (the deferrals the epic's merged story PRs left).

## Why it exists

The residue reads every merged story PR's section to find the deferrals that may block the epic's
integration. Without a line grammar the reader cannot tell a filed deferral from a note that merely
mentions an issue (an open `question` issue cited in a procedural note read as an open deferral), and
cannot tell which polish ledger entries a filed issue carries — so a `file` entry kept blocking the
epic after its issue had shipped.

## Format

```
## Follow-ups
- Filed: #301 — cache invalidation on cold start · covers P1.2, P2.1
- Filed: https://github.com/octo/widgets/issues/302 — retry budget for the sync client
- Note: the importer's batch size was tuned against the staging data set; revisit once #61 is answered
```

- **`- Filed: <ref> — <title>`** — one line per filed issue, which is one per filing **group**
  (`follow-up-filing.md` "Grouping"), never one per item. `<ref>` is `#<N>` or the issue's full URL in
  this repo — no other form is read.
- **` · covers <ids>`** — appended when the group files `## Polish` ledger entries
  ([`polish-ledger.md`](polish-ledger.md)): every ledger id the issue carries, comma-separated. It is
  what ties a `file` entry to its issue, so the residue reads the deferral once, through the issue, and
  sees it resolved when the issue closes or is adopted as a story. Omit it for a group with no ledger
  entries (a review-deferred defect, a retry-ladder deferral).
- **`- Note: <text>`** — a procedural note (`follow-up-tracking.md` "capture in PR body"): something
  the next session should know that is not worth an issue. An issue it mentions is **not** a deferral.

## Rules

- **Writers add, never rewrite.** Each filing appends its `Filed:` lines; a line is never removed when
  its issue closes — the issue's state is the live fact, read at evaluation time.
- **Writes go through the single write path** — the staged body through `gh_persist.py edit-pr-body`,
  or the resolver's staged `pr.md` on a fresh PR.
- **Reading is lenient.** `scan_follow_ups` takes `Filed:` lines and, for PR bodies written before this
  contract (4.37.0), any other bullet's issue references — but never a `Note:` line, nor a line under a
  legacy *Procedural notes* label. It never raises.
