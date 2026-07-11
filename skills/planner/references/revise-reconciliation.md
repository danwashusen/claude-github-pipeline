# Re-plan reconciliation

When a revise runs against an issue with a draft PR that has shipped phases, the body's `## Definition
of done` may already carry projected ticks attributed to phases of the **old** plan (e.g. `- [x] <text>
(closed by phase 2, commit abc1234)`). Annotation shapes and the parser are in
[`../../_shared/dod-annotations.md`](../../_shared/dod-annotations.md). The planner reconciles those
projections against the new plan; the user is engaged at the spine S8 confirm gate to see what's about
to change. The PR's `## Phase tracker` (which phases shipped) rides in `facts.revise.phase_tracker` —
never re-fetched.

### SOFT vs HARD classification

LLM judgment, bounded by structural rules:

**Always HARD:**

- A code-shipping phase ticked in the PR's `## Phase tracker` (shipped) has its `ships`, `deliverable`,
  or `kind` field changed in the new plan.
- The old plan's `## Architecture decisions` has a decision reversed in the new plan **and** that
  decision is reflected in a shipped phase's code.
- A code-shipping phase ticked in the tracker is removed entirely from the new plan.
- A top-level `## Definition of done` bullet's text was edited between the two plan runs **and** that
  bullet was ticked under the old plan.

**Always SOFT:**

- Only `closes-dod` indexes changed (no other structural change).
- Only un-shipped phases changed (forward-looking only).
- Only doc-grounding text was tweaked.
- New phases added beyond what's shipped.

**Judgment call (reason + surface uncertainty):** `## Changes` block text edits (does the shipped diff
still match the new wording?); DoD bullet wording adjustments without structural change. **Lean HARD
when ambiguous** — surprising a visible-progress regression on a SOFT misclassification is worse than
offering "Start fresh" on a borderline-SOFT case the user can decline.

### SOFT-path body reconciliation

Walk the captured body annotations against the new plan's `closes-dod` mappings together:

- **Unchanged attribution** (annotation says phase X, new plan's phase X still claims this bullet) → no
  edit.
- **Reassignment, new phase hasn't shipped** (new plan's phase Y claims it; Y not ticked) → un-tick to
  `- [ ] <text> (resolver claimed phase X, commit <sha>; evaluator rejected: re-plan reassigned to phase
  Y, awaiting its ship)`. Reusing the evaluator-rejection shape is intentional — the resolver's
  projection respects it as a sticky veto until Y ships.
- **Reassignment, new phase has shipped** (Y ticked) → re-attribute, leave ticked: `- [x] <text> (closed
  by phase Y, commit <Y-sha>)`.
- **Phase removed/renumbered** → un-tick to `- [ ] <text> (resolver claimed phase X, commit <sha>;
  evaluator rejected: re-plan removed phase X — needs re-verification)`.
- **Orphaned bullet** (no phase claims this index) → un-tick with the same orphan annotation; surface as
  a Dimension-7 violation in the new plan's verify loop (a re-plan bug the new plan should have caught).
- **Evaluator-rejected bullet** (`- [ ] … evaluator rejected: …`) → **preserve verbatim.** Surface it at
  the S8 confirm so the user sees the rejection alongside the diff. **Do not auto-clear it** even when
  the new plan reassigns the bullet — the rejection is evidence the prior code failed the bullet.

Stage the reconciled body to `<facts.scratch>/issue-body-reconciled.md` and, after the user confirms at
S8, apply it via the single write path:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py edit-body <owner/repo> <issue> \
  "<facts.scratch>/issue-body-reconciled.md"
```

### HARD-path: Start fresh

When the user picks **Start fresh (recommended)** at S8's three-way confirm:

1. **Add a `## Predecessor` section to the new plan comment**, inserted immediately after `## Approach`:

   ```
   ## Predecessor

   This plan supersedes a prior plan that drove PR #<closed-PR> (closed <YYYY-MM-DD>) after a HARD
   re-plan. The closed PR's branch (`<branch-name>`) is preserved for audit and should be deleted by the
   user after the new PR lands. The brief reason for starting fresh: <one-line rationale>.
   ```

2. **Un-tick the issue body's DoD bullets** that were ticked under the old plan, each to the predecessor
   annotation `- [ ] <text> (previously claimed by phase X, commit <sha> on closed PR #<M>)` (per
   `../../_shared/dod-annotations.md`; an evaluator-rejection annotation is rewritten to this predecessor
   form — the closed PR makes the rejection no longer load-bearing). Stage to
   `<facts.scratch>/issue-body-reconciled.md` and apply via `gh_persist.py edit-body`.

3. **Close the superseded PR, with the byte-faithful supersession marker staged first.** This is
   required so the resolver's fresh-PR path fires on the next run: it detects the closed predecessor PR
   + branch by greping closed-PR bodies for the literal phrase `Re-plan superseded this PR`
   (`docs/specs/resolver.md` "Deterministic steps": "Predecessor-PR detection … filtered to `Re-plan
   superseded this PR` bodies") and computes the next `-vN` branch suffix from it — so the phrase is a
   cross-skill contract, not free prose; stage it verbatim. Stage the close comment to
   `<facts.scratch>/close-comment.md`:

   ```
   Re-plan superseded this PR. See updated plan at <new-plan-comment-url>. A new branch and PR will open
   at the next `/github-pipeline:resolver #<N>` run.
   ```

   then close through the single write path:

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py close-pr <owner/repo> <PR#> \
     --comment-file "<facts.scratch>/close-comment.md"
   ```

   This step runs only after the user has already picked **Start fresh** at the S8 three-way confirm —
   the op executes that already-gated decision, it does not gate anything itself. Leave the branch in
   place (the `## Predecessor` reminder is the user's cue to clean up after the new PR lands).

### Worked examples

*SOFT — closes-dod reshuffle:* old Phase 1 `closes-dod: 1, 3`; new Phase 1 `closes-dod: 1` and a new
Phase 4 `closes-dod: 3`. Phase 1 shipped at `abc1234`; Phase 4 hasn't. Body bullet 3 reads `- [x]
Document the export format (closed by phase 1, commit abc1234)`. SOFT reconciliation un-ticks it to
`- [ ] Document the export format (resolver claimed phase 1, commit abc1234; evaluator rejected: re-plan
reassigned to phase 4, awaiting its ship)`.

*HARD — shipped phase's `ships` changed:* old Phase 1 `ships: PR commits implementing a service-layer
abstraction`; new Phase 1 `ships: PR commits implementing protocol-based dependency injection`. Phase 1
shipped at `abc1234`; the shipped diff doesn't match the new `ships`. Classify HARD, recommend Start
fresh: post the new plan with `## Predecessor` naming PR #287 + branch `142-add-csv-export`, un-tick the
three ticked DoD bullets to `- [ ] <text> (previously claimed by phase 1, commit abc1234 on closed PR
#287)`, and close PR #287 via `close-pr` with the staged `Re-plan superseded this PR. See updated plan
at …` comment. The next resolver run detects the closed predecessor and opens a PR on branch
`142-add-csv-export-v2`.
