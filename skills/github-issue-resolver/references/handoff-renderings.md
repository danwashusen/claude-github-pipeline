# Handoff renderings

The seven rendering shapes the resolver emits as the run's final `## Handoff` block. Pick the one that matches the §11 outcome rubric's classification; copy the shape verbatim, substituting the issue/PR/epic/SHA placeholders with the values from §10.7's `pr-state.json` refresh and §4.7's captured phase list.

Schema, omission rules, and state-marker vocabulary live in [`../../_shared/handoff-format.md`](../../_shared/handoff-format.md).

## Forward — standard or story PR opened / updated

The default code-change outcome. For a story PR under an open epic, the `Issue:` line is replaced with `Story:` and an `Epic:` line is added per `_shared/handoff-format.md`'s Epic variant rules.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · open · base main · review: not run · health: not run · merge: not run

**Next:** evaluate the PR in a fresh session.

    /github-pipeline:github-pr-evaluator #287

**Why:** the evaluator runs the branch-health gate, checks the diff against the issue's acceptance criteria + the plan's locked decisions, posts a formal review, and on a clean APPROVE auto-merges (standard / story PRs) or asks for the merge mode (Epic integration).
```

## Re-route — multi-phase, non-final code phase pushed

A code-shipping phase landed on the draft PR; the plan's `## Phases` still lists unshipped phases. The next session continues the same multi-phase resolution.

```
## Handoff

**Issue:** #640 — Spike: Mitigate Gemini thinking-token truncation · open · feature · plan: ✓ (multi-phase: 2 of 4 phases shipped)
**PR:** #649 — feat(llm): #640 spike harness · draft · base main · review: ✓ at 40f1d36 · health: ✓ at 40f1d36 · merge: not run

**Next:** continue with the next phase in a fresh session.

    /github-pipeline:github-issue-resolver #640

**Why:** the plan's `## Phases` declares 4 phases; this run shipped Phase 2 (`harness PR`) onto the draft. Phase 2's `closes-dod` bullets have been projected onto the issue body's `## Definition of done`. The next planned phase is **Phase 2-measurement** (operator run — see the operator-action handoff if it fires next), followed by **Phase 3 — decision write-up**. The PR stays in draft until every phase has shipped and the evaluator runs its DoD check.
```

## Terminal-with-action — multi-phase, next phase is operator / decision-only

The next phase ships a comment or runs an operator action, not commits. The resolver can't perform the action; surface it verbatim from the plan's `deliverable` so the user (or whoever runs the action) does not have to look it up.

```
## Handoff

**Issue:** #640 — Spike: Mitigate Gemini thinking-token truncation · open · feature · plan: ✓ (multi-phase: 2 of 4 phases shipped)
**PR:** #649 — feat(llm): #640 spike harness · draft · base main · review: ✓ at 40f1d36 · health: ✓ at 40f1d36 · merge: not run

**Next:** run the operator phase, then return to the resolver.

    ./scripts/spike-640.sh
    # then post the per-cell table from build/spike-640-*.log as a comment on #640
    # include this marker on its own line so the next resolver run picks up the
    # operator phase deterministically (otherwise it will fall back to asking you):
    #     <!-- operator-phase-complete: 2-measurement -->

**Then:** once the measurement comment is posted, continue with the following phase in a fresh session.

    /github-pipeline:github-issue-resolver #640

**Why:** the plan's Phase 2-measurement is `kind: operator` — it ships a per-cell measurement comment on the issue, not PR commits. The resolver can't run the harness for you; once you post the measurement comment, Phase 3 (decision write-up) becomes runnable from the resolver. The `<!-- operator-phase-complete: <N> -->` marker is the next resolver's deterministic signal that the operator phase landed — it ticks the PR's `## Phase tracker` and projects the phase's `closes-dod` onto the issue body's `## Definition of done`. Omitting the marker is fine; the next resolver run will ask via `AskUserQuestion` instead of auto-applying.
```

## Forward — multi-phase, last planned phase shipped

Every phase in `## Phases` is ticked in `## Phase tracker`. **Immediately before emitting this handoff, run `gh pr ready <N> --repo <owner/repo>` to flip the PR draft → ready.** Without that flip, the evaluator's §3 draft-PR guard deadlocks the handoff (transcript: `/tmp/671-resolver.md` + `/tmp/671-evaluator.md`). The PR-line's `state: open` marker below reflects the post-flip state and overrides pr-state.json's pre-flip `isDraft: true` for this rendering.

