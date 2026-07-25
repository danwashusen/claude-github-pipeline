# Parity — evaluator (v1 `github-pr-evaluator` → v2 `evaluator`)

> Records the [implementation.md](../../implementation.md) **S7** parity run per the
> [parity protocol](../../implementation.md) (`## The parity protocol`) and [prd.md §9.5](../../prd.md).
> The offline work (router + playbooks + references + tests) landed in S7's implementor pass; the
> **four live scenarios below are operator-gated** — run them on the sandbox
> ([SANDBOX.md](../../../tests/SANDBOX.md)) and fill each result section. A v1 skill directory is
> deleted only after its v2 replacement passes this protocol (S20); the S8 go/no-go **requires this
> run recorded with zero unexplained divergences**.

## Line-count metric ([prd.md §10](../../prd.md); S7 DoD box 7)

The success metric: the prompt a session loads (router + the one playbook it executes) is **at most
half** the v1 `SKILL.md` line count. v1 `github-pr-evaluator/SKILL.md` = **971 lines**
([baseline.md](../baseline.md) §1) → bar = **485**.

| File | Lines |
|---|---:|
| `skills/evaluator/SKILL.md` (router) | 103 |
| `skills/evaluator/playbooks/evaluate-spine.md` (the shared spine — largest) | 320 |
| `skills/evaluator/playbooks/story.md` | 95 |
| `skills/evaluator/playbooks/epic-integration.md` | 65 |
| `skills/evaluator/playbooks/standard.md` | 51 |
| **router + largest playbook (the loaded set)** | **423** |

**423 ≤ 485** ✅. Router **103 ≤ 150** ✅ (architecture.md §9 size bar). References are read
on-demand and are not part of the loaded-prompt metric; recorded for completeness:
`handoff-renderings.md` 158, `test-selection-sub-agent.md` 144 (carried from v1),
`health-cache-comment.md` 56, `review-comment.md` 50, `epic-delivery-log.md` 29.

Every routed session loads the router (103) + `evaluate-spine.md` (320) + exactly one thin routed
playbook (51–95) — so the true per-session load is **≤ 103 + 320 + 95 = 518** when the routed
playbook is `story.md`. The DoD's metric is *router + largest playbook* = 423; the additional thin
routed playbook a story session also reads is a deliberate spine+variant split (see the split
rationale below), and each individual document still fits one default `Read`.

## Playbook split (the §5-bar decision the Work says to record)

architecture.md §5 "parameterize before you playbook": a playbook exists only for flows that differ
in **actions taken**, not in values. The evaluator's PR-type differences that are *values* (base ref,
merge strategy, escalation, merge-policy default) are carried as **facts** from `prep_evaluator.py`
and consumed as data in the shared spine — never branched on. The split landed as:

- **`playbooks/evaluate-spine.md`** — the pre-merge flow every route runs (identify → health gate →
  five-dimension evaluation → verdict → merge strategy → merge-approval gate → merge). PR-type is a
  fact here, not a branch. Every routed playbook opens by reading the spine.
- **`playbooks/standard.md`** — post-merge: terminal, residual follow-up filing, cleanup.
- **`playbooks/story.md`** — post-merge: the three distinct **actions** a story merge requires
  (close the story, tick the epic checkbox, append the delivery log) because a story PR merges into a
  non-default branch and GitHub fires none of them automatically; then the forward handoff.
- **`playbooks/epic-integration.md`** — the always-gated merge, full-suite escalation (a fact fed to
  the test-selection sub-agent), the epic-DoD historical walk (the spine's no-annotation fallback,
  which fires naturally on an epic body), and the load-bearing `## Follow-ups` re-adjudication; then
  the terminal handoff.

Why a spine + three variants rather than one file per PR type (which would each restate the whole
evaluate flow) or a single file with `if story … else …` (banned by §5)? The pre-merge evaluate flow
is identical across PR types up to *facts*; only the **post-verdict actions** diverge. A single shared
spine keeps that flow in one place (no triplication, no drift) and satisfies "one route per session"
(the router picks exactly one variant; the variant pulls in the one shared spine and nothing else).
The three variants contain **zero PR-type conditionals** — the route *is* the branch — verified by
`tests/test_evaluator_routing.py::RouterStructuralBarTests`.

## Contract-token census ([global DoD](../../implementation.md) skill-cutover clause)

The S1 baseline census ([baseline.md](../baseline.md) §2) was re-run against the identical command
after this cutover. Result: **zero drops vs baseline**, and every addition is a legitimate
`skills/evaluator/` contract token (the marker strings the skill reads/writes —
`<!-- pr-evaluator-health-cache:v1 -->`, `<!-- epic-delivery-log:v1 -->`, `<!-- implementation-plan:v1 -->`,
`<!-- open-question-links:v1 -->`, `<!-- pr-evaluator-test-target -->`, `<!-- worktree-teardown -->`,
`<!-- claude-code-stack-profile -->` — plus the v2 handoff namespace strings `github-pipeline:planner`
/ `github-pipeline:resolver` and §-anchors). New `skills/evaluator/` files introduce **no**
`github-ops`, **no** `GATHER_*`/`PERSIST_*` op names, **no** `github-pipeline:github-*` v1 namespace
strings, and **no** `§P` IDs.

**Deliberate-retirement note (deferred to S20).** No v1 token retires at S7 — the v1
`skills/github-pr-evaluator/` directory is untouched and still contributes all its baseline census
rows (`GATHER_ISSUE`/`GATHER_PR`/`PERSIST_COMMENT`/`PERSIST_ISSUE`, `github-pipeline:github-ops`, its
`§`-anchors, and the `github-pipeline:github-issue-planner`/`-resolver` handoff strings). Those are
the tokens that **will** legitimately retire when S20 deletes the v1 directory after this v2
replacement passes the live parity below; the S20 census diff will account for that drop then.

## Grep gates (S7 DoD box 3) — recorded green

Run over `skills/evaluator/`:
- `github-ops` — **0 hits**.
- Old skill-invocation namespace (`github-pipeline:github-*`) — **0 hits**.
- v1 op names (`GATHER_*` / `PERSIST_*`) — **0 hits**.
- Raw `gh` persist/gather writes (`gh issue|pr create|edit|comment|review|close|reopen`, `gh api … DELETE`) — **0 hits**.
- `§P` IDs (resolver-local; must not appear) — **0 hits**.

