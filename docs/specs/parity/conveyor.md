# End-to-end conveyor run (S20 DoD box 4) — operator-gated

> Records [implementation.md](../../implementation.md) step **S20**'s fourth DoD box: *"Fresh
> end-to-end conveyor run on the sandbox — draft → research (decline acceptable) → plan → resolve →
> evaluate → merge — with every handoff schema-valid."* This is the **run's last operator gate**,
> and the only DoD box in S20 that is not implementor-completable.

**This is not a parity run.** The eight per-skill parity runs are already recorded and accepted
(`docs/specs/parity/*.md`); v1 is gone from the tree, so there is no v1 leg to twin against. What
box 4 asks for is different and complementary: an **integration acceptance run** proving the five
v2 pipeline stages compose end to end through nothing but GitHub artifacts and the `## Handoff` —
the one property no per-skill scenario could test, because each ran one stage in isolation against
hand-constructed state.

The falsifiable claim: *one issue, drafted from informal feedback, reaches a merged PR on the
sandbox's `main` through five separate sessions, with each session started **only** by
copy-pasting the previous session's handoff command, and every handoff validating against
`skills/_shared/handoff-format.md`.*

## Preconditions

- Sandbox: `https://github.com/danwashusen/gh-pipeline-sandbox` ([SANDBOX.md](../../../tests/SANDBOX.md)).
  Labels, grounding docs, config marker blocks, and the controllable CI gate are already seeded.
- `gh auth status` clean; `git` and `python3` on `PATH`; **no other runtime is needed**.
- A fresh clone of the sandbox per run (`/tmp/s20-conveyor`), on `main`, clean — the resolver and
  evaluator both fail closed on a dirty or diverged root (`ROOT_DIRTY` / `ROOT_DIVERGED`), which is
  correct behavior, not a run failure, but it costs a restart.
- Plugin under test: this branch, via `--plugin-dir <repo root>`.
- **Harness.** Every stage gates on `AskUserQuestion`, which headless `claude -p` cannot render, so
  run each session in the **tmux interactive harness** (the recipe in [`setup.md`](setup.md)
  Scenario 1, with the S18 Scenario-1 `--allowedTools` upgrade):

  ```bash
  cd /tmp/s20-conveyor
  claude --plugin-dir /Users/danwas/Development/Projects/claude-github-pipeline --model opus \
    --allowedTools Bash Read Grep Glob Task TodoWrite Edit Write WebFetch
  ```

  Two tmux gotchas recorded by S19 Scenario 1 and worth re-reading before the first leg: the
  ghost-suggestion input trap, and `Submit` being a **tab** (Right), not a Down row, on the
  question card.
- **One session per stage.** Start a new session for each leg — never continue the previous one.
  Session-per-stage is the property under test; continuing would invalidate the run.

## The subject issue

Draft something small, real, and *buildable in one phase* against the sandbox's toy source — the
run is testing the conveyor, not the difficulty of the work. A single-file behavior change with an
obvious Definition of done is ideal (the sandbox carries `salute_a` / `formatter_a`-style helpers
from earlier parity runs; a new sibling helper, or a defect in an existing one, works).

