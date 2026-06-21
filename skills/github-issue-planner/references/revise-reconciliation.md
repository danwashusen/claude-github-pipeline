# Re-plan reconciliation

When step 4 above runs against an issue with a draft PR that has shipped phases, the body's `## Definition of done` may already carry projected ticks attributed to phases of the **old** plan (e.g. `- [x] <text> (closed by phase 2, commit abc1234)`). Annotation shapes and parser are in [`../../_shared/dod-annotations.md`](../../_shared/dod-annotations.md). The planner is responsible for reconciling those projections against the new plan; the user is engaged at step 9's confirm gate to see what's about to change.

### SOFT vs HARD classification

LLM judgment, bounded by structural rules:

**Always HARD:**

- A code-shipping phase in the old plan whose entry is ticked in the PR's `## Phase tracker` (i.e. shipped) has its `ships`, `deliverable`, or `kind` field changed in the new plan.
- The old plan's `## Architecture decisions` block has a decision reversed in the new plan **and** that decision is reflected in a shipped phase's code (extract the shipped phase's diff per the recipe in `github-pr-evaluator` §6's "Per-phase verification mechanics" and reason about whether the diff embodies the decision).
- A code-shipping phase that's ticked in the PR's `## Phase tracker` is removed entirely from the new plan.
- The issue body's `## Definition of done` had a top-level bullet's text edited (between old plan run and new plan run) **and** that bullet was ticked under the old plan. Detect by comparing the old plan's recorded DoD-bullet count + indexes against the current body's count + text.

**Always SOFT:**

- Only `closes-dod` indexes changed in the new plan (no other structural changes).
- Only un-shipped phases changed (forward-looking only).
- Only doc-grounding text was tweaked.
- New phases added beyond what's shipped.

**Judgment call (LLM reasoning + surface uncertainty):**

- `## Changes` block text edits — does the existing diff still match the new wording? Read the shipped phase's diff and reason about it. When uncertain, lean HARD.
- DoD bullet wording adjustments without structural change — is the new wording a refinement of the old, or a meaningful shift? Lean HARD.

When the classification is ambiguous, lean HARD and let the user override at step 9's three-way confirm — surprising visible progress regression on a SOFT misclassification is worse than offering "Start fresh" on a borderline-SOFT case the user can decline.

### SOFT-path body reconciliation

Walk the captured body annotations and the new plan's `closes-dod` mappings together:

