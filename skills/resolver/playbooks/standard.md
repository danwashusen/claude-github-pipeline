# Standard issue

Route for `vector.type == standard` (a regular bug / feature / refactor; audit ref and PR base are
both `main`). A single-issue resolution that lands directly on `main` via its PR.

**Run the spine first.** Read [`resolve-spine.md`](resolve-spine.md) and execute it end to end
(distill → audit → plan-gate → doc grounding → phases → code + review loop → per-phase push + DoD
projection → follow-ups). `facts.audit_ref` is `main`; the work workspace's `base_ref` is `main`; there
is no read workspace beyond the audit one (prep omits `read_workspaces` when `audit_ref == main` and no
second view is needed). Everything below runs only after the spine returns; on a re-route exit, emit the
matching re-route handoff instead.

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md) and match the run's
outcome to its rubric:

- **Forward — standard PR opened / updated** (default code outcome): `Issue:` line, `PR:` line
  (`base main · review: not run · health: not run · merge: not run` — the resolver runs none of the
  evaluator's checks), `Next: /github-pipeline:evaluator #<PR>`, `Why:`.
- **Multi-phase** — pick **non-final code phase pushed** (`plan: ✓ (multi-phase: K of M …)`, PR stays
  draft, `Next: /github-pipeline:resolver #<N>`), **operator/decision-only next phase** (surface the
  `deliverable` + the `<!-- operator-phase-complete: <N> -->` marker verbatim), or **last planned phase
  shipped** (PR flipped ready, `Next: /github-pipeline:evaluator #<PR>`). **Every one of these three
  shapes still carries `review: not run · health: not run`** — the review loop and the §8 gate ran
  internally this session, but that is not what those two fields mean (they are the evaluator's,
  populated only once it acts); do not render an off-closed-set glyph for "ran internally."
- **Re-route → planner** (plan drift / thread-supersedes-plan): `plan: stale`, `Next:
  /github-pipeline:planner revise #<N>`; `Why:` quotes the locked decision + `file:line`.
- **Re-route → drafter** (audit blocker or doc conflict): `Next: /github-pipeline:drafter revise #<N>`;
  `Why:` names the dimension + quotes the evidence (or the doc section, for a doc conflict).
