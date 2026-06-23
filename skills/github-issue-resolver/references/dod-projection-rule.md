# DoD projection rule

The rule the `github-issue-resolver` applies when projecting a shipped phase's `closes-dod` onto the issue body's `## Definition of done` — extracted here so it doesn't consume the default Read budget at skill-load time. SKILL.md keeps the `#### DoD projection rule` anchor and a one-line intro under §9, and force-`Read`s this file before computing any projection diff. Both the §9 push paths (existing-PR continuation, fresh-PR open) and §4.7 re-entry reconciliation apply this rule with the same inputs.

**Annotation shapes and parser:** see [`../../_shared/dod-annotations.md`](../../_shared/dod-annotations.md) for the closed set of annotation forms (code-phase / operator / single-phase / evaluator-rejected / predecessor), the 1-based top-level-bullet indexing rule, the recognition regex, and the invariants every reader must respect. This skill writes the three `closed by ...` ticked forms — the rest are written by `github-pr-evaluator` (sticky-veto un-ticks) and `github-issue-planner` (revise-mode predecessor un-ticks); they are read here to respect existing annotations during projection.

**Reconciliation source.** The projection's expected DoD-bullet set is computed from two inputs only:

- The PR's `## Phase tracker` (ticked entries only) — the authoritative record of which phases have shipped on this branch.
- The captured phase list from §4.7 — each ticked phase's `closes-dod` indexes.

The union of `closes-dod` across all ticked code-shipping and operator phases is the expected ticked set on the issue body's `## Definition of done`. The resolver never reads the issue body's DoD ticks to decide routing — only to compute the diff between expected and current state.

**Single-phase fallback.** When the plan has no `## Phases` section (single-phase issue per §4.7), or `## Phases` contains a single entry with no `closes-dod`, fall back to "tick every top-level DoD bullet" on the **first push of the run** only. Subsequent §10.6 re-pushes within the same run do not re-tick (the projection has already landed). Re-entry reconciliation (§4.7) re-applies if the first push's `gh issue edit` failed.

**Operator-phase hybrid detection.** Operator and decision-only phases (`kind: operator` | `decision-only`) ship no commits — the resolver doesn't run them. On a re-entry where the next phase is unticked but its `depends-on` is satisfied:

1. **Marker scrape (deterministic).** Look in the issue's comment thread for a comment posted after the prior handoff's timestamp containing `<!-- operator-phase-complete: <N> -->` (where `<N>` is the phase number) on its own line. If exactly one unambiguous match is found, treat the phase as complete — tick the PR's `## Phase tracker` entry as `- [x] (operator phase <N>, applied <ISO-date from the marker comment>)` and project its `closes-dod` onto the issue body using the operator-phase annotation form in "Annotation format".
2. **`AskUserQuestion` fallback.** If no marker is found, or the match is ambiguous (multiple markers for the same phase, marker for a phase that isn't the next expected), present the prior handoff's operator action verbatim and ask: header **"Op phase <N> done?"**, options: **Yes — apply** (tick + project), **No — re-show handoff** (re-emit the operator handoff verbatim and stop the run), **Other** (user explains). Do not silently scrape prose; the marker-or-ask gate is the only deterministic path.

**Annotation format.** Each projection edit replaces the bullet's `- [ ] <text>` with one of:

- Code-shipping phase: `- [x] <text> (closed by phase <N>, commit <short-sha>)`
- Operator / decision-only phase: `- [x] <text> (closed by phase <N>, operator action <ISO-date>)`
- Single-phase fallback (no `## Phases`): `- [x] <text> (closed by commit <short-sha>)`

Use 7-char short SHAs (matching `## Phase tracker` and `../../_shared/handoff-format.md`). The bullet text itself is preserved verbatim; the annotation is appended after the existing text. When a bullet already carries a prior annotation (rare — typically only on plan-revision mid-flight, see "Edge cases"), replace the prior annotation in full rather than appending a second.

**Respect the evaluator's sticky veto.** A bullet annotated `- [ ] <text> (resolver claimed phase <N>, commit <sha>; evaluator rejected: <reason>)` is the evaluator's rejection of a prior projection — the diff in the attributed commit(s) didn't satisfy the bullet. Treat such bullets as **not projected**, even when `Phase tracker × closes-dod` would tick them. The disagreement is resolved by re-planning (the planner reassigns the bullet to a different phase), by a new code phase whose diff actually satisfies the bullet, or by user intervention — never by silent re-ticking on the next push.

**Idempotent diff-only application.** Projection is computed as `expected_set − (currently_ticked_set ∪ rejected_set)`. Only the diff is applied to the body. Never blindly re-tick bullets that are already `- [x]` (clobbering attribution annotations is a regression).

**Worked examples.**

*Example A — multi-phase code phase with `closes-dod: [1, 3]`:*
Plan's Phase 2 carries `closes-dod: 1, 3`. Phase 2's commits land at SHA `abc1234`. After the push, `## Phase tracker` is updated to `- [x] Phase 2 — harness (commit abc1234)`. Then the issue body's `- [ ] First bullet text` becomes `- [x] First bullet text (closed by phase 2, commit abc1234)` and the third bullet flips the same way. Bullet 2 (claimed by Phase 1 if Phase 1 already ticked it, or still `- [ ]` if Phase 4 will close it later) is untouched.

*Example B — single-phase fallback:*
Plan has no `## Phases`. The fresh-PR open pushes the single phase's commits at SHA `def5678`. Single-phase fallback fires: every top-level `- [ ]` under `## Definition of done` flips to `- [x] <text> (closed by commit def5678)`. Subsequent §10.6 re-pushes during review-loop iterations do not re-tick.

*Example C — operator phase with `closes-dod: (none)`:*
Phase 2-measurement is `kind: operator` with `closes-dod: (none)`. On the next re-entry, the marker scrape finds `<!-- operator-phase-complete: 2 -->` posted at `2026-06-04`. The Phase tracker entry becomes `- [x] Phase 2-measurement (operator phase 2, applied 2026-06-04)`. No `gh issue edit` against the issue body — `(none)` means zero bullets to project. The next code phase ships and projects its own `closes-dod`.

**Edge cases.**

- *Plan revision mid-flight* (resolver shipped Phase 1, ticked bullet 3; plan revised so bullet 3 is now claimed by Phase 4): reconciliation never auto-un-ticks. The bullet stays `- [x] <text> (closed by phase 1, commit abc1234)` until Phase 4 ships, at which point projection replaces the annotation with `(closed by phase 4, commit <newer-sha>)`. State summary records `DoD plan-revision drift: bullet 3 was ticked by phase 1 under the prior plan; current plan reassigns to phase 4.`
- *Bullet count drift* (issue body has more or fewer top-level DoD bullets than the plan's max-referenced index): block projection this run, surface in state summary, route back to the planner via the existing `Re-route → planner` handoff (the bullet shift breaks the planner's Dimension-7 invariant).
- *`closes-dod: (none)` phase*: PR Phase tracker still ticks normally; zero `gh issue edit` calls. Log `DoD projection: phase <N> closes (none) — no DoD edits.`
- *Issue with no `## Definition of done` section*: skip projection silently with state-summary line `DoD projection: issue has no \`## Definition of done\` section — projection skipped.` (Multi-phase issues without a DoD section are impossible past planner Dimension-7 review; if detected, treat as bullet-count drift and re-route to planner.)