The only raw `gh` commands present are the **merge executor** `gh pr merge` and the PR-state toggles
`gh pr ready --undo` (draft-flip) + the reads `gh pr checks --watch` / `gh pr view`. `gh pr merge` has
**no `gh_persist.py` op** (no persist subcommand covers a merge, and no S-step adds one) and is the
step the spec explicitly names as the merge executor ([evaluator.md](../evaluator.md) "Deterministic
steps": "the exact `gh pr merge` invocation"). It is therefore a documented exception to the
raw-write gate, not a bypass of an existing script — the gate targets persist/gather ops that *do*
have scripts. Three frozen artifact-footer strings (`_Cached by `github-pr-evaluator`._`, `_Recorded
by `github-pr-evaluator`._`) are preserved verbatim as [prd.md §7](../../prd.md) compatibility tokens
(v1-written comments carry them; cross-version readers must recognize them) — they are attribution
text inside a comment body, not a skill-invocation name.

## Operator-gate coverage (S7 DoD box 5)

Every operator gate in [evaluator.md](../evaluator.md) "## Operator gates" is present in the v2 skill
(all in the spine unless noted):

| S1-spec gate | v2 home |
|---|---|
| Health-check config missing | spine S3.3 (`header: "Health check"`) |
| CI vs local discrepancy | spine S3.5 (`header: "CI vs local"`) |
| Merge-approval decision gate | spine S7-gate step 2 (`header: "Approve PR"`) |
| Unresolved `/review` issues | spine S5 "Other gates" (`header: "Open review"`) |
| Squash type ambiguous | spine S6 squash-subject ("if the two disagree, confirm with the user") |
| Epic-integration DoD not evidently satisfied | spine S5 "Other gates" |
| `REVIEW_REQUIRED` owed to a named reviewer | spine S5 "Other gates" (`header: "Reviewer"`) |
| No `closingIssuesReferences` | spine S2 (`header: "Issue link"`) |
| Conflicting acceptance criteria across ≥2 linked issues | spine S2 |
| Branch protection non-403, stricter than expected | spine S6 |

No gate's absence traces to a PRD § — all are present.

---

## Live parity scenarios (operator-gated — TODO)

Run each per the [parity protocol](../../implementation.md) steps 1–5 on the sandbox: construct the
target state, run **v1** `github-pr-evaluator` capturing every GitHub write / gate / handoff / turn
count, reset (or use a twin — the story and epic-checkbox flows mutate a shared parent, so **twin the
parent subtree**, e.g. two single-story epics), run **v2** `evaluator` on the same state, then compare:
persisted artifacts **schema-identical** (same marker line, section/heading set + order, structured
fields; confirmed by cross-consumption), same genuine decisions gated, handoff validates against the
shared schema, startup ≤ one state-assembly call. List divergences; each must trace to a PRD
requirement or be a filed defect. **Unexplained divergence fails the run.**

### Scenario 1 — Standard PR: approve + merge

Target: a standard PR (base `main`) that satisfies its issue on all five dimensions, green health,
merge-policy `auto` (or operator Approve at the `ask` gate). Expected v2: health-cache comment posted,
`--approve` review, squash merge into `main`, terminal handoff (`merge: squash → main@<sha>`), residual
follow-ups filed if any, workspace torn down + removed.

> **Run recorded 2026-07-05** on `danwashusen/gh-pipeline-sandbox`. **Twin fixture:** two equivalent
> standard PRs, each adding a `greet(name)` fix and `Closes`-linking its own seeded `bug` issue, base
> `main`, green CI (no `.ci-force-red`). Twin-A → v1 = PR #9 / issue #7; Twin-B → v2 = PR #10 / issue
> #8 (rebased onto post-twin-A `main` so both PRs were `CLEAN`/single-commit at eval time). Both runs
> headless: `claude -p "/github-pipeline:<skill> <PR>" --plugin-dir <this branch> --model opus
> --permission-mode bypassPermissions`, cwd = a fresh sandbox clone (v2 clone created after twin-A's
> merge to avoid `ROOT_DIVERGED`). Made hands-free by a **per-run** `- standard: auto` merge-policy
> override (SANDBOX.md-sanctioned per-run block edit; local-commit-only, never pushed). Two constraints
> shaped the run and apply **identically to both versions**, so neither breaks parity: (a) single-account
> sandbox ⇒ both PRs self-authored ⇒ both correctly downgraded `--approve`→`--comment` (GitHub 422s
> self-approve), verdict APPROVE and the squash-merge proceeding either way; (b) CI-green ⇒ both skills
> take the local-gate-skip short-circuit (v1 §5.3, v2 spine S3.2), so the missing `pyflakes`/`pytest`
> never ran. **Seed defect noted (not a parity divergence):** the sandbox's seeded
> `<!-- pr-evaluator-merge-policy -->` block uses bare `standard: ask` lines, but *both* v1 (SKILL.md:481)
> and v2 (`prep_evaluator._MERGE_POLICY_LINE_RE`) require the `- standard: ask` list-item form — so as
> seeded the block parses to empty and every type defaults to `ask`; SANDBOX.md's §3 seed recipe should
> emit the list form.

- [x] v1 run captured (writes / gates / handoff / turns): **0 gates.** Writes: health-cache comment
      (`issuecomment-4884932829`), approval review (`COMMENTED`, self-authored), squash-merge →
      `main@26e6046` (subject `fix: greet() returns a personalized greeting (#9)`), issue #7 auto-closed,
      branch deleted. Terminal handoff (`merge: squash → main@26e6046` · `review: APPROVE (self-authored →
      --comment)` · Cleanup `no worktree for this branch; scratch dir purged`). ~23 turns, ~7 min, $2.30;
      **4 `github-pipeline:github-ops` sub-agents**; startup state assembled via **2** `GATHER` calls
      (PR #9 + issue #7).
- [x] v2 run captured: **0 gates.** Writes: health-cache comment (`issuecomment-4884968411`), approval
      review (`COMMENTED`, self-authored), squash-merge → `main@edf293a` (subject `fix: greet() returns a
      personalized greeting (#10)`), issue #8 auto-closed, branch deleted. Terminal handoff (`merge: squash
      → main@edf293a` · `review: APPROVE` · Cleanup `worktree removed; teardown ran; scratch dir purged`).
      ~25 turns, ~6.7 min, $1.85; **0 sub-agents** (direct `prep_evaluator.py` + `gh_persist.py` calls —
      the §9.1 "no intermediary relay" design). Startup state assembled via **1** `prep_evaluator.py` call
      (+ 1 pre-merge `--refresh`, the router-prescribed currency re-check, not a second assembly).
- [x] Artifacts schema-identical (health-cache comment, review): **Yes.** Health-cache: same marker
      `<!-- pr-evaluator-health-cache:v1 -->`, first-line state token `all green ✅`, `SHA:` (full) / `TIER:
      full` / `Source:` fields in order, a 2-row check table, and the **frozen** `_Cached by
      `github-pr-evaluator`._` footer — both preserve the v1 attribution token despite the v2 rename.
      Review: both prose bodies lead with a health line → `## Verdict: APPROVE` → five-dimension assessment
      (scope / DoD / native-blocked-by / doc-grounding / plan-adherence) → self-authored footer; **neither**
      emits `## DoD verification` (historical DoD path — no projection annotations — correct omission).
      Squash subjects schema-identical: `fix: <summary> (#<PR>)`, the title's issue-ref `(#N)` stripped and
      the PR-ref appended (the double-suffix rule) → `(#9)` / `(#10)`.
- [x] Cross-consumption confirmed (v1 reader ↔ v2 artifact): **Yes — both directions, mechanically.**
      v2's `prep_evaluator._health_cache_fact` on v1's comment → `{sha: 768d534…, hit: True}`; v1's §5.2
      parse rules on v2's comment → `{state: all green ✅, HEALTH_OK: true, sha: 7f8e119, tier: full}`.
      Each version's health-cache comment is read correctly by the other's reader.
- [x] Gates match; handoff schema-valid; ≤1 state-assembly call: **Yes.** Gates 0 = 0 (both hands-free
      under `auto`). v2 handoff validates against `_shared/handoff-format.md`: `Issue:`/`PR:` field order,
      all closed-set markers correct (`closed`, `merged`, `review: APPROVE`, `health: ✅ at 7f8e119`,
      `merge: squash → main@edf293a` with 7-char SHAs), `research:` omitted (never researched), terminal
      `(terminal — no follow-up skill)` — matching `docs/specs/examples/handoff-evaluator.md`. Startup
      state assembly = **1** `prep_evaluator.py` call (§9.2 satisfied; the `--refresh` re-derives only
      volatile PR/CI facts before merge).
- [x] Divergences (each traced to a PRD § or filed as a defect):
  - **(explained → §8.3 / §9.2) Cleanup line.** v1 `no worktree for this branch` vs v2 `worktree removed;
    teardown ran; scratch dir purged`. v2's `prep_evaluator.py` always provisions the PR-head workspace
    (`ensure --work`) as part of one-shot state assembly (§9.2 / §8.3 workspaces), so there is always a
    worktree to tear down + remove; v1 lazily skips worktree creation on the CI-green short-circuit. Both
    correct for their architecture; v2 matches the `standard.md` Cleanup shape.
  - **(free prose, schema-identical) Handoff `review:` annotation.** v1 `APPROVE (self-authored →
    --comment)` vs v2 bare `APPROVE`. Both carry the `APPROVE` closed-set marker; v2's bare form is the
    strictly schema-compliant one (v1's parenthetical is free text outside the closed set).
  - **(free prose, non-consumed) Health-cache `Source:` value.** v1 `GitHub statusCheckRollup (sandbox-ci
    / gate)` vs v2 `COMMANDS.md / CLAUDE.md` (the frozen template's literal default). Same `Source:` field
    (schema-identical); the value is free prose read by no consumer (prep parses only `SHA:`; v1 parses
    state + SHA + TIER). On the CI-green path v1's value is marginally more accurate; a low-severity
    template nit for the v2 `references/health-cache-comment.md`, not a compatibility break.
  - **(test-harness artifact, not v1/v2 behavior)** v2 surfaced a phantom `CLAUDE.md` merge-policy delta
    in a two-dot `main..HEAD` scope diff — an artifact of the per-run local-only `- standard: auto`
    commit (clone `main` carries it; the PR head does not). v2 correctly diagnosed it as a fork-point
    artifact (`changedFiles: 1`; the branch commit doesn't touch `CLAUDE.md`; squash applies only
    `merge-base..head`) and did **not** reject on it. No persisted-artifact impact.

**Verdict: PASS.** Schema-identical persisted artifacts (cross-consumable both directions), identical gate
set (0), schema-valid v2 handoff, one startup state-assembly call. Every divergence traces to a PRD § (§8.3
/ §9.2), is free prose within the shared schema, or is a test-harness artifact — **no unexplained
divergence**. (One shared cosmetic: both skills render `plan: none` where `handoff-format.md`'s inline
`plan:` set is `✓ | ✗ | stale`; identical across versions, so parity-neutral — a pre-existing baseline
behavior, not a v2 regression.)

### Scenario 2 — Story PR: merge (delivery-log append + epic checkbox)

Target: a story PR (base `epic/<N>-<slug>`) under a single-story epic (**twin** it — two epics — for
the destructive checkbox/log mutation). Expected v2: after merge, story issue closed
(`--reason completed`), epic `## Stories` checkbox ticked, `<!-- epic-delivery-log:v1 -->` appended
(shape from the merged diff), forward handoff to `/github-pipeline:planner` (more stories) or
`/github-pipeline:resolver` (last sibling).

> **Run recorded 2026-07-05** on `danwashusen/gh-pipeline-sandbox`. **Twin fixture (parent twinned):** two
> single-story epics, each `epic #<E>` → one `story #<S>` → one story PR (base `epic/<E>-s2-twin-<x>`, head
> `story/<S>-farewell-<x>`) adding an identical `farewell(name)` helper to its own `src/greeter_<x>.py`, so v1
> mutates epic-A's checkbox+log and v2 mutates epic-B's independently. **Twin-A → v1** = epic #11 / story #13 /
> PR #15 (`epic/11-s2-twin-a`); **Twin-B → v2** = epic #12 / story #14 / PR #16 (`epic/12-s2-twin-b`). Both runs
> headless: `claude -p "/github-pipeline:<skill> <PR>" --plugin-dir <this branch> --model opus
> --permission-mode bypassPermissions`, cwd = a fresh sandbox clone (one per run). Three setup constraints shaped
> the run and apply **identically to both versions**, so none breaks parity: (a) a **per-run `- story: auto`**
> merge-policy override (SANDBOX.md-sanctioned local-commit-only block edit, never pushed) made the story merge
> hands-free — same device as S1's `- standard: auto`; (b) GitHub does **not** populate `closingIssuesReferences`
> from a `Closes #<story>` keyword on a **non-default-base** PR (verified: PR #15 base `epic/11-…` → empty; the
> default-base S1 PR #9 → `#7`), so the story→issue link was established with a **pure-CLI base-swap** (point base
> at `main` → GitHub populates the ref → point base back to the epic branch → the ref **persists**). This mirrors
> the manual Development-panel link / the "Name the issue" gate answer a real operator supplies — the invariant's
> "linkage is recorded but the close never auto-fires" (`docs/specs/evaluator.md` §13). Without it, both v1 and v2
> would hit the identical "No `closingIssuesReferences`" gate (spine S2 / v1 §"When to ask"). (c) single-account
> sandbox ⇒ both PRs self-authored ⇒ both correctly downgraded `--approve`→`--comment` (GitHub 422s self-approve),
> verdict APPROVE and the squash merge proceeding either way. Both stories carry an unticked, un-annotated DoD →
> both took the **historical walk-the-item** DoD path (no `## DoD verification` section — correct omission).

- [x] v1 run captured (writes / gates / handoff / turns): **0 gates.** Writes: health-cache comment
      (`issuecomment-4885133981`), approval review (`COMMENTED`, self-authored, `pullrequestreview-4630881075`),
      squash-merge → `epic/11-s2-twin-a@5f7ee9f` (subject `feat: add farewell(name) to greeter_a (#15)`), story
      #13 closed `--reason completed`, epic #11 `## Stories` ticked `- [x] #13` (explicit `gh issue edit`,
      userContentEdit 06:48:36), delivery-log created on epic #11 (`issuecomment-4885141304`). Forward handoff →
      `/github-pipeline:github-issue-resolver #11` (last sibling → Epic-integration mode). ~25 turns, ~8.7 min,
      $3.25; **6 `github-pipeline:github-ops` sub-agents**; startup state assembled via **3** GATHER calls
      (`GATHER_PR` #15 + `GATHER_ISSUE` #13 + `GATHER_ISSUE` #11). A **transient `503`** on `gh pr merge` (the
      merge had already landed server-side; v1 confirmed `MERGED`/`5f7ee9f` before any retry and deleted the
      lingering `story/13-farewell-a` branch by hand since `--delete-branch` didn't fire) — infra artifact,
      handled correctly, not a parity divergence.
- [x] v2 run captured: **0 gates.** Writes: health-cache comment (`issuecomment-4885769777`), approval review
      (`COMMENTED`, self-authored), squash-merge → `epic/12-s2-twin-b@2a2059c` (subject `feat: add farewell(name)
      to greeter_b (#16)`), story #14 closed `--reason completed`, epic #12 `## Stories` shows `- [x] #14`
      (**no `edit-body` write** — GitHub auto-ticked the task-list item on story close; Action 2 re-fetched, saw
      `[x]`, and skipped per its idempotency guard), delivery-log created on epic #12 (`issuecomment-4885775766`).
      Forward handoff → `/github-pipeline:resolver #12` (last sibling → Epic-integration mode). ~29 turns, ~6.9
      min, $1.90; **0 sub-agents** (direct `prep_evaluator.py` + `gh_persist.py` — the §9.1 "no intermediary
      relay" design). Startup state assembled via **1** `prep_evaluator.py` call (+ 1 pre-merge `--refresh`, the
      router-prescribed currency re-check, not a second assembly).
- [x] Artifacts schema-identical (delivery-log line, epic-checkbox edit, review): **Yes.** **Delivery-log:** both
      lead with marker `<!-- epic-delivery-log:v1 -->` (first line), `**Epic delivery log** — #<E> <title>`, then
      one `- #<story> — delivered: <shape> @ \`<sha>\` (PR #<M>, merged 2026-07-05)` line — v1 `#13 … \`farewell(name)\`
      → personalized farewell string in \`src/greeter_a.py\` @ \`5f7ee9f\` (PR #15, …)`, v2 `#14 … \`farewell(name)\`
      in \`src/greeter_b.py\` (returns \`"Goodbye, {name}!"\`, personalized) @ \`2a2059c\` (PR #16, …)`. Both name the
      **actual merged public surface** (`farewell(name)` + file) derived from the diff per the contract; the
      `<shape>` prose and a header/entry blank line (v1 has one, v2 none) are free-form. **Epic-checkbox edit:**
      both epic bodies end at `- [x] #<story>` in `## Stories` (identical). **Review:** both are `COMMENTED`
      (self-authored downgrade), lead with a health line, carry `Verdict: APPROVE` + the five-dimension assessment
      (scope / DoD / native-blocked-by / doc-grounding / plan-adherence) + story/epic-context note + self-authored
      footer; **neither** emits `## DoD verification` (historical DoD path — correct omission). Squash subjects
      schema-identical: `feat: <summary> (#<PR>)`.
- [x] Cross-consumption confirmed (the planner reads the v2 delivery-log line; a v1 delivery-log is readable by
      v2): **Yes — both directions, mechanically.** A contract-faithful reader (the planner's read: locate by
      `startswith("<!-- epic-delivery-log:v1 -->")`, parse each `- #<story> — delivered: … @ \`sha\` (PR #M, merged
      date)` line per `_shared/epic-delivery-log.md`) parses **both** logs to one structured entry each — v2's
      epic #12 log → `{story: 14, shape, sha: 2a2059c, pr: 16, date}` (the planner reads the v2 line), and v1's
      epic #11 log → `{story: 13, shape, sha: 5f7ee9f, pr: 15, date}` (readable by the same version-agnostic
      reader the v2 evaluator uses before appending). The reader is shared, so consumability is symmetric.
- [x] Story closed + checkbox ticked + log appended, each idempotent on a re-run: **Yes** (verified by re-invoking
      each action's v2 script on twin B). **Action 1 (close):** re-running `gh_persist.py close … 14 --reason
      completed` on the already-closed story returns `closed: true`, exit 0, no error — safe no-op; story stays
      `CLOSED/COMPLETED`. **Action 2 (checkbox):** the box is already `- [x] #14` (GitHub auto-tick + the skill's
      note-and-skip), and re-PUT of the identical body via `gh_persist.py edit-body` leaves exactly one `[x] #14`
      (no duplicate). **Action 3 (delivery-log):** delete-and-repost via `gh_persist.py comment … --delete-marker-id
      <numeric-id>` leaves exactly **one** comment with **one** `#14` entry (update-in-place). Note: `--delete-marker-id`
      requires the **numeric** REST comment id — `gh_gather.py:268-272` surfaces the marker's numeric id for exactly
      this DELETE endpoint; passing the GraphQL node id instead leaves a stale duplicate (`gh_persist.py:377-388`
      warns). The live run's Action 3 was a fresh **create** (single-story epic), so the delete-and-repost path was
      exercised **post-hoc** here, not during the run.
- [x] Gates match; handoff schema-valid; ≤1 state-assembly call: **Yes.** Gates 0 = 0 (both hands-free under the
      per-run `story: auto`; prep raised no `needs_decision`). Both handoffs match the **"story merged — last
      sibling"** rendering (`references/handoff-renderings.md`): `Story:` (`closed · story`) + `Epic:` (`open (1 of
      1 stories closed)`) + `PR:` (`merged · base epic/<E>-s2-twin-<x> · review: APPROVE · health: ✅ at <7-sha> ·
      merge: squash → epic/<E>-s2-twin-<x>@<7-sha>`) + `Cleanup:` + forward `Next:` to the resolver in
      Epic-integration mode + `Why:`; all closed-set markers valid. Startup state assembly = **1** `prep_evaluator.py`
      call for v2 (§9.2 satisfied; the pre-merge `--refresh` re-derives only volatile PR/CI facts). v1's 3-call
      `GATHER` assembly is its own architecture and not the §9.2 bar.
- [x] Divergences (each traced to a PRD § or filed as a defect):
  - **(explained → §9.1 / GitHub behavior) Epic-checkbox write mechanism.** v1 **explicitly** writes `- [x] #13`
    via `gh issue edit` (userContentEdit at 06:48:36); v2 issues **no** `edit-body` — GitHub auto-ticks the
    `- [ ] #<story>` task-list item when the referenced story closes (verified: epic #12 has no post-fixture
    userContentEdit yet shows `- [x] #14`), so v2's Action 2 re-fetches, sees `[x]`, and skips per `story.md`'s
    "already `[x]` → note and skip" guard. **Identical `- [x] #story` artifact.** v2's skip is the strictly-more-
    idempotent behavior and directly exercises the Action-2 idempotency guard; both are correct.
  - **(explained → §8.3 / §9.2) Cleanup line — worktree.** v1 `no worktree (CI green — local gate short-circuited)`
    vs v2 `worktree removed; …`. Same as S1: v2's `prep_evaluator.py` always provisions the PR-head workspace
    (`ensure --work`) as one-shot state assembly, so there is always a worktree to remove; v1 lazily skips
    worktree creation on the CI-green short-circuit. Both correct for their architecture; v2 matches `story.md`'s
    Cleanup shape (`worktree removed; epic checkbox ticked; delivery log …; story issue closed; scratch purged`).
  - **(deliberate rename, schema-valid) Handoff next-command namespace.** v1 forwards to
    `/github-pipeline:github-issue-resolver #11`, v2 to `/github-pipeline:resolver #12` — the v1→v2 skill rename.
    Both are the resolver in Epic-integration mode; parity-neutral.
  - **(free prose, schema-identical) Handoff `review:` annotation.** v1 `APPROVE (self-authored → comment)` vs v2
    bare `APPROVE`. Both carry the `APPROVE` closed-set marker; v2's bare form is the strictly schema-compliant one
    (v1's parenthetical is free text). Same as S1.
  - **(free prose / free rendering) Health-cache non-consumed fields.** Same marker, first-line state token `all
    green ✅`, and full `SHA:` in both (the only field a consumer parses — `prep` reads `SHA:`). Free-prose diffs:
    `Source:` v1 `GitHub statusCheckRollup` vs v2 `COMMANDS.md / CLAUDE.md` (frozen template default — same as
    S1); v1 **omits** the `TIER:` line (adds a prose note) while v2 emits `TIER: full` (schema: `TIER` optional,
    absent → read as `full` — both valid); the check table columns differ (v1 `Check|Status|Source`, v2 the frozen
    `Command|Status|Duration`) on the CI-green path. Read by no consumer beyond `SHA:`; not a compatibility break.
  - **(free prose) Review lead ordering.** v2 leads with the `**Health:**` line then `## Verdict: APPROVE` (spine
    S5 "start the body with `HEALTH_BODY`"); v1 leads with `**Verdict: APPROVE**` then the health line. Same
    element set (health + verdict + five dimensions + self-authored footer); free-prose arrangement.
  - **(architecture, metrics not artifacts) Sub-agent topology / startup calls.** v1 = 6 `github-ops` sub-agents +
    some raw main-loop `gh`; v2 = 0 sub-agents (direct scripts, §9.1). Startup: v1 = 3 `GATHER` calls, v2 = 1
    `prep` (+1 pre-merge `--refresh`). Same shape as S1; v2 meets §9.2's ≤1, v1's multi-call assembly is its own
    architecture. No persisted-artifact impact.
  - **(shared cosmetic, parity-neutral) `plan: none`.** Both skills render `plan: none` on the `Story:` line where
    `handoff-format.md`'s inline `plan:` set is `✓ | ✗ | stale` (the fixture stories carry no plan). Identical
    across versions — a pre-existing baseline behavior, also noted in S1, not a v2 regression.

**Verdict: PASS.** Schema-identical persisted artifacts — delivery-log line, epic `## Stories` checkbox, and the
review — cross-consumable in both directions by the shared reader; the three story-completion actions (close story
`--reason completed`, tick the epic checkbox, append the delivery log) each verified idempotent on re-run; identical
gate set (0), schema-valid v2 handoff (story-merged-last-sibling → forward to the resolver), one v2 startup
state-assembly call. Every divergence traces to a PRD § (§9.1 / §8.3 / §9.2), a GitHub behavior (task-list auto-tick,
self-approve 422, non-default-base `closingIssuesReferences`), the deliberate v1→v2 skill rename, or free prose within
the shared schema — **no unexplained divergence**.

### Scenario 3 — Red-CI rejection

Target: a PR whose CI is red at head (or a failing local gate). Expected v2: health gate produces
`HEALTH_OK=false` → **unconditional hard block** → `--comment` soft-reject review leading with
`HEALTH_BODY` + the failing check(s), PR flipped back to draft, re-route handoff to
`/github-pipeline:resolver continue #<N>` (`merge: skipped (verdict)`, no Cleanup line). No merge, no
story bookkeeping.

> **Run recorded 2026-07-05** on `danwashusen/gh-pipeline-sandbox`. **Twin fixture:** two equivalent
> red-CI PRs, each adding a broken `sign_off(name)` helper (a `def sign_off(name)` line **missing its
> trailing colon** → `SyntaxError`) plus a `.ci-force-red` marker, base `main`, and `Closes`-linking its
> own seeded `bug` issue. **Twin-A → v1** = PR #19 / issue #17 (`parity/s3-twin-a`, `src/signoff_a.py`);
> **Twin-B → v2** = PR #20 / issue #18 (`parity/s3-twin-b`, `src/signoff_b.py`). Twinning (not reset) —
> the flow rejects rather than merges, so two independent red PRs are cleaner and touch nothing shared.
> Both runs headless: `claude -p "/github-pipeline:<skill> <PR>" --plugin-dir <this branch> --model opus
> --permission-mode bypassPermissions`, cwd = a fresh sandbox clone (one per run; `main` never mutates
> here so no `ROOT_DIVERGED` risk). Three constraints shaped the run and apply **identically to both
> versions**, so none breaks parity: (a) single-account sandbox ⇒ both PRs self-authored ⇒ both post the
> review as `--comment` — but a soft-reject is `--comment` regardless of authorship, so the self-approval
> downgrade is a no-op on this path (unlike S1/S2 it changes nothing). (b) The **fixture is deliberately
> double-red**: `.ci-force-red` forces GitHub CI red *and* the syntax error fails the local byte-compile,
> so CI and the local gate **agree red** and the CI/local-discrepancy operator gate never fires (a
> single-red fixture — red CI over a green local gate — would have tripped that gate and stalled the
> headless run). (c) The sandbox's configured static check (`pyflakes`) and test wrapper (`pytest`) are
> **not installed** in the run environment, so **both** skills, by their own judgment, substituted the
> `CLAUDE.md`-documented no-dependency `python3 -m compileall` byte-compile check as the code-health
> signal — which caught the genuine `SyntaxError` and independently confirmed red CI. Identical
> substitution on both sides ⇒ parity-neutral; recorded transparently in both cache comments.

- [x] v1 run captured (writes / gates / handoff / turns): **0 gates.** Writes: health-cache comment
      (`issuecomment-4885917764`, first-line `failed ❌`), soft-reject review (`COMMENTED`, self-authored,
      `pullrequestreview-4631253219`), PR #19 flipped back to **draft** (`gh pr ready 19 --undo`). **No
      merge** (`main` unchanged at `f148437`); no story bookkeeping. Worktree `.worktrees/parity/s3-twin-a`
      provisioned (the red-CI path runs the local gate, so a checkout is needed — unlike the S1/S2
      CI-green short-circuit) and **left in place** (no teardown — merge didn't run). Handoff → re-route
      `/github-pipeline:github-issue-resolver continue #19` (`review: COMMENT (soft-reject)` · `health: ❌
      at ba53cfb` · `merge: skipped (verdict)`, **no Cleanup line**). ~23 turns, ~7.1 min, $2.59; **4
      `github-pipeline:github-ops` sub-agents** (`GATHER_PR` #19 + `GATHER_ISSUE` #17 + two
      `PERSIST_COMMENT`); startup state assembled via **2** GATHER calls.
- [x] v2 run captured: **0 gates.** Writes: health-cache comment (`issuecomment-4885913604`, first-line
      `1 failed ❌`), soft-reject review (`COMMENTED`, self-authored, `pullrequestreview-4631250582`), PR
      #20 flipped back to **draft** (`gh pr ready 20 --undo`). **No merge** (`main` unchanged at
      `f148437`); no story bookkeeping. Workspace provisioned by `prep_evaluator.py` (`ensure --work`,
      `.worktrees/parity/s3-twin-b`) and **left in place** (no teardown — the no-merge exit skips the
      routed playbook's post-merge/cleanup). Handoff → re-route `/github-pipeline:resolver continue #20`
      (`review: COMMENT (soft-reject)` · `health: ❌ at a5c788e` · `merge: skipped (verdict)`, **no Cleanup
      line**). ~19 turns, ~4.8 min, $1.39; **0 sub-agents** (direct `prep_evaluator.py` + `gh_persist.py` —
      the §9.1 "no intermediary relay" design). Startup state assembled via **1** `prep_evaluator.py` call
      (no `--refresh`: the soft-reject short-circuits before the S7 merge gate, so the pre-merge currency
      re-check never fires).
- [x] Artifacts schema-identical (health-cache comment "N failed ❌", `--comment` review): **Yes.**
      **Health-cache:** both lead with marker `<!-- pr-evaluator-health-cache:v1 -->`, first-line state in
      the `N failed ❌` family (v2 `1 failed ❌`; v1 `failed ❌` — same `❌` fail token, v1 drops the count
      `N`), full `SHA:`, `TIER: targeted`, `Source:` field, a `| Command | Status | Duration |` table
      showing `compileall` `❌ fail (exit 1)` with the `SyntaxError` cause, and a `<details>` fail block
      carrying the identical `SyntaxError: expected ':'` at `src/signoff_<x>.py:4`; both preserve the
      **frozen** `_Cached by `github-pr-evaluator`._` footer, and **both correctly omit** the
      `**Selection reasoning**` block (static checks short-circuited before test selection fired — the
      `health-cache-comment.md` rule). **Review:** both are `COMMENTED` (self-authored), **lead with
      `HEALTH_BODY`** (the red-health line + the failing `compileall` command + the SHA + "CI agrees red"
      + a link to the health-cache comment), carry the `pyflakes → compileall` substitution note as a
      block-quote, then the five-dimension assessment (scope / DoD / native-blocked-by / doc-grounding /
      plan-adherence) with `.ci-force-red` flagged out-of-scope in both; **neither** emits `## DoD
      verification` (historical un-annotated-DoD path — correct omission).
- [x] PR flipped to draft; no merge fired; workspace left in place: **Yes** (all three, both twins). Both
      PRs `isDraft: true`, `mergedAt: null`, `state: OPEN`; sandbox `main` unchanged at `f148437`; **no
      `gh pr merge`** in either transcript; **no `worktree-hooks.sh teardown` / `git worktree remove`** in
      either; both worktrees present on disk at eval end (`.worktrees/parity/s3-twin-a` @ `ba53cfb`,
      `.worktrees/parity/s3-twin-b` @ `a5c788e`). Both handoffs **omit the Cleanup line** per the
      no-merge omission rule.
- [x] Gates match; handoff schema-valid; ≤1 state-assembly call: **Yes.** Gates **0 = 0** (the
      double-red fixture keeps the CI/local-discrepancy gate silent; no `closingIssuesReferences` gate —
      default-base PRs link cleanly; no `/review`/reviewer gates). Both handoffs validate against
      `_shared/handoff-format.md`'s **soft-reject re-route** shape (`handoff-renderings.md` "Soft-reject —
      re-route to resolver"): `Issue:` (`open · bug · plan: ✗`), `PR:` (`draft · base main · review:
      COMMENT (soft-reject) · health: ❌ at <7-sha> · merge: skipped (verdict)`), **no Cleanup line**,
      `Next:` fenced `resolver continue #<PR>`, load-bearing `Why:` naming the syntax error + `.ci-force-red`.
      All closed-set markers valid. v2 startup state assembly = **1** `prep_evaluator.py` call (§9.2
      satisfied); v1's 2-call GATHER assembly is its own architecture, not the §9.2 bar.
- [x] Divergences (each traced to a PRD § or filed as a defect):
  - **(deliberate rename, schema-valid) Handoff next-command namespace.** v1 re-routes to
    `/github-pipeline:github-issue-resolver continue #19`, v2 to `/github-pipeline:resolver continue #20` —
    the v1→v2 skill rename. Both target the resolver in continue-on-existing-branch mode; parity-neutral.
    Same device as S2.
  - **(environment, identical on both sides) `pyflakes`/`pytest` not installed → `compileall`
    substitution.** Both skills, by their own judgment, ran the `CLAUDE.md`-documented no-dependency
    `python3 -m compileall -q .` as the health signal (the configured `pyflakes` and `pytest` modules are
    absent in the run environment), which caught the genuine `SyntaxError` and agreed with red CI. This is
    not a spec-gap gate (`Health-check config missing` fires only when *no* static-checks config exists;
    here the config is present but the tool is missing) — it's a run-time judgment substitution both
    versions made **identically**, recorded transparently in both cache comments. Parity-neutral; the
    scenario's "N failed ❌" is therefore a real code failure, not just a tooling gap.
  - **(free prose, schema-identical) Health-cache first-line count.** v2 `1 failed ❌` (the strictly-correct
    frozen `N failed ❌` form) vs v1 `failed ❌` (drops the `N`). Same `❌` fail token and state family; the
    only consumer-parsed distinction is fail-vs-green, which both carry. Low-severity v1-side omission.
  - **(free prose, non-consumed) Health-cache `Source:` value.** v1 `CLAUDE.md` vs v2 `COMMANDS.md /
    CLAUDE.md` (the frozen template's literal default). Same field, read by no consumer beyond `SHA:`.
    Identical to the S1/S2 finding.
  - **(free prose) Health-cache table rows + review lead ordering.** v1's table lists three commands
    (`pyflakes` / `compileall` / `pytest`) with a trailing prose paragraph and `0s`/`1s` durations; v2's
    lists two (`pyflakes` / `compileall`) with `—` durations. Same `| Command | Status | Duration |`
    schema. In the review, v2 **leads with the health line** (spine S5 "start the body with `HEALTH_BODY`");
    v1 prepends a `**Verdict: soft-reject**` line first. Same element set, free-prose arrangement — same
    ordering divergence noted in S2.
  - **(architecture, metrics not artifacts) Sub-agent topology / startup calls.** v1 = 4 `github-ops`
    sub-agents, 2 `GATHER` startup calls; v2 = 0 sub-agents (direct scripts, §9.1), 1 `prep` startup call
    (§9.2 ≤1). Same shape as S1/S2; no persisted-artifact impact. (v2 also issued one supplemental direct
    `gh issue view 18` after prep — a redundant targeted re-read of an issue prep had already assembled,
    not a second one-shot state assembly; the §9.2 startup bar is still met at 1 `prep` call. Low-severity
    observation, not a divergence in behavior.)

**Verdict: PASS.** The health gate produced an **unconditional hard block** on both twins → soft-reject
`--comment` review leading with `HEALTH_BODY`, PR flipped back to **draft**, **no merge** (`main`
untouched), **workspace left in place** (no teardown, no Cleanup line), and a schema-valid re-route
handoff to `resolver continue #<PR>` (`merge: skipped (verdict)`). Persisted artifacts (health-cache
`N failed ❌` comment + `--comment` soft-reject review) are schema-identical; gate set identical (0 = 0);
v2 startup = one state-assembly call. Every divergence traces to the deliberate v1→v2 rename, a run-time
environment substitution both versions made identically, or free prose within the shared schema — **no
unexplained divergence**.

### Scenario 4 — `ask`-policy merge gate

Target: a standard/story PR that passes evaluation cleanly with merge-policy `ask` (the default).
Expected v2: the review is **deferred** (not posted at verdict time); the S7-gate refreshes PR state,
asks `header: "Approve PR"`, posts the review as the **operator's** decision with the
operator-attribution header, and merges only on Approve (or prints the command on
DIRTY/BLOCKED/deferred). `review: APPROVE (operator)`.

> **Run recorded 2026-07-05** on `danwashusen/gh-pipeline-sandbox`. **Twin fixture:** two equivalent
> passing standard PRs, each adding a distinct-file `welcome(name)` helper and `Closes`-linking its own
> seeded `bug` issue, base `main`, green CI (no `.ci-force-red`). **Twin-A → v1** = PR #24 / issue #21
> (`parity/s4-twin-a`, `src/welcome_a.py`); **Twin-B → v2** = PR #25 / issue #22 (`parity/s4-twin-b`,
> `src/welcome_b.py`, rebased onto post-twin-A `main` so both PRs were `CLEAN`/single-commit at eval
> time). A **third solo v2 PR** exercises the override path: PR #26 / issue #23
> (`parity/s4-override`, `src/salute_o.py`, `salute(name)`), rebased onto post-twin-B `main`. Unlike
> S1/S2, the sandbox's `<!-- pr-evaluator-merge-policy -->` was **left at its `- standard: ask` default
> — that *is* this scenario's condition**, so the merge-approval gate fired naturally on every run (no
> per-run `auto` override). Runs were **interactive** (not headless `-p`) precisely because the `ask`
> gate needs a live operator to answer `header: "Approve PR"`. Two constraints apply **identically to
> both versions** (parity-neutral): (a) single-account sandbox ⇒ all PRs self-authored ⇒ both correctly
> downgraded `--approve`→`--comment` (GitHub 422s self-approve), the operator decision authoritative
> and the `review:` marker unchanged; (b) each PR carries an unticked, un-annotated DoD → the
> historical walk-the-item DoD path (no `## DoD verification` section — correct omission).

- [x] v1 run captured: PR #24, standard, `ask` policy, verdict **APPROVE**. Review **deferred** to the
      §12.0 gate (§11 deferral rule — not posted at verdict time). §12.0 **merge-approval gate fired**
      (`header: "Approve PR"`; the pre-gate recap named the PR/verdict/squash plan) → operator chose
      **Approve**. Writes: health-cache comment (`issuecomment-4886042341`, first-line `all green ✅` at
      `34e8f04`), the deferred review posted **operator-attributed** (`COMMENTED`, self-authored;
      header `**Operator decision: Approve** — operator action 2026-07-05T12:33:36Z` / rationale
      `Confirmed the evaluator's APPROVE verdict.` / frozen footer `_Recorded by `github-pr-evaluator`
      on behalf of the human operator._`), squash-merge → `main@90f9923` (subject `fix: add
      welcome(name) helper (S4 twin-a) (#24)`), issue #21 auto-closed. Terminal handoff
      (`review: APPROVE (operator)` · `merge: squash → main@90f9923`).
- [x] v2 run captured: PR #25, standard, `ask` policy, verdict **APPROVE**. Review **deferred** — the
      skill showed the verdict + merge plan and explicitly gated ("Standard merge policy is `ask`, so
      this is your call at the gate"), staging `review.md` without posting (spine S7 defer rule). S7-gate
      **refreshed** first (`prep_evaluator.py --refresh` — clean, no external action), then asked
      `header: "Approve PR"` → operator **Approve**. Writes: health-cache comment
      (`issuecomment-4886137100`, `all green ✅` at `a269c83`), the deferred review posted
      **operator-attributed** (`COMMENTED`, self-authored; header `**Operator decision: Approve** —
      operator action 2026-07-05T13:05:19Z` + the same frozen `github-pr-evaluator` footer, body leading
      `**Health:**` → `Verdict: APPROVE` → five-dimension assessment), squash-merge → `main@a07eb90`
      (subject `fix: add welcome(name) helper (S4 twin-b) (#25)`), issue #22 auto-closed. **Terminal
      handoff** (`review: APPROVE (operator)` · `merge: squash → main@a07eb90` · Cleanup `worktree
      force-removed; teardown ran; scratch purged`) — the `standard.md` shape. Startup = **1**
      `prep_evaluator.py` call (+1 pre-merge `--refresh`, the router-prescribed currency re-check).
- [x] Merge gate asked with the fixed option set; review posted operator-attributed (schema-identical
      header): **Yes.** Both v1 §12.0 and v2 spine S7-gate ask the **identical** gate — `header:
      "Approve PR"`, the `question` naming the PR + its URL + a one-line verdict/strategy recap, and the
      **fixed option set Approve / Needs Revision / Reject** (Other → deferred-merge). Both **defer** the
      review under `ask` and post it only after the operator decides, with a **schema-identical**
      operator-attribution header (`**Operator decision: <decision>** — operator action <ISO-8601 UTC>` /
      rationale / the **frozen** `_Recorded by `github-pr-evaluator` on behalf of the human operator._`
      footer — preserved verbatim despite the v2 rename, a prd.md §7 compatibility token). The v2 #26
      gate card (captured verbatim from the run transcript) names the PR + URL + `verdict APPROVE …
      Recommended merge: squash → main, subject …` — matching the spec.
- [x] Operator override path exercised (Reject an approve), recorded on the PR: **Yes** (PR #26, v2). The
      automated verdict was **APPROVE** (all five dimensions clean, health green at `10f5a02`); the
      review was **deferred**; the S7-gate fired and the operator chose **Reject**, overriding the
      verdict. v2 posted the review **operator-attributed as a Reject** (`COMMENTED`, self-authored;
      header `**Operator decision: Reject** — operator action 2026-07-05T13:20:27Z`, rationale carrying
      the spec-mandated **`Overrides this run's automated verdict (APPROVE).`** line + frozen footer),
      flipped PR #26 back to **draft** (`gh pr ready 26 --undo`), ran **no merge** (`main` unchanged at
      `a07eb90`; issue #23 stays open), and emitted the **re-route handoff** (`review: COMMENT (operator:
      reject)` · `merge: skipped (verdict)`, **no Cleanup line**) → `/github-pipeline:resolver continue
      #26`. The override is durably recorded on the PR. (Note: "Approve a soft-reject" is **unreachable**
      by design in both versions — a COMMENT/soft-reject verdict short-circuits *before* the gate, so the
      gate only ever adjudicates an APPROVE; "Reject an approve" is the reachable override, and it is what
      was exercised.)
- [x] Gates match; handoff schema-valid; ≤1 state-assembly call: **Yes.** Gate set matches exactly —
      each run fired **one** merge-approval gate (`header: "Approve PR"`, identical option set); no other
      gates (default-base PRs link cleanly, health green, no `/review`/reviewer gates). All three v2
      handoffs validate against `_shared/handoff-format.md`: #25 the **standard-terminal** shape, #26 the
      **operator soft-reject → re-route** shape (`handoff-renderings.md` "Operator soft-reject (Needs
      Revision / Reject)"); all closed-set markers valid (`APPROVE (operator)`, `COMMENT (operator:
      reject)`, `merge: squash → main@<7-sha>` / `merge: skipped (verdict)`, `health: ✅ at <7-sha>`).
      v2 startup state assembly = **1** `prep_evaluator.py` call per run (§9.2 satisfied; the pre-merge
      `--refresh` re-derives only volatile PR/CI facts); **0** sub-agents (direct `prep_evaluator.py` +
      `gh_persist.py`, the §9.1 "no intermediary relay" design).
- [x] Divergences (each traced to a PRD § or filed as a defect):
  - **(deliberate rename, schema-valid) Handoff next-command namespace.** v2 re-routes #26 to
    `/github-pipeline:resolver continue #26` — the v1→v2 skill rename. The v2 `resolver` skill does not
    exist until S9/S10, so a live session reports "Unknown command" until the resolver cutover lands;
    the operator ran the current v1 `/github-pipeline:github-issue-resolver continue #26` instead. Benign
    forward-looking namespace, identical device to S1–S3; parity-neutral.
  - **(free prose, non-consumed) Health-cache `Source:` value.** v1 #24 `GitHub statusCheckRollup` vs v2
    #25 `COMMANDS.md / CLAUDE.md` (frozen template default). Same `Source:` field, same marker /
    `all green ✅` / `SHA:` / `TIER: full`; read by no consumer beyond `SHA:`. Identical to the S1/S3
    finding.
  - **(v2 solo behavior, not a v1↔v2 comparison) Local byte-compile on the CI-green path (#26).** On
    #26's green-CI path v2 additionally ran `python3 -m compileall -q .` to ground the health-cache with
    an honest command row (the configured `pyflakes` being unavailable — the same substitution device as
    S3), rather than taking the strict spine-S3.2 skip-to-cache short-circuit it took in S1/S2. Same
    `HEALTH_OK=true`; extra work within model discretion. #26 is a solo v2 override PR (no v1 twin), so
    this is not a parity comparison — noted for completeness.
  - **(out of S7 scope) Downstream resolver card.** After the #26 re-route the operator invoked the
    resolver (`github-issue-resolver continue #26`); on a **no-reason** Reject with clean code it
    correctly asked a "rework / close / re-submit" decision card rather than fabricating changes. That is
    the *resolver's* behavior (not under test at S7 — the evaluator's re-route + operator-attributed
    Reject were both correct and complete) and the operator declined it. No evaluator-side impact.

**Verdict: PASS.** Under the sandbox's default `- standard: ask` policy, both versions **deferred** the
review, fired the **identical** merge-approval gate (`header: "Approve PR"`, fixed option set), and
posted the review as the **operator's** decision with a **schema-identical** operator-attribution header
(frozen `github-pr-evaluator` footer preserved). On operator **Approve** v2 squash-merged and rendered
`review: APPROVE (operator)` (terminal); on operator **Reject** (overriding an APPROVE) v2 posted the
operator-attributed Reject with the `Overrides this run's automated verdict (APPROVE)` note, flipped the
PR back to draft, ran no merge, and re-routed — the override durably recorded on the PR. Gate set
identical; handoffs schema-valid; v2 startup = one state-assembly call. Every divergence traces to the
deliberate v1→v2 rename, free prose within the shared schema, a solo-run v2 judgment, or downstream
(out-of-scope) resolver behavior — **no unexplained divergence**.

## Go/no-go (S8 input)

- [x] All four scenarios pass with **zero unexplained divergences**. Scenario 1 (standard approve +
      merge) **PASS**, Scenario 2 (story merge — delivery-log + epic checkbox) **PASS**, Scenario 3
      (red-CI rejection) **PASS**, Scenario 4 (`ask`-policy merge gate + operator override) **PASS**.
- [x] Result summary (accepted / blocking finding + remediation step): **Accepted — go.** Across all
      four scenarios the v2 `evaluator` produces persisted artifacts (health-cache comment, PR review
      incl. operator-attribution header, delivery-log line, epic checkbox) that are **schema-identical**
      to v1 and **cross-consumable in both directions** by the shared readers; the same genuine decisions
      are gated (merge-approval, none-else under these fixtures); every handoff validates against
      `_shared/handoff-format.md`; and startup is **one** `prep_evaluator.py` state-assembly call
      (§9.2). No blocking finding. All recorded divergences trace to a PRD § (§8.3 / §9.1 / §9.2), a
      GitHub behavior (task-list auto-tick, self-approve 422, non-default-base `closingIssuesReferences`),
      the deliberate v1→v2 skill rename, free prose within the shared schema, or an identical run-time
      environment substitution. The S8 go/no-go input is satisfied: **S7 parity recorded with zero
      unexplained divergences.**
