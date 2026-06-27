# Follow-up issue tracking

Follow-up items — adjacent bugs noticed during planning, incomplete features the diff exposed, deferred tests the retry-ladder or review loop punted, baseline detours that need their own PR — surface at four moments in this workflow: §7 baseline (pre-existing failures need a detour), the retry-ladder's escalation option 2 (defer failing tests), §10.4 (reviewer routes items to follow-up), and §11 summary (post-merge cleanup). Historically each moment improvised its own filing: some items got captured in PR-body lines that aged out of memory, others got hand-crafted `gh issue create` bodies that bypassed the project's `github-issue-drafter` skill and ended up with inconsistent format and missing parent references. The point of this section is to make filing follow-ups a single, predictable protocol that reuses the drafter's structure (PRD-grounded, sub-agent-reviewed, type-specific sections) rather than re-inventing it in each touch point.

## The follow-up registry

Maintain a working list — kept in your own conversation context, no file persistence needed — of follow-up items as they surface. Each entry has five fields:

- **Type** — `bug` | `incomplete-feature` | `deferred-test` | `revise-existing`. The drafter has a section template for each; classification matters because it determines the body structure.
- **Title hint** — one-line summary, drafter-style (e.g. *"Checkout-flow system specs deferred under intermittent session-timeout race"*).
- **Description** — 2–5 sentences naming what's wrong / what's needed / why deferred. The drafter takes this as the informal feedback and shapes the body around it.
- **Parent reference** — the current PR URL or issue #, plus the parent epic # if applicable. Without this, the filed issue is orphaned.
- **Urgency** — `file-now` or `file-at-checkpoint` (see "Hybrid timing" below).

## Filing vs. capturing — the decision rule

Not every observation deserves a filed issue. Distinguish:

- **File as issue** when the follow-up represents distinct trackable work: a bug to fix, an incomplete feature to finish, a deferred test to re-enable, or a revision to an existing issue body.
- **Capture in PR body / §11 summary** when the follow-up is procedural / informational only: drift notes ("epic-203 is behind main by 16 commits"), epic checkbox-sync reminders, "watch out for X in the next iteration."

Criterion: would a future contributor, reading the PR body alone, have all they need to act? If yes, PR-body note suffices. If they'd need a separate place to discuss, plan, or assign — file an issue. Conflating the two is how trackable work gets lost: a one-line PR-body bullet is invisible the moment the PR merges.

## Hybrid timing

When each touch point files matters because some items need a real issue number in the same iteration's commits (TODO markers, skip-annotation reasons, PR-body cross-links).

| Source of follow-up | Urgency | When to file |
|---|---|---|
| Defer-by-retry (retry-ladder escalation option 2) | `file-now` | Before pushing the iteration's commits — the `// TODO(#NNN)` markers and skip-annotation reasons (`XCTSkip(...)`, `skip "..."`) need real issue numbers in the same push. Filing after-the-fact and amending the markers in a follow-up commit clutters history and risks the markers being missed. |
| Defer-by-review (§10.4 deferred items) | `file-now` | Same reason — review-deferred items often include test changes that need real issue numbers before the iteration's commit. |
| §7 baseline-failure detour (option a) | `file-now` | Before resuming the original work — the detour PR resolves the filed issue, and the original PR's body will cite the detour. |
| Planning-time discoveries (§6 doc grounding turned up adjacent work) | `file-at-checkpoint` | End of §10, after review approval, before §11 — batched. These don't gate any commit, so deferring to one moment is cleaner than interrupting the planning phase. |
| Implementation-time discoveries (mid-§8, the model notices a related bug) | `file-at-checkpoint` | Same checkpoint. Note them in the registry as they surface; file at end-of-§10. |

## The end-of-§10 checkpoint

After §10's review loop reports approval and before §11's summary, present the `file-at-checkpoint` items in the registry to the user:

> *"These follow-ups surfaced during this resolution but weren't filed in-flight. File them?"*
>
> *[list each item: title hint, type, one-sentence description]*

The user batch-approves, edits the list, or drops items. Only after batch approval do you spawn the sub-agents (one per item). Then weave URLs back into §11's summary.

## Filing protocol — sub-agent proxy-confirms via the drafter

The drafter-proxy filing round-trip is shared with `github-pr-evaluator` (its post-merge
residual-filing step), so it lives in [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md) —
the single source of truth for the `general-purpose` sub-agent prompt, the three proxy-confirm checks,
and the URL return. For each item the user has approved at the §P5 checkpoint, spawn one sub-agent per
that file's protocol (substitute the placeholders at call time). The sub-agent isolates the drafter's
verbose work from the resolver's main context: the resolver sees one round-trip per item, input brief →
output URL.

## URL weaving — close the loop

Once an item is filed, the resolver does three things with the URL:

1. **Replace temporary `// TODO(?)` markers** in code with `// TODO(#NNN)` referencing the filed issue. Same for skip annotations — rewrite the test framework's skip reason (`XCTSkip("Deferred to ?…")`, Minitest/RSpec `skip "?…"`) to reference `#NNN`. Don't push the iteration without this rewrite; markers without real numbers age into noise.
2. **Update the PR body's `## Follow-ups` section** with a list item per filed issue (use `gh pr edit --body-file` or a one-shot append). Add the section if it doesn't exist. Putting follow-up links in the body (not a comment) makes them durable: comments scroll, the body persists.
3. **Thread the URLs into §11's summary** under a "Follow-ups filed" bullet, separate from the "Procedural notes" bullet that holds the capture-in-PR-body items.

A filed follow-up isn't complete until all three weaves are done.
