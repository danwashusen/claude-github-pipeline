# Story PR

Route for `vector.type == story` (base matches `epic/<N>-<slug>`). A child-story PR that merges into
its epic's integration branch, not `main`.

**Run the spine first.** Read [`evaluate-spine.md`](evaluate-spine.md) and execute it end to end. The
spine already grounds the scope check against the parent epic (`## Goal` / `## Background`) and
verifies the integration-branch caveat in the PR body. Everything below runs **only after S7-merge
actually merged**; on any no-merge exit, skip to the handoff — the three actions below must not fire
before the branch lands.

The distinct post-merge actions this route adds — all three needed because a story PR merges into a
**non-default** branch, so GitHub's auto-close-on-merge never fires and the tracker/planner state must
be updated by hand. Each is **idempotent** against a re-run or another tool.

## Action 1 — Close the story issue

`Fixes #<story>` never auto-fires on a merge into `epic/<N>-<slug>`. Close it explicitly (already-closed
is a safe no-op — `gh_persist.py close` is idempotent):

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py close <owner/repo> <story> --reason completed
```

## Action 2 — Tick the epic `## Stories` checkbox

GitHub task lists don't auto-tick on merge. Re-fetch the current epic body (another story may have
merged since prep) into `<facts.scratch>/epic-body-current.md`, find the `- [ ] #<story>` line in
`## Stories`, replace it with `- [x] #<story>`, and stage the updated body to
`<facts.scratch>/epic-body-updated.md`. Show the diff, then:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py edit-body <owner/repo> <epic> \
  "<facts.scratch>/epic-body-updated.md"
```
If the checkbox is already `[x]`, note it and skip. A failed epic edit does **not** block the review or
the other actions — surface it for manual reapplication.

## Action 3 — Append the epic delivery log

Record what the story **actually delivered** so the planner's just-in-time planning of later stories
grounds on what shipped. The evaluator is the **sole writer** of the single
`<!-- epic-delivery-log:v1 -->` comment; recording every story — including the last — keeps it
complete. Format and the writer/reader contract are owned by
[`../../_shared/epic-delivery-log.md`](../../_shared/epic-delivery-log.md); render it byte-for-byte per
[`../references/epic-delivery-log.md`](../references/epic-delivery-log.md).

Derive the delivered contract **shape** from the merged diff (the new/changed type, service, or API
signature — read from the workspace) — record **what actually merged**, not the plan's pinned
contract; a divergence is deliberately visible and is the planner's feedback edge. Cross-check against
the plan's `## Epic contract` `Delivers:` line (in hand from the facts). Under a `Plan override` (no
plan), record the shape from the diff alone.

Fetch the existing log comment (it may not exist yet — `startswith("<!-- epic-delivery-log:v1 -->")`),
stage the full updated body (marker line first, then the header, then one line per shipped story) to
`<facts.scratch>/delivery-log.md` — starting from the fetched body when it exists, from scratch
(marker + header + this story's line) when absent. Idempotent: update an existing `#<story>` line in
place rather than duplicating. Post through the single write path (plain create when absent;
delete-and-repost via `--delete-marker-id` when it existed):

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py comment <owner/repo> issue <epic> \
  "<facts.scratch>/delivery-log.md" [--delete-marker-id <existing-log-comment-id>]
```

## Residual follow-ups + cleanup

Then file residual non-blocking follow-ups (shared with the standard route): de-dup against the PR
body's `## Follow-ups` *Filed* entries, file each via
[`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md) (parent reference = this PR +
the story issue + the parent epic), post the URLs as a brief PR comment. Then tear down + remove the
work workspace and purge the scratch dir:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/workspace.py remove --work <facts.workspace.branch> --root <root>
```
(teardown hooks best-effort before removal, then `git worktree remove`), then `rm -rf "<facts.scratch>"`.

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md). A story clean merge
is **not terminal** — route by whether sibling stories remain (re-read the epic `## Stories` list,
re-fetched in Action 2):
- **More stories pending** → forward to `/github-pipeline:planner #<next-story>` to plan the next story
  just-in-time against the now-current epic HEAD. Story / Epic (`open (K of M stories closed)`) / PR /
  Cleanup lines.
- **Last sibling closed** → forward to `/github-pipeline:resolver #<epic>` in Epic-integration mode
  (it opens the integration PR against `main`). Epic progress `open (M of M stories closed)`.

`review:` is `APPROVE` or `APPROVE (operator)`; the merge line is `squash → epic/<N>-<slug>@<sha>`.

On a **no-merge** exit, Actions 1–3 did **not** run: emit the **soft-reject → re-route** shape to
`/github-pipeline:resolver continue #<PR>` (not the forward-to-next-story route — no merge landed; the
next story is deferred to a later run that actually merges this one), or the **APPROVE-but-skipped**
shape with the manual `gh pr merge` command.