```
## Handoff

**Issue:** #640 — Spike: Mitigate Gemini thinking-token truncation · open · feature · plan: ✓ (multi-phase: 4 of 4 phases shipped)
**PR:** #649 — feat(llm): #640 spike harness · open · base main · review: ✓ at 9f0a112 · health: ✓ at 9f0a112 · merge: not run

**Phases:** all 4 planned phases shipped at 9f0a112; PR flipped to ready for the evaluator (`gh pr ready 649`).

**Next:** evaluate the PR in a fresh session.

    /github-pipeline:github-pr-evaluator #649

**Why:** every phase in the plan's `## Phases` has been ticked on the PR's `## Phase tracker`, and each ticked phase's `closes-dod` bullets have been projected onto the issue body's `## Definition of done` as the phases shipped. The evaluator verifies each projected DoD tick against its attributed phase's diff (per-phase commit ranges from the Phase tracker), runs its branch-health gate and review against the plan's locked decisions, un-ticks any bullet whose attributed diff doesn't actually satisfy it (sticky soft-reject), and — on a clean APPROVE — merges. On a COMMENT (soft-reject) verdict, the evaluator flips the PR back to draft (`github-pr-evaluator` §11) so this resolver can re-enter in continue mode and address the gaps without re-deadlocking on the draft guard.
```

## Forward — Epic integration PR

Same forward direction (→ pr-evaluator), but the `Why:` line calls out the higher merge risk and the canonical-suite escalation so the user knows what pr-evaluator will do differently.

```
## Handoff

**Epic:** #150 — Chat & session UX polish · open · epic · plan: ✓
**Stories:** 5 of 5 closed
**PR:** #300 — Chat & session UX polish (epic #150) · open · base main · review: not run · health: not run · merge: not run

**Next:** evaluate the Epic integration PR in a fresh session.

    /github-pipeline:github-pr-evaluator #300

**Why:** integration PRs land the accumulated diff of every child story onto `main` at once. pr-evaluator's escalation rules fire on `pr_type: epic-integration` — the full canonical test suite runs before merge, the verdict is checked against the epic's `## Definition of done`, and the merge mode is gated (§12b) even on a clean APPROVE.
```

## Re-route → planner

Triggered by §4.6 plan-currency drift or §8 plan-invalidation. The `Why:` line quotes the locked decision verbatim and cites the `file:line` where the contradiction surfaced. If a draft PR was opened before the invalidation surfaced, the PR line carries `state: draft` and stays open so the resolver can continue from the same branch after the plan is refreshed.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: stale
**PR:** #287 — Add CSV export (#142) · draft · base main · review: not run · health: ❌ at abc1234 · merge: not run

**Next:** revise the plan in a fresh session — implementation revealed a locked decision is unbuildable.

    /github-pipeline:github-issue-planner revise #142

**Why:** the plan's `## Architecture decisions` line "<quoted decision>" assumed <X>, but `<path:line>` reveals <Y>. The §4.6 plan-currency check failed (alternatively: §8's plan-invalidation gate fired mid-implementation). Refresh the plan against today's surface before resuming. The draft PR stays open; re-run the resolver in continue mode after the plan revise lands.
```

If no PR was opened yet (§4.6 fired before §8 started), omit the PR line entirely and the resolver continues with `/github-pipeline:github-issue-resolver #142` instead of `continue #287`.

## Re-route → drafter (fitness audit)

Triggered by §4.5 finding a blocker (typically a body claim that references a symbol no longer in the codebase, an acceptance criterion that can't be evaluated, or a contradiction between body sections). The `Why:` line names the dimension and quotes the specific evidence.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✗

**Next:** revise the issue body in a fresh session — the §4.5 fitness-to-implement audit found a blocker.

    /github-pipeline:github-issue-drafter revise #142

**Why:** the body's acceptance criterion "<quoted criterion>" references `<symbol>`, which doesn't exist in the current codebase (closest match: `<symbol>` at `<path:line>`). The criterion needs to be reshaped against today's surface — or the codebase needs a precursor change — before planning can ground in real precedent.
```

## Re-route → drafter (doc conflict)

Triggered by §6 finding that the issue body directly contradicts a project doc the resolver can't reconcile in-skill. Same shape as the fitness re-route; the `Why:` cites the doc section verbatim.

```
## Handoff

**Issue:** #142 — Allow editing submitted forms · open · feature · plan: ✗

**Next:** reshape the issue body in a fresh session — the body contradicts `docs/prd.md`.

    /github-pipeline:github-issue-drafter revise #142

**Why:** `docs/prd.md` §4 says "entries are immutable after submit"; the issue body proposes an edit-after-submit feature. The user chose `Reshape issue` at the §6 doc-conflict gate. The drafter's revise mode either reshapes the body to fit the PRD or routes the conflict back to the user to decide whether the PRD itself should change.
```

## Terminal — non-PR resolution

Comment-only answer, triage-only re-labelling, or abandoned/declined work. No PR was opened; the handoff names the issue's current state and closes the pipeline for this run.

```
## Handoff

**Issue:** #142 — Should we add CSV export? · open · feature · plan: ✗

**Next:** (terminal — no follow-up skill)

**Why:** the resolver posted a clarifying comment in response to the question; no code change was warranted and no PR was opened. The issue stays open in its current state for the user (or a future resolver run) to take forward.
```

For abandoned / declined / stale-issue-close outcomes, name the close reason in the `Why:` line (e.g. "the user declined to open a PR after the §5 existing-work check surfaced a duplicate in #138").
