# Handoff format — shared reference

The four GitHub-pipeline skills (`github-issue-drafter`, `github-issue-planner`, `github-issue-resolver`, `github-pr-evaluator`) close every clean run with a single **`## Handoff`** block. Each skill runs in its own Claude Code session, so the handoff is the only bridge between sessions — it must read cold and carry a copy-pasteable command for the user to start the next session.

This file is the single source of truth for the schema, the omission rules, and the state-marker vocabulary. Per-skill renderings (which clean-exit branches a given skill emits, and the exact wording for each) live in that skill's `SKILL.md`.

## Schema

```
## Handoff

**Issue:** #N — <title> · <state> · <type> · plan: <✓ | ✗ | stale>
**PR:** #M — <title> · <state> · base <ref> · review: <verdict | not run> · health: <✅/❌ at <short-sha> | not run> · merge: <strategy → <ref>@<short-sha> | skipped (<reason>) | not run>
**Cleanup:** <one-line worktree / branch / scratch summary>

**Next:** <one-line description of what the fresh session will do>.

    /<next-skill> [<args>]

**Why:** <one line — for forward routes, what the next session will accomplish; for re-routes, the specific finding that triggered the regression and what the user should confirm>
```

The block is always present on a clean exit. Lines are omitted (not blanked, not stubbed) when they don't apply.

## Omission rules

- **`Issue:` / `Epic:` / `Story:`** — exactly one is always present. Which one depends on the work shape:
  - Single non-Epic issue → `Issue:`.
  - Epic in any role (drafter Epic batch, planner Epic fan-out, evaluator on an Epic integration PR) → `Epic:`. Add a `Stories:` line listing the child stories with their state markers.
  - A story under an Epic (evaluator after a story PR merges, resolver working on a story) → `Story:` for the story plus an `Epic:` line for the parent's progress (e.g. `open (3 of 5 stories closed)`).
- **`PR:`** — omit entirely when no PR exists. Drafter clean exits and the planner's plan-comment-only clean exits skip this line. Resolver clean exits always have a PR. Evaluator clean exits always have a PR.
- **`Cleanup:`** — evaluator-only, and only after the merge ran (§14's worktree teardown / removal / scratch purge sequence has executed). Omit on the evaluator's no-merge branches (soft-reject, DIRTY/BLOCKED-skip, user-declined merge) and on every other skill's clean exit.
- **Fenced next-action block** — replaced with the literal `(terminal — no follow-up skill)` for terminal endings (evaluator clean merge of a standard PR, evaluator clean merge of an Epic integration PR). The `Why:` line still appears and explains why the pipeline ends here.
- **`Why:`** — always present, on both forward and backward routes. For forward routes, name what the next session will accomplish. For re-routes, name the specific finding (audit dimension, plan-decision quote, doc citation, file:line evidence) that triggered the regression — vague Whys aren't useful weeks later when the user picks the issue back up.

## State-marker vocabulary (closed sets)

Use these exact words. Don't invent synonyms.

| Field | Values |
|---|---|
| Issue `state` | `open`, `closed` |
| Issue `type` | `bug`, `feature`, `incomplete`, `story`, `epic` |
| Issue `plan` | `✓` (posted), `✗` (none), `stale` (posted but superseded) |
| PR `state` | `draft`, `open`, `merged`, `closed` |
| PR `review` | `APPROVE`, `COMMENT (soft-reject)`, `not run` |
| PR `health` | `✅ at <short-sha>`, `❌ at <short-sha>`, `not run` |
| PR `merge` | `squash → <ref>@<short-sha>`, `merge → <ref>@<short-sha>`, `skipped (<reason>)`, `not run` |

`<short-sha>` is a 7-character hex prefix. `<ref>` is the merge target (`main` for standard PRs and Epic integration PRs, `epic/<N>-<slug>` for story PRs). When the plan marker carries a URL (planner clean exit), append the URL in parentheses: `plan: ✓ (https://github.com/owner/repo/issues/N#issuecomment-...)`.

## Epic and Story variants

When the work shape involves an Epic, the heading line and supporting state expand:

- **Epic in any role.** Replace `Issue:` with `Epic:`. Add a `Stories:` line that lists the child story numbers and a coarse progress marker:

  ```
  **Epic:** #150 — Chat & session UX polish · open · epic · plan: ✓
  **Stories:** #151, #152, #153, #154, #155 (5 filed, dependency-ordered)
  ```

  After child stories start closing, switch the `Stories:` line to a progress count and (optionally) flag the next story:

  ```
  **Stories:** 3 of 5 closed · next: #154
  ```

- **Story under an open Epic** (evaluator on a story PR; resolver working on a story). Use a `Story:` line for the story itself and add an `Epic:` line that names the parent's progress:

  ```
  **Story:** #151 — Add export service · closed · story · plan: ✓
  **Epic:** #150 — Chat & session UX polish · open (1 of 5 stories closed)
  ```

The PR / Cleanup / Next / Why lines follow the standard rules.

## Terminal endings

Some clean exits end the pipeline for this issue — there's no next skill to invoke. Drop the fenced command block and keep everything else:

```
**Next:** (terminal — no follow-up skill)

**Why:** the PR satisfied every dimension cleanly and merged into main. The issue is closed by GitHub's auto-close; no follow-up skill is required for this issue.
```

Terminal endings exist today on the evaluator only:
- standard PR clean merge,
- Epic integration PR clean merge.

Story PR clean merges are **not** terminal — they hand off to the resolver on the next story (or to the resolver in Epic-integration mode if every child story is now closed).

## Re-routes

A re-route is a handoff whose `Next:` points at a prior skill — typically:

- resolver → planner (the plan's locked decisions don't survive contact with the code; refresh the plan)
- resolver → drafter (the issue body fails the resolver's fitness-to-implement audit, or contradicts a doc the resolver can't reconcile)

The schema does not change. The `Why:` line is the load-bearing piece — it must name the specific evidence so the user (and the prior skill, when re-run) can act without re-investigating:

- Plan re-routes: quote the locked decision verbatim and cite the `file:line` where the contradiction surfaced.
- Drafter re-routes: quote the body's claim verbatim, name the missing or contradictory symbol, and cite the closest-match `file:line`.

The resolver does **not** invoke the prior skill via the `Skill` tool on a re-route. The handoff is the only signal; the user runs the revise command in a fresh session. This is intentional: session-per-skill is the architectural choice that lets each skill stay context-clean, and crossing session boundaries silently from inside a skill defeats it.

## Authorship

The snapshot lines (issue state, PR state, base, verdict, health, merge, cleanup) are mechanical and should be filled from data the skill already has in hand — typically the most recent `github-ops` payload (`GATHER_ISSUE`, `GATHER_PR`) plus the locally-produced results of the current run (the review verdict, the cache comment's SHA, the merge command's outcome). Don't re-fetch just to render the handoff; if the cache is fresh enough to gate decisions, it's fresh enough to print.

The `Next:` action and the `Why:` line are judgment, not data. The skill's main loop authors them — the choice of next skill, the framing of why, and the exact argument shape passed to the next slash command are decisions the skill makes based on the run it just completed.