Avoid: an epic (the epic path is already covered by `planner.md` Scenario 2 and `resolver.md`
Scenario 4 and adds a bootstrap leg that is not what box 4 measures); anything touching
`.ci-force-red` (that fixture is the evaluator's red-CI scenario).

## Legs

Record each leg's result inline. A leg **passes** when its own criteria hold **and** its handoff
validates (checklist below).

### Leg 1 — `drafter`

```
/github-pipeline:drafter <paste the informal feedback here>
```

- [ ] Classifies the feedback (bug / incomplete / feature / epic / question) without asking unless
      signals genuinely conflict; grounds framing in the sandbox `docs/prd.md`.
- [ ] Runs its adversarial review before filing; nothing is filed before the confirmation gate.
- [ ] Files one issue with a `## Definition of done` whose bullets are checkable.
- [ ] Startup performed **exactly one** state-assembly call (`prep_drafter.py`) — [prd.md §9.2](../../prd.md).
- [ ] Handoff points at `/github-pipeline:researcher <N>`.
- **Result:**

### Leg 2 — `researcher` (a decline is a pass)

```
/github-pipeline:researcher <N>
```

- [ ] Applies the currency-risk gate. **Declining is an acceptable outcome** and the likely one for
      a small internal change — the pass condition is that the decline is *stated with its
      reasoning* and that **nothing is posted** (no dossier comment, no marker, no label).
- [ ] If it does research: the dossier carries the `<!-- issue-research:v1 -->` marker on its first
      line, tiered + dated sources, and is validated before posting.
- [ ] Handoff renders `research: ✓` or `research: ✗` from the closed set and points at
      `/github-pipeline:planner <N>`.
- **Result:**

### Leg 3 — `planner`

```
/github-pipeline:planner <N>
```

- [ ] Posts one `<!-- implementation-plan:v1 -->` comment, grounded on an explicitly recorded
      commit SHA, citing sandbox docs by anchor.
- [ ] Gates any genuine tradeoff to the operator; records no open design decision in `## Changes`.
- [ ] Applies the `planned` label and the issue-body plan pointer.
- [ ] Handoff renders `plan: ✓ (<url>)` and points at `/github-pipeline:resolver <N>`.
- **Result:**

### Leg 4 — `resolver`

```
/github-pipeline:resolver <N>
```

- [ ] Audits fitness before building; builds **only** in `.worktrees/<branch>` — `git -C
      /tmp/s20-conveyor status --porcelain` stays **empty throughout** and the root stays on `main`
      ([prd.md §8.1](../../prd.md)).
- [ ] Opens a PR that closes the issue by keyword (`Fixes #<N>` / `Closes #<N>`), with
      `## Doc grounding`.
- [ ] Projects the DoD ticks with annotations from the closed set as the phase ships.
- [ ] Runs its review loop to approval, then flips the PR draft→ready before the handoff.
- [ ] Handoff carries the PR line and points at `/github-pipeline:evaluator <PR>`.
- **Result:**

### Leg 5 — `evaluator` (through merge)

```
/github-pipeline:evaluator <PR>
```

- [ ] Runs the health gate (sandbox CI + the configured checks) and caches it in a
      `<!-- pr-evaluator-health-cache:v1 -->` comment keyed on the head SHA.
- [ ] Verifies each DoD tick against its annotation; un-ticks with a sticky veto on any mismatch
      (none expected here — a clean run is the pass).
- [ ] Posts an `APPROVE` review (never self-approving — the sandbox PR is authored by the same
      account, so **expect and record** the self-review guard's behavior).
- [ ] Merges per the sandbox's `<!-- pr-evaluator-merge-policy -->` (default `ask` → an operator
      gate), with the strategy rules for the PR's shape.
- [ ] Post-merge: the issue closes, the work workspace is torn down and removed, and the root is
      still clean on `main`.
- [ ] Handoff is **terminal** (`(terminal — no follow-up skill)`) with a `Cleanup:` line and a
      `Why:` explaining why the pipeline ends here.
- **Result:**

## Handoff schema validity (the box's explicit clause)

Validate each of the five handoffs against
[`skills/_shared/handoff-format.md`](../../../skills/_shared/handoff-format.md) — the schema is the
contract, and this run is the first time all five are produced in one chain.

For each handoff, check:

- [ ] The block is `## Handoff`, cold-readable without the session transcript.
- [ ] Every state marker is from the **closed set** — no invented synonyms (`open`/`closed`,
      `✓`/`✗`/`stale`, `APPROVE`/`COMMENT`, `squash`/`merge`, the `skipped (…)` reasons).
- [ ] The omission rules hold: no `PR:` line before a PR exists; `Cleanup:` only after a merge ran;
      `Open questions:` only when the issue/plan gated on one.
- [ ] The fenced next-action block carries a command that runs **as printed** — the operator ran it
      verbatim to start the next leg (this is the real test; a handoff that needed editing is a
      defect, not a nit).
- [ ] `Why:` is present and specific.

| Leg | Handoff valid | Command ran as printed | Notes |
|---|---|---|---|
| 1 drafter | | | |
| 2 researcher | | | |
| 3 planner | | | |
| 4 resolver | | | |
| 5 evaluator | | (terminal) | |

## Cross-cutting checks

- [ ] **One state-assembly call per session** ([prd.md §9.2](../../prd.md), [§10](../../prd.md)) —
      each leg's first tool call is its own `prep_*.py`, and no leg assembles state across multiple
      model-mediated calls.
- [ ] **Root untouched, all five legs** — `git -C /tmp/s20-conveyor status --porcelain` empty and
      HEAD on `main` before and after every leg.
- [ ] **No stale-name breakage** — no session printed or ran a `/github-pipeline:github-*` command,
      and no skill tried to invoke a retired script (the S20 removal's live falsification).
- [ ] **Artifacts on the issue/PR** carry their markers verbatim: `<!-- implementation-plan:v1 -->`,
      the optional `<!-- issue-research:v1 -->`, `<!-- pr-evaluator-health-cache:v1 -->`, and the
      DoD annotations.

## Divergences / defects

One row per unexpected behavior. Each must trace to a PRD requirement, a GitHub behavior, a fixture
artifact, or be filed as a defect — an unexplained divergence fails the run (the parity protocol's
rule, applied here too).

| # | Leg | What happened | Adjudication |
|---|---|---|---|
| | | | |

## Cleanup

After the run: `git worktree remove` any leftover workspace, delete the `/tmp/s20-conveyor` clone,
and leave the merged PR + closed issue in place as the run's evidence.

## Go/no-go (operator) — the run's last

- [ ] All five legs pass.
- [ ] All five handoffs are schema-valid and every next-command ran as printed.
- [ ] Cross-cutting checks pass.
- **Operator verdict:**
- **Recommendation (implementor):** the offline half of S20 is complete and green (boxes 1, 2, 3,
  5 — see the S20 implementor report); box 4 is this run. The conveyor's composition has never been
  exercised in one chain, so this is the one place a seam between two accepted skills could still
  surface — most plausibly in a handoff's next-command rendering, which is exactly what the table
  above measures.
