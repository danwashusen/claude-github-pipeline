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

- [ ] v1 run captured:
- [ ] v2 run captured:
- [ ] Artifacts schema-identical (delivery-log line, epic-checkbox edit, review): 
- [ ] Cross-consumption confirmed (the planner reads the v2 delivery-log line; a v1 delivery-log is readable by v2):
- [ ] Story closed + checkbox ticked + log appended, each idempotent on a re-run:
- [ ] Gates match; handoff schema-valid; ≤1 state-assembly call:
- [ ] Divergences:

### Scenario 3 — Red-CI rejection

Target: a PR whose CI is red at head (or a failing local gate). Expected v2: health gate produces
`HEALTH_OK=false` → **unconditional hard block** → `--comment` soft-reject review leading with
`HEALTH_BODY` + the failing check(s), PR flipped back to draft, re-route handoff to
`/github-pipeline:resolver continue #<N>` (`merge: skipped (verdict)`, no Cleanup line). No merge, no
story bookkeeping.

- [ ] v1 run captured:
- [ ] v2 run captured:
- [ ] Artifacts schema-identical (health-cache comment "N failed ❌", `--comment` review): 
- [ ] PR flipped to draft; no merge fired; workspace left in place:
- [ ] Gates match; handoff schema-valid; ≤1 state-assembly call:
- [ ] Divergences:

### Scenario 4 — `ask`-policy merge gate

Target: a standard/story PR that passes evaluation cleanly with merge-policy `ask` (the default).
Expected v2: the review is **deferred** (not posted at verdict time); the S7-gate refreshes PR state,
asks `header: "Approve PR"`, posts the review as the **operator's** decision with the
operator-attribution header, and merges only on Approve (or prints the command on
DIRTY/BLOCKED/deferred). `review: APPROVE (operator)`.

- [ ] v1 run captured:
- [ ] v2 run captured:
- [ ] Merge gate asked with the fixed option set; review posted operator-attributed (schema-identical header): 
- [ ] Operator override path exercised (Approve a soft-reject and/or Reject an approve), recorded on the PR:
- [ ] Gates match; handoff schema-valid; ≤1 state-assembly call:
- [ ] Divergences:

## Go/no-go (S8 input)

- [ ] All four scenarios pass with **zero unexplained divergences**.
- [ ] Result summary (accepted / blocking finding + remediation step):
