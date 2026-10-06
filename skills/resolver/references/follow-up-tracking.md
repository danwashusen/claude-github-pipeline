# Follow-up issue tracking

Follow-up items — adjacent bugs noticed during planning, incomplete features the diff exposed, deferred
tests the retry-ladder or review loop punted, baseline detours that need their own PR — surface at four
moments in this workflow: the epic baseline (pre-existing failures need a detour), the retry-ladder's
escalation option 2 (defer failing tests), the review loop's classification (reviewer routes items to
follow-up), and the handoff (post-merge cleanup). Historically each moment improvised its own filing: some
items got captured in PR-body lines that aged out of memory, others got hand-crafted `gh issue create`
bodies that bypassed the project's drafter skill and ended up with inconsistent format and missing parent
references. The point of this section is to make filing follow-ups a single, predictable protocol that
reuses the drafter's structure (PRD-grounded, sub-agent-reviewed, type-specific sections) rather than
re-inventing it in each touch point.

## The follow-up registry

Maintain a working list — kept in your own conversation context, no file persistence needed — of
follow-up items as they surface. Each entry has seven fields:

- **Type** — `bug` | `incomplete-feature` | `deferred-test` | `revise-existing`. The drafter has a
  section template for each; classification matters because it determines the body structure.
- **Title hint** — one-line summary, drafter-style (e.g. *"Checkout-flow system specs deferred under
  intermittent session-timeout race"*).
- **Description** — 2–5 sentences naming what's wrong / what's needed / why deferred, plus any judgment
  worth freezing (rulings, exemption classes, constraints). Durable anchors only (paths, symbols, doc
  section headings, register IDs, `#N`) — never pasted grep output or `path:line` inventories; downstream
  skills re-derive sites fresh. The drafter takes this as the informal feedback and shapes the body
  around it. A defect this PR **introduced** (`review-fix-round.md` "Classification rubric") reaches the
  registry only through an operator answer, and its description states why it was not fixed here — the
  answer that deferred it and the reason given — never nothing.
- **Parent reference** — the current PR URL or issue #, plus the parent epic # if applicable. Without
  this, the filed issue is orphaned.
- **Urgency** — `file-now` or `file-at-checkpoint` (see "Hybrid timing" below).
- **Group** — the related items it files together with, per
  [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md) "Grouping" (same type, same
  seam, ≤ ~5; a lone item is a group of one). Two rubric groupings come first: items sharing a root cause
  are one entry naming the class and every known site, and drift in docs the repo routes through a named
  command or process is one group per owning process, one item per claim, uncapped — the **docs lane**.
  A pre-existing security or privacy defect is a group of its own. Group only items filed at the same
  moment: `file-now` items group among themselves at their filing moment (state the grouping in the round
  reply — there is no card), `file-at-checkpoint` items at the checkpoint.
- **Trigger** — for a risk that becomes live only when a named issue X ships, X. Empty otherwise.

## Filing vs. capturing — the decision rule

Not every observation deserves a filed issue. Distinguish:

- **File as issue** when the follow-up represents distinct trackable work: a bug to fix, an incomplete
  feature to finish, a deferred test to re-enable, or a revision to an existing issue body.
- **Capture in PR body / handoff** when the follow-up is procedural / informational only: drift notes
  ("epic-203 is behind main by 16 commits"), epic checkbox-sync reminders, "watch out for X in the next
  iteration."

Criterion: would a future contributor, reading the PR body alone, have all they need to act? If yes,
PR-body note suffices. If they'd need a separate place to discuss, plan, or assign — file an issue.
Conflating the two is how trackable work gets lost: a one-line PR-body bullet is invisible the moment the
PR merges.

## Hybrid timing

When each touch point files matters because some items need a real issue number in the same iteration's
commits (TODO markers, skip-annotation reasons, PR-body cross-links).

| Source of follow-up | Urgency | When to file |
|---|---|---|
| Defer-by-retry (retry-ladder escalation option 2) | `file-now` | Before committing the iteration's fix (the phase pushes once, at S5.2) — the `// TODO(#NNN)` markers and skip-annotation reasons (`XCTSkip(...)`, `skip "..."`) need real issue numbers in the same commit. Filing after-the-fact and amending the markers in a follow-up commit clutters history and risks the markers being missed. |
| Defer-by-review (review-loop deferred items) | `file-at-checkpoint`, or `file-now` when the round's commit needs the number | Batched for the operator's approval: the resolver once filed every review-deferred item mid-loop with no confirmation step, and an audit of one repo's review-loop follow-ups found a fifth of them were fixable in the PR, plan gaps, or noise. An item whose number a commit needs — a `// TODO(#NNN)` marker, a skip annotation — still files `file-now`, before that commit. |
| Epic baseline-failure detour | `file-now` | Before resuming the original work — the detour PR resolves the filed issue, and the original PR's body will cite the detour. |
| Planning-time discoveries (doc grounding turned up adjacent work) | `file-at-checkpoint` | End of the review loop, after review approval, before the handoff — batched. These don't gate any commit, so deferring to one moment is cleaner than interrupting the planning phase. |
| Implementation-time discoveries (the model notices a related bug mid-work) | `file-at-checkpoint` | Same checkpoint. Note them in the registry as they surface; file at end-of-loop. |

## The end-of-loop checkpoint

After the review loop reports approval and before the handoff — or before the phase's `Checkpoint` card
when the session continues to the next phase (`phase-continuation.md`; a different checkpoint from this
one) — present the `file-at-checkpoint` items in the registry to the user:

> *"These follow-ups surfaced during this resolution but weren't filed in-flight. File them?"*
>
> *[list each proposed group: title hint, type, then its items — one-sentence description each]*

List a pre-existing security or privacy group first. The user batch-approves, edits the list, regroups
(splits or merges groups), or drops items. Only after batch approval do you spawn the sub-agents — one per group, all in one message per the shared protocol. Then, once the whole batch has
returned, weave URLs back into the handoff.

## Before filing — search for the root cause

For each group about to be filed (either urgency), search the repo's open issues for the same root cause,
the shape [`retry-ladder.md`](retry-ladder.md) "The check" uses for a failing test — the class's
distinctive symbol, path, or claim:

```bash
gh issue list --repo <owner/repo> --state open \
  --search "<distinctive symbol> OR <path> OR <claim keyword>" \
  --json number,title,url --limit 10
```

Read a plausible match before deciding. An open issue that already tracks the class is **cited, never
re-filed**: the item takes its URL in the weaving below, and a site the issue does not name goes on it
as one comment through the single write path (stage the body to `<facts.scratch>/followup-site.md`):

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py comment <owner/repo> issue <M> "<facts.scratch>/followup-site.md"
```

## Filing protocol — sub-agent proxy-confirms via the drafter

The drafter-proxy filing round-trip is shared with the evaluator (its post-merge residual-filing step),
so it lives in [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md) — the single
source of truth for the `general-purpose` sub-agent prompt, the three proxy-confirm checks, and the URL
return. For the groups the user has approved at the checkpoint, spawn one sub-agent per group, all in one
message, per that file's protocol (substitute the placeholders at call time). The sub-agents isolate the
drafter's verbose work from the resolver's main context: the resolver sees one batched round-trip, one
brief per group in → one URL per group out (with the item ids it covers), and an errored group never
blocks the others' weaving.

## URL weaving — close the loop

Once a group is filed, the resolver does three things with its URL — every item in the group shares it:

1. **Replace temporary `// TODO(?)` markers** in code with `// TODO(#NNN)` referencing the filed issue.
   Same for skip annotations — rewrite the test framework's skip reason (`XCTSkip("Deferred to ?…")`,
   Minitest/RSpec `skip "?…"`) to reference `#NNN`. Don't commit the iteration without this rewrite; markers
   without real numbers age into noise.
2. **Update the PR body's `## Follow-ups` section** with a list item per filed issue — one per group, not
   per item (stage the updated body and `edit-pr-body` the PR). Add the section if it doesn't exist. Putting follow-up links in the body
   (not a comment) makes them durable: comments scroll, the body persists.
3. **Thread the URLs into the handoff** under a "Follow-ups filed" bullet, separate from the "Procedural
   notes" bullet that holds the capture-in-PR-body items. A pre-existing security or privacy follow-up
   leads it.
4. **Link the trigger** when the entry carries one: the risk goes live when X ships, so X is blocked by
   the follow-up (a native dependency, capability-gated with the `DEPS_UNSUPPORTED` prose-link fallback):

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py link <owner/repo> <follow-up> --add-blocking <X>
   ```

A filed follow-up isn't complete until all its weaves are done.
