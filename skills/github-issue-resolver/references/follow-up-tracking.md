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

For each item that the user has approved for filing, spawn a `general-purpose` sub-agent with this prompt (substitute the placeholders at call time):

```
You are filing one GitHub follow-up issue on behalf of the
github-issue-resolver skill. Invoke the `github-issue-drafter` skill,
proxy-confirm the draft, and return the filed issue URL.

Item to file:
- Type: <bug | incomplete-feature | deferred-test | revise-existing>
- Title hint: <one-line summary>
- Description: <2–5 sentences explaining the follow-up>
- Parent reference: PR <URL>, issue #<N>, epic #<E> (if applicable)
- Repository: <owner/repo>

Steps:

1. Invoke the github-issue-drafter skill, passing the description above as
   the informal feedback. State the type hint, title hint, and parent
   reference clearly so the drafter has them at classification time.

2. The drafter will run its own sub-agent review loop (it validates against
   the project's PRD, architecture, constitution, and current code state).
   Let it complete its review-loop passes — don't try to shortcut them.

3. The drafter will reach its step-6 user-confirmation gate ("Show the
   draft and wait for confirmation"). You act as the user at this gate.
   Run three checks:

   a. Type — does the drafter's chosen type match the hint? If the drafter
      decided differently (e.g., classified as `incomplete-feature` when
      you hinted `bug`), accept the drafter's call IF its rationale is
      sound. The drafter sees the description directly and may classify
      better than the hint; only override if the drafter has clearly
      misread the description.

   b. Parent reference — is the parent PR/issue/epic preserved in the
      body's Related-issues section? The drafter's bug, story, feature,
      and incomplete-feature formats all have this section. Without it
      the filed issue is orphaned. If missing, reply to the drafter:
      "Please add the parent reference (PR <URL>, parent issue #<N>) to
      the Related-issues section."

   c. Substance — does the body's What's-wrong / What's-missing /
      Definition-of-done content match the description? If the drafter
      hallucinated detail the description doesn't support, reply with a
      one-sentence correction.

4. Approve if all three checks pass. If any check fails, reply with the
   correction and let the drafter iterate. Cap at 2 correction rounds —
   if the third draft still fails any check, stop and return an error to
   the parent with the latest draft inline so the parent can decide.

5. After approval, the drafter runs `gh issue create` (or `gh issue edit`
   in revise mode) and returns the URL. Capture that URL.

Return only:
- The filed URL (or "error: <reason>" if you stopped at step 4's cap)
- The drafter's final type (in case it overrode the hint)
- A one-line note if you raised any correction before approving

Do NOT file an issue yourself with `gh issue create`. The drafter does
this inside its own flow. Your role is to invoke, proxy-confirm, return.
```

The sub-agent isolates the drafter's verbose work (PRD reading, classification questioning, nested sub-agent review loop) from the resolver's main context. The resolver sees one round-trip per item: input brief → output URL.

## URL weaving — close the loop

Once an item is filed, the resolver does three things with the URL:

1. **Replace temporary `// TODO(?)` markers** in code with `// TODO(#NNN)` referencing the filed issue. Same for skip annotations — rewrite the test framework's skip reason (`XCTSkip("Deferred to ?…")`, Minitest/RSpec `skip "?…"`) to reference `#NNN`. Don't push the iteration without this rewrite; markers without real numbers age into noise.
2. **Update the PR body's `## Follow-ups` section** with a list item per filed issue (use `gh pr edit --body-file` or a one-shot append). Add the section if it doesn't exist. Putting follow-up links in the body (not a comment) makes them durable: comments scroll, the body persists.
3. **Thread the URLs into §11's summary** under a "Follow-ups filed" bullet, separate from the "Procedural notes" bullet that holds the capture-in-PR-body items.

A filed follow-up isn't complete until all three weaves are done.