- **Unchanged attribution** (annotation says phase X, new plan's phase X still claims this bullet index) → no edit needed.
- **Reassignment, new phase hasn't shipped** (annotation says phase X, new plan's phase Y claims this bullet; Y not in the PR's ticked Phase tracker) → un-tick to `- [ ] <text> (resolver claimed phase X, commit <sha>; evaluator rejected: re-plan reassigned to phase Y, awaiting its ship)`. Reusing the evaluator-rejection annotation shape (per `../../_shared/dod-annotations.md`) is intentional: the resolver's projection logic already respects this as a sticky veto, so the bullet won't be re-ticked on the next resolver run until phase Y actually ships.
- **Reassignment, new phase has shipped** (annotation says phase X, new plan's phase Y claims this bullet; Y is ticked in the PR's Phase tracker) → re-attribute, leave ticked: `- [x] <text> (closed by phase Y, commit <Y-sha>)`. Both phases' diffs exist; the new plan says Y owns this bullet; no visible regression.
- **Phase removed/renumbered** (annotation says phase X, no phase in the new plan has that number) → un-tick to `- [ ] <text> (resolver claimed phase X, commit <sha>; evaluator rejected: re-plan removed phase X — needs re-verification)`. Same sticky-veto reuse as above.
- **Orphaned bullet** (no phase in the new plan's `closes-dod` claims this bullet index) → un-tick with the same orphan annotation; surface as a Dimension-7 violation in the new plan's verify loop (the new plan should have caught this — it's a re-plan bug).
- **Evaluator-rejected bullet** (annotation form `- [ ] ... evaluator rejected: ...`) → preserve verbatim. Surface to the user at the step 9 confirm so they see the rejection alongside the diff and can confirm the new plan addresses it. **Do not auto-clear the rejection annotation** even when the new plan reassigns the bullet to a different phase — the rejection is evidence the prior code didn't satisfy the bullet, and the user needs to make the call on whether the new plan's approach will.

The reconciled body is staged to `/tmp/gh-planner-<N>/issue-body-reconciled.md` and applied via `gh issue edit <N> --repo <owner/repo> --body-file /tmp/gh-planner-<N>/issue-body-reconciled.md` after the user confirms at step 9. Use the same `github-ops` `PERSIST_BODY` route the pointer-line step (step 10) uses if available — fall back to a direct `gh issue edit` otherwise.

### HARD-path: Start fresh

When the user picks **Start fresh (recommended)** at step 9's three-way confirm:

1. **Close the existing PR with a re-plan note.**
   ```bash
   gh pr close <PR#> --repo <owner/repo> --comment "Re-plan superseded this PR. See updated plan at <new-plan-comment-url>. A new branch and PR will open at the next \`/github-pipeline:github-issue-resolver #<N>\` run."
   ```
2. **Un-tick the issue body's DoD bullets** that were ticked under the old plan. Each gets the predecessor annotation (per `../../_shared/dod-annotations.md`):
   ```
   - [ ] <text> (previously claimed by phase X, commit <sha> on closed PR #<M>)
   ```
   Bullets that were already `- [ ]` are unchanged. Bullets carrying an evaluator-rejection annotation get their annotation rewritten to the predecessor form — the closed PR makes the rejection no longer load-bearing. Stage the reconciled body to `/tmp/gh-planner-<N>/issue-body-reconciled.md` and apply.
3. **Add a `## Predecessor` section to the new plan comment.** Insert immediately after `## Approach`:
   ```
   ## Predecessor

   This plan supersedes a prior plan that drove PR #<closed-PR> (closed <YYYY-MM-DD>) after a HARD re-plan. The closed PR's branch (`<branch-name>`) is preserved for audit and should be deleted by the user after the new PR lands. The brief reason for starting fresh: <one-line rationale from the user or the planner's classification>.
   ```
4. **Leave the closed PR's branch in place.** Do not delete it. The reminder in the `## Predecessor` section is the user's cue to clean up after the new PR lands.

The resolver's existing fresh-PR path (§9) handles the next step: on the next `/github-pipeline:github-issue-resolver #<N>` invocation, the resolver sees no open PR, detects the closed predecessor PR + branch via `gh pr list --state closed --search "<issue-number>" --json number,headRefName`, computes the next `-vN` branch suffix (`<issue>-<slug>-v2`, `-v3`, …), opens a fresh PR on that branch, and mirrors the `## Predecessor` section into the PR body. See the resolver's §9 "Fresh-PR branch detection on re-entry" for the branch-suffix logic.

### Worked examples

*SOFT — closes-dod reshuffle:* old plan's Phase 1 has `closes-dod: 1, 3`; new plan's Phase 1 has `closes-dod: 1` and a new Phase 4 has `closes-dod: 3`. Phase 1 already shipped at commit `abc1234`. The body's bullet 3 currently reads `- [x] Document the export format (closed by phase 1, commit abc1234)`. Phase 4 hasn't shipped. SOFT-path reconciliation un-ticks bullet 3 to `- [ ] Document the export format (resolver claimed phase 1, commit abc1234; evaluator rejected: re-plan reassigned to phase 4, awaiting its ship)`. When Phase 4 ships, the resolver's projection re-attributes to phase 4.

*HARD — shipped phase's `ships` changed:* old plan's Phase 1 says `ships: PR commits implementing a service-layer abstraction`; user re-plans because the architecture decided otherwise. New plan's Phase 1 says `ships: PR commits implementing protocol-based dependency injection`. Phase 1 already shipped at commit `abc1234`. The shipped diff doesn't match the new `ships` field. Planner classifies HARD, recommends Start fresh. On Start fresh: PR #287 closes with re-plan note, body's three ticked DoD bullets become `- [ ] <text> (previously claimed by phase 1, commit abc1234 on closed PR #287)`, new plan's `## Predecessor` section names PR #287 + branch `142-add-csv-export` + reminder to delete. Next resolver run opens PR on branch `142-add-csv-export-v2`.
