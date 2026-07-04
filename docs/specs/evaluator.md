# evaluator — v1 functional spec (baseline)

> Source: `skills/github-pr-evaluator/SKILL.md` (971 lines) + references
> (`references/handoff-renderings.md`, `references/test-selection-sub-agent.md`).
> Captures v1 behavior as the parity baseline for [implementation.md](../implementation.md) S<cutover>.
> v1 skill name: `github-pr-evaluator`; v2 name: `evaluator`.

## Overview

The evaluator is the final gate between "code reviewed" and "merged cleanly into main." Given a PR
number (or the PR for the current worktree branch), it fetches the PR + its origin issue(s) + prior
`/review` comments, runs a cached branch-health gate (targeted or full test selection), evaluates the
diff against the issue on five dimensions (scope, DoD/acceptance-criteria, native `blocked by`, doc
grounding, plan adherence), posts a formal GitHub review (`--approve` or `--comment`), recommends a
merge strategy, and — subject to a per-PR-type merge-approval policy — either merges hands-free or
puts a human operator in the loop before merging. On a story-PR merge it also closes the story issue,
ticks the parent epic's checkbox, and appends to the epic delivery log. It runs as its own Claude Code
session (`model: opus`, `effort: xhigh`) and ends every clean run with a single `## Handoff` block that
is the only bridge to the next session (`skills/_shared/handoff-format.md:3`). Inputs: a PR
number/URL/current-branch context. Outputs: a posted GitHub PR review, a cache comment, an optional
merge, optional story/epic bookkeeping, and the `## Handoff`.

## Artifacts written

| Artifact | Marker / schema | Lives in | Trigger |
|---|---|---|---|
| Health-check cache comment | `<!-- pr-evaluator-health-cache:v1 -->` (SKILL.md:300) | PR comment | Every run of the §5 branch-health gate that doesn't skip posting (SKILL.md §5.6), keyed to `HEAD_SHA` |
| PR review | GitHub native review object (no marker; body is prose) | PR review | §11 (COMMENT verdict, or APPROVE under `auto` policy) or §12.0 step 3 (operator-attributed decision under `ask` policy / epic-integration) |
| Epic delivery log entry | `<!-- epic-delivery-log:v1 -->` (SKILL.md:725; schema owned by `skills/_shared/epic-delivery-log.md`) | epic issue comment | §13, third action, on every story-PR merge (evaluator is the **sole writer**, per `epic-delivery-log.md:9`) |
| DoD un-tick (sticky veto) | `- [ ] <text> (resolver claimed phase <N>, commit <sha>; evaluator rejected: <reason>)` (schema owned by `skills/_shared/dod-annotations.md:15`) | issue body, `## Definition of done` | §6 "Un-tick on rejection," on a clear semantic mismatch between a projected DoD tick and its attributed phase diff |
| Epic `## Stories` checkbox tick | `- [x] #<story-number>` (was `- [ ]`) | epic issue body | §13, second action, on every story-PR merge |
| `## Handoff` block | schema owned by `skills/_shared/handoff-format.md` | session output (chat) | §15, end of every clean run |
| Filed follow-up issue(s) | `bug \| incomplete-feature \| deferred-test \| revise-existing` type (per `skills/_shared/follow-up-filing.md`) | new GitHub issue | §13a, after any merge, for residual non-blocking findings not already filed |
| Follow-up URLs comment | — (no marker; prose listing the filed URLs) | PR comment | §13a, immediately after filing follow-up issue(s), "so they're durable" (SKILL.md:749) |

**Health-check cache comment — full schema (SKILL.md:297-329):**

```
<!-- pr-evaluator-health-cache:v1 -->
**Health checks** at `<short-sha>` — <all green ✅ | N failed ❌ | local-green over red CI ⚠️> — <ISO-8601 UTC timestamp>

SHA: <full-sha>
TIER: <targeted | full>
Source: COMMANDS.md / CLAUDE.md

**Selection reasoning** (from §5.5.2 sub-agent):
> <SELECTION_REASONING verbatim — the sub-agent's RATIONALE: section...>

| Command | Status | Duration |
|---|---|---|
| `<cmd-1>` | ✅ pass | 1.2s |
...

<details>
<summary>Failed: `<cmd-2>` — last 50 lines</summary>

```
<FAIL_TAIL>
```
</details>

_Cached by `github-pr-evaluator`. Do not edit; will be regenerated when HEAD changes._
```

Keyed per head SHA — the comment is deleted and reposted (never edited in place) whenever `HEAD_SHA`
changes (SKILL.md:131-134, :331-335). First-line state token is one of exactly three: "all green ✅",
"N failed ❌", "local-green over red CI ⚠️" (the CI/local discrepancy gate's operator-override outcome,
SKILL.md:295, :301). `TIER:` is `targeted` or `full`; a comment with no `TIER:` line predates
targeting and is read as `full` (SKILL.md:131).

**Epic delivery log entry — one line per story, format from `skills/_shared/epic-delivery-log.md:20-22`:**

```
- #<story> — delivered: <actual contract shape, as merged> @ `<commit-sha>` (PR #<M>, merged <ISO-8601 date>)
```

Recorded from the **merged diff**, not copied from the plan's pinned contract (SKILL.md:727,
`epic-delivery-log.md:25`) — a divergence is deliberately visible. Idempotent: a re-run updates an
existing `#<story>` line in place rather than duplicating (`epic-delivery-log.md:33`).

**`## DoD verification` review-body section (SKILL.md:434-443)** — included only when per-phase
verification ran and produced at least one un-tick (or, in the all-clean case, a single summary
line). Per un-ticked bullet:

```markdown
- **Bullet <index>** — <verbatim bullet text>
  - **Resolver claimed:** phase <N>, commit `<short-sha>`
  - **Evidence:** <file:line range or short diff excerpt showing the mismatch>
  - **Why rejected:** <one-sentence rationale>
```

**Operator-attribution header (§12.0 step 3, SKILL.md:614-623)** — prepended to the staged review
body when the merge-approval gate ran, mirroring `dod-annotations.md`'s `operator action <ISO-date>`
form:

```
**Operator decision: <Approve | Needs Revision | Reject>** — operator action <ISO-8601 UTC>

<rationale...>
[optional: "Overrides this run's automated verdict (<APPROVE|COMMENT>)."]

_Recorded by `github-pr-evaluator` on behalf of the human operator._
```

**`## Handoff` block** — the evaluator's per-outcome renderings are cataloged in
`references/handoff-renderings.md`; the schema and closed-set vocabulary are owned by
`skills/_shared/handoff-format.md`. See a verbatim worked example in
`docs/specs/examples/` (per the S1 baseline task; not authored by this spec).

## Artifacts read

| Artifact | Marker | Where | What's extracted |
|---|---|---|---|
| PR body, diff, reviews, thread | — (via `GATHER_PR`) | PR | `headRefOid`, `statusCheckRollup`, `closingIssuesReferences`, `mergeStateStatus`, `mergeable`, `reviewDecision`, `additions`/`deletions`/`changedFiles`/`commit_count`, `url`, `labels`, `state` (SKILL.md:84) |
| Health-cache marker (self-read) | `<!-- pr-evaluator-health-cache:v1 -->` | PR comment | `marker_comment_id`/`_url`/`_path`/`_bytes` or `marker_comment_present: false`, carried on the same `GATHER_PR` call via `marker_prefix` (SKILL.md:84, §5.2) |
| Origin issue body, thread | — (via `GATHER_ISSUE`) | issue | full body + thread, for scope/DoD/doc-grounding evaluation (SKILL.md:86-90) |
| Native issue dependencies | `blocked_by` list + `deps_available` flag | issue (via `GATHER_ISSUE`) | Any **open** blocker holds the merge — soft-reject (SKILL.md:360; contract in `skills/_shared/open-question-links.md:35`) |
| Implementation plan | `<!-- implementation-plan:v1 -->` | issue comment (via `GATHER_ISSUE` `marker_prefix`) | `## Architecture decisions`, `## Changes`, `## Data model / schema impact`, `## Test plan`, `## Deviations`, `## Epic contract` `Delivers:` line (SKILL.md:88, :413-416, :727) |
| DoD checkbox annotations | closed set owned by `skills/_shared/dod-annotations.md` | issue body, `## Definition of done` | `closed by phase <N>, commit <sha>` / `closed by phase <N>, operator action <date>` / `closed by commit <sha>` ticked forms drive per-phase verification (SKILL.md:353, `dod-annotations.md:64`) |
| `## Open questions` section | `<!-- open-question-links:v1 -->` | issue body | Read only via the native `blocked_by` relationship it sets — bullets themselves are **not** read as DoD/acceptance-criteria (SKILL.md:358, :360) |
| `## Follow-ups` section | — | PR body | Filed-deferral entries, re-adjudicated against docs rather than trusted (SKILL.md:405-409, :747) |
| `## Phase tracker` section | — | PR body | `- [x] Phase N — title (commit <sha>)` entries — the phase→commit mapping for per-phase verification (SKILL.md:362) |
| Prior `/review` comments | — (numbered scored-issues list or "No issues found") | PR comments | Code-quality signal, filtered from `comments`/`reviews` (SKILL.md §4) |
| Parent epic body | — | issue (fetched by search for a body containing `#<story-number>`, or directly for an epic-integration PR) | `## Goal`, `## Background`, `## Stories`, `## Definition of done` (SKILL.md:94, :792-794, §"If the PR is an epic integration PR") |
| Existing epic delivery log | `<!-- epic-delivery-log:v1 -->` | epic issue comment | Fetched before append, to update-in-place vs. create (SKILL.md:729-736) |
| Config: static checks | `<!-- pr-evaluator-static-checks -->` | `COMMANDS.md`/`CLAUDE.md` (+ `@`-includes) | Fail-fast hygiene command list (SKILL.md §5.4) |
| Config: test target | `<!-- pr-evaluator-test-target -->` | `COMMANDS.md`/`CLAUDE.md` | wrapper, `full-suite-command`, per-target naming/fallback rules (SKILL.md §5.4) |
| Config: escalation labels | `<!-- pr-evaluator-escalation-labels -->` | `COMMANDS.md`/`CLAUDE.md` | PR labels that force the full suite (SKILL.md §5.4) |
| Config: merge policy | `<!-- pr-evaluator-merge-policy -->` | `COMMANDS.md`/`CLAUDE.md` | per-PR-type `ask \| auto`, default `ask` (SKILL.md §8 "Resolve the merge-approval policy") |
| Legacy config: health checks | `<!-- pr-evaluator-health-checks -->` | `COMMANDS.md`/`CLAUDE.md` | Backward-compat flat command list when the split blocks are absent (SKILL.md:188, :201) |
| Worktree setup/teardown blocks | `<!-- worktree-setup -->` / `<!-- worktree-teardown -->` | `COMMANDS.md`/`CLAUDE.md` (via `worktree-hooks.sh`) | Per-worktree provisioning/release commands (SKILL.md:217, :759; contract owned by `skills/_shared/worktree-lifecycle.md`) |
| Repo merge config | `allow_squash_merge`, `allow_merge_commit`, `allow_rebase_merge`, `delete_branch_on_merge`, `allow_auto_merge` | `gh api repos/<owner>/<repo>` | Clamps the recommended merge strategy to what the repo allows (SKILL.md §8) |
| Branch protection | `gh api .../branches/main/protection` | GitHub API | 403 on a private free-plan repo is read as "no enforced linear-history rule" (SKILL.md:458) |

## Operator gates

Exhaustive list of every point this skill asks a human for a decision (via `AskUserQuestion`, per
`skills/_shared/asking-the-user.md`):

| Gate | When | Options | Effect of each choice |
|---|---|---|---|
| **Health-check config missing** | Neither `pr-evaluator-static-checks` nor legacy `pr-evaluator-health-checks` found (SKILL.md:190-195) | "Skip for now" / "I'll specify commands" (+ auto-appended "Other" free text) | Skip → `HEALTH_OK=null`, proceed without a local gate (still hard-blocks if CI is red with nothing to clear it). Specify → runs the typed commands as a flat list for this run; offers (but doesn't write) to persist the block after a green result |
| **CI vs local discrepancy** | §5.3 found CI red at `HEAD_SHA` **and** the local gate ran green (SKILL.md:295) | "Trust local gate" / "Treat as red" | Trust → `HEALTH_OK=true`, cache comment stamped "local-green over red CI ⚠️", review body records the operator's override. Treat as red → `HEALTH_OK=false`, §7 hard-blocks citing the failing CI checks |
| **Merge-approval decision gate (§12.0)** | Verdict is APPROVE and `MERGE_POLICY[pr-type]` is `ask` (default), **or** the PR is epic-integration (always gated) | "Approve" (or, for epic integration, split into "Approve (merge commit)" / "Approve (squash)") / "Needs Revision" / "Reject" (+ "Other" free text) | Approve → posts review as operator-attributed `--approve` (or `--comment` if self-authored), proceeds to merge (§12a/§12b). Needs Revision / Reject → posts review as operator-attributed `--comment`, flips PR to draft, re-routes to resolver, no merge. "Other" ("approve but merge manually later") → records as Approve, routes to §12c (print command, no merge now) |
| **Unresolved `/review` issues** | Latest `/review` run left flagged issues that look unaddressed (SKILL.md §"When to ask the user") | "Hard rejection" / "Note + proceed" | Hard rejection → treated as a blocking soft-reject. Note + proceed → cited in the verdict body, doesn't block |
| **Squash type ambiguous** | Inferred Conventional-Commits `<type>` disagrees between PR title and issue labels, or neither carries a prefix (SKILL.md §9, §"When to ask the user") | free-form confirmation (implicit — the draft is always shown per §10 before posting) | Confirms the type before the squash subject is composed |
| **Epic-integration DoD not evidently satisfied** | One or more `## Definition of done` items on an epic-integration PR aren't clearly met by the accumulated diff (SKILL.md §"When to ask the user") | (situational) | Surfaces the gap before approval |
| **`REVIEW_REQUIRED` owed to a named reviewer** | `reviewDecision == REVIEW_REQUIRED` and a specific reviewer hasn't acted (SKILL.md §"When to ask the user") | "Proceed anyway" / "Wait for reviewer" | Proceed → posts approval now (merge may still gate on the named reviewer). Wait → holds off |
| **No `closingIssuesReferences`** | PR isn't linked to any issue (SKILL.md §"When to ask the user") | "Name the issue" (Other free text) / "Intentionally standalone" | Name → runs the scope evaluation against the given issue number. Standalone → skips the scope-against-issue check |
| **Conflicting acceptance criteria across multiple linked issues** | PR closes ≥2 issues whose acceptance criteria conflict (SKILL.md §"When to ask the user") | (situational) | Surfaces before a verdict is formed |
| **Branch protection returns non-403, stricter than expected** | (SKILL.md §"When to ask the user") | (situational) | Surfaces before recommending a merge strategy |

Every `AskUserQuestion` in this skill can only originate from the main loop — the two sub-agents this
skill dispatches (test-selection `Explore`, `apple-platform-build-tools:builder`) cannot call it and
never attempt to (SKILL.md:34-35, and see "Sub-agents dispatched" below).

## Judgment steps (model reasoning — stays in the prompt)

| Step | What it judges | Main loop or sub-agent |
|---|---|---|
| §4 code-quality signal read | Whether prior `/review` comments show blessed or open findings | Main loop |
| §5.5.2 test selection | Which test suites the PR's diff warrants (escalation rules, heuristics, integration blast-radius) | **`Explore` sub-agent** — reasoning stays out of the main conversation (SKILL.md §5.5.2, full prompt in `references/test-selection-sub-agent.md`) |
| §6 Scope match | Whether the diff changes only what the issue asked, drive-by edits | Main loop |
| §6 DoD / acceptance-criteria verification (both the per-phase and historical-fallback paths) | Whether each bullet is satisfied by its attributed diff or the whole-PR diff | Main loop |
| §6 Doc grounding | Whether the diff is consistent with the project's documented constraints, at an escalating depth | Main loop |
| §6 `## Follow-ups` re-adjudication | Whether a filed deferral is actually an in-scope documented-constraint violation being laundered past the gate | Main loop |
| §6 Plan adherence | Whether the diff reverses a plan-locked decision without disclosure | Main loop |
| §6 Story/epic context checks | Base ref, integration-branch caveat presence, `Fixes #<epic>` presence | Main loop |
| §7 Verdict | APPROVE vs COMMENT-REJECTION, from the dimension results + `HEALTH_OK` | Main loop |
| §8 Merge strategy | Squash vs merge-commit vs (unused) rebase, by PR shape, clamped to repo config | Main loop |
| §9 Squash subject composition | Conventional-Commits `<type>` inference, double-`(#NN)`-suffix stripping | Main loop |
| §12.0 step 1 freshness check | Whether the operator already acted on GitHub since the last snapshot | Main loop |
| §13a residual follow-up filing | Which findings are genuinely residual and non-duplicate | Main loop (dispatches one `general-purpose` sub-agent per item per `skills/_shared/follow-up-filing.md`) |
| §5.5.3 test execution (xcodebuild-shaped only) | Pass/fail + first error, narrowly bounded — **not** a diagnose-and-fix judgment | **`apple-platform-build-tools:builder` sub-agent**, explicitly forbidden from editing code or expanding scope (SKILL.md:282-286) |
| §15 Handoff composition | `Next:`/`Why:` framing — judgment, not mechanical data (per `skills/_shared/handoff-format.md:128`) | Main loop |

## Deterministic steps (candidate script work — moves to a prep/executor script)

| Step | Inputs → output |
|---|---|
| Self-approval pre-check (§2) | `PR_AUTHOR`, `CURRENT_USER` (from `gh pr view`/`gh api user`) → boolean (self-authored?) that forces `review_action=comment` regardless of verdict |
| PR/issue fetch envelope (§3) | PR number, repo, scratch dir → PR metadata + body/thread/diff/reviews/line-comments paths + health-cache marker scalars, via `github-ops` `GATHER_PR`; then per-issue `GATHER_ISSUE` with `marker_prefix` for the plan |
| PR-type classification | `headRefName`, `baseRefName`, `commits.totalCount` → `epic-integration \| story \| regular` (SKILL.md:254-256) |
| CI rollup classification (§5.3) | `statusCheckRollup` → `empty \| pending \| green \| red` + `CI_FAIL_CHECKS` list |
| Pending-CI watch → re-classify loop (§5.3 "Wait for pending CI") | `pending` classification, PR number, repo → blocks on `gh pr checks <N> --repo <owner/repo> --watch --interval 30`, output redirected to `/tmp/gh-pr-eval-<N>/ci-watch.log`; on return, re-fetches `statusCheckRollup` and re-applies §5.3 classification to the settled value. Unbounded/re-invokable (a harness timeout mid-watch is resumed by re-invoking, not treated as failure). If `HEAD_SHA` advanced during the wait, re-resolve it and re-enter §5.2 before re-classifying, so the cache/gate key on the SHA actually under test. Runs from the **main loop, explicitly not via `github-ops`** — the cheap Sonnet executor must not be held open for a long blocking watch (SKILL.md:141-153) |
| Health-cache marker SHA compare (§5.2) | cached comment's `SHA:` line vs `HEAD_SHA` → cache-hit (`HEALTH_OK` parsed from first-line state + `TIER:`) or cache-miss |
| Worktree resolve/create (§5.5.0) | branch name, repo root → worktree path (reuse existing or create fresh), delegated setup via `worktree-hooks.sh` |
| Static-checks execution (§5.5.1) | ordered command list, worktree path → per-command exit/duration/log, first-failure short-circuit |
| Test execution (§5.5.3) | selected `COMMAND:`, worktree path → exit/duration/log; xcodebuild-shaped commands route to the builder sub-agent, others run inline |
| Cache-comment compose + post (§5.6) | health results, selection rationale → the marker comment body, posted via `PERSIST_COMMENT` with `delete_marker_id` when stale |
| Per-phase diff extraction (§6 "Per-phase verification mechanics") | `## Phase tracker` entries, base ref → `git diff <PHASE_START>..<PHASE_END>` per phase, written to scratch |
| Repo merge-config fetch (§8) | owner/repo → `allow_squash_merge` etc., branch-protection 403 handling |
| Merge-policy resolution (§8 "Resolve the merge-approval policy") | config block → `MERGE_POLICY[standard]`, `MERGE_POLICY[story]`, hardcoded `MERGE_POLICY[epic-integration]=ask` |
| Squash subject/body composition (§9) | PR title, labels, issue number → composed Conventional-Commits subject + body, double-suffix stripped |
| Merge execution (§12a/§12b/§12c) | verdict, PR type, `mergeStateStatus`, `MERGE_POLICY` → the exact `gh pr merge` invocation (or skip-with-command) |
| Story-issue close / epic checkbox tick / delivery-log append (§13) | story number, epic number, merged diff → three `gh`/`github-ops` writes, each idempotent against a re-run |
| Cleanup (§14) | branch name, repo root → worktree teardown result, `git worktree remove`, scratch-dir purge |
| Gate-config pin at root SHA | (implicit across §5.4/§8) — the four config blocks are read once per run and held for the rest of the run, not re-read per gate |

## Invariants (with the WHY)

- **Health-cache keyed per head SHA, not re-run needlessly (§5.2).** Re-evaluating an unchanged PR
  costs nothing and leaves an auditable trail — the WHY is efficiency plus a durable audit record of
  *why* a given run was targeted vs full (SKILL.md:262).
- **Sticky veto on DoD mismatch (§6 "Un-tick on rejection").** Once a bullet is un-ticked with
  `evaluator rejected: ...`, no subsequent resolver run re-ticks it without new evidence — the
  disagreement must be resolved by re-planning, new satisfying code, or user intervention, not by the
  resolver silently re-asserting its original claim (SKILL.md:387).
- **Threshold for un-ticking is high — clear semantic mismatch only (§6, "Threshold for un-ticking").**
  An over-eager evaluator un-ticking on soft mismatches turns the sticky veto into a per-phase nitpicker
  that blocks merges on disagreements of interpretation, since un-ticks propagate as merge-blockers
  (SKILL.md:395, :833).
- **Never approve your own PR (§2).** GitHub rejects self-`--approve` with HTTP 422; checking upfront
  avoids a failed write at the very end of the run, after all the evaluation work is done (SKILL.md:69).
- **Never re-verify a `github-ops` write.** `PERSIST_COMMENT` returns the canonical URL on success —
  that *is* the confirmation. Re-fetching to "check it posted" burns context/tokens for nothing and a
  slow-but-buffered result must not be mistaken for a lost one (SKILL.md:41-46, :825).
- **Post-new-before-delete-old is NOT how the cache/log/un-tick writes work — it's the opposite:
  delete-then-repost, staged to disk first.** Every verbatim body (cache comment, delivery log,
  corrected issue body) is staged to a scratch file and posted **byte-for-byte from disk** via
  `gh-persist.sh`, never re-serialized through the sub-agent prompt — that's the surface that filed
  empty bodies in the drafter's #626/#627 incident (SKILL.md:331, :555).
- **Un-tick and delivery-log append are idempotent against a re-run.** The issue-body un-tick, the
  epic-checkbox tick, and the delivery-log entry all check current state first (already-closed,
  already-ticked, already-logged) and skip re-applying — because another tool, or a retried run, may
  have already landed the same effect, and re-applying would corrupt the state or duplicate a log line
  (SKILL.md:706, :723, `epic-delivery-log.md:33`).
- **Teardown runs before worktree removal, never after (§14).** The teardown commands live *inside*
  the worktree; removing the worktree first would delete the very script that releases per-worktree
  resources (simulators, containers, ports, scratch DBs), orphaning them (SKILL.md:761, :849; contract
  in `skills/_shared/worktree-lifecycle.md:69-72`).
- **Teardown is best-effort; a failure never blocks removal (§14).** A leaked resource is recoverable
  by hand; a stuck worktree blocks every future run against the same branch — the asymmetry favors
  always removing (SKILL.md:850).
- **Never run worktree-teardown when the merge didn't run.** Teardown is paired with removal; running
  it without removal leaves a worktree whose resources are already released, so a retry would silently
  fail against missing dependencies (SKILL.md:848).
- **Health-check failure is an unconditional hard block (§7).** A red branch never approves regardless
  of how well the code satisfies the issue — code quality and branch health are orthogonal, and
  approving a red branch defeats the entire point of the gate (SKILL.md:429, :819).
- **Targeted test selection is the default; full-suite is reserved for epic-integration PRs and
  explicitly-labeled PRs (§5.5.2 escalation rules).** An epic-integration diff *is* the union of every
  child story — exactly the integration risk this gate exists to verify, so targeting there would miss
  cross-story interactions; running full for every story PR would be needlessly expensive when CI on
  the integration target is the broader safety net (SKILL.md:199, :820-822).
- **When blast-radius is uncertain, widen rather than narrow (test-selection sub-agent, step 5d).** The
  targeted-selection win on integration tests is bounded; the cost of merging a root-surface regression
  masquerading as a leaf change is the entire next baseline plus diagnostic cost — the asymmetry
  strongly favors over-inclusion (test-selection-sub-agent.md:107-111).
- **The build-delegate sub-agent must not diagnose-and-fix (§5.5.3).** A silent fix loop inside the
  subagent uncaps the wall-clock cost of one delegation, hides code changes from the PR's commit
  history, and turns `HEALTH_OK=true` into a lie the cache comment can't detect (SKILL.md:284, :823).
- **Never mutate shared test infrastructure to "recover" a failing gate (Common pitfalls).** Actions
  like erasing a simulator or wiping a shared device almost always target the *wrong* resource — the
  global default the wrapper falls back to when per-worktree state is missing — surfacing as data loss
  on infrastructure the user was using for something else; the correct response to a failing gate is to
  record it faithfully, not "fix" it (SKILL.md:824).
- **`MERGE_POLICY` defaults to `ask`, not `auto` (§8, §12.0).** A repo that never configures the block
  gets human-in-the-loop merges by default — `auto` is strictly opt-in, so a silent misconfiguration
  can never produce hands-free merges the operator didn't ask for (SKILL.md:488, :828).
- **Epic-integration merges are always gated, regardless of the merge-policy block (§8, §12.0).** An
  epic-integration PR lands every child story's diff on `main` in one merge — a qualitatively different
  risk than a single-issue PR — so this is hardcoded, not configurable (SKILL.md:489, :811).
- **Code merit and merge-readiness are orthogonal — never block approval on `BEHIND`/`DIRTY`/`BLOCKED`
  (§10, §12c, Common pitfalls).** The verdict evaluates whether the diff satisfies the issue; whether the
  branch can currently merge is a separate, transient fact about `mergeStateStatus`/`reviewDecision` at
  this moment. Approve on code merit and surface the merge-readiness blocker separately, rather than
  holding a good diff hostage to a rebase or a pending reviewer (SKILL.md:835: "Don't block approval over
  `mergeStateStatus == BEHIND` or `DIRTY` — approve on code merit and surface the merge-readiness blocker
  separately"). §10 surfaces four flags alongside, not inside, the verdict (SKILL.md:534-538):
  - `mergeStateStatus == BEHIND` → "Branch is behind base — rebase or merge base before merging."
  - `mergeStateStatus == DIRTY` → "Branch has conflicts — resolve before merging."
  - `mergeStateStatus == BLOCKED` → "Merge blocked by branch protection — check status checks."
  - `reviewDecision == REVIEW_REQUIRED` owed to another reviewer → "Awaiting review from @reviewer — your
    approval will still post, but merge may be gated."

  When the verdict is APPROVE but the branch is DIRTY or BLOCKED (or the §12.0 gate's "Other" choice
  recorded an operator-deferred merge), §12c prints the recommended `gh pr merge` command and stops
  without merging — auto-invoking it would just emit a noisy failure, and the operator can resolve the
  blocker and retry (SKILL.md:679-683). The run does **not** proceed to §13 (story bookkeeping) or §14
  (cleanup) on this path; the worktree stays in place for the retry, same as the §12a-failure path
  (SKILL.md:681, :683). The closed-set `merge` marker values on the resulting `## Handoff` — owned by
  `skills/_shared/handoff-format.md:58` — are: `skipped (DIRTY)` and `skipped (BLOCKED)` name an
  unmergeable branch; `skipped (deferred)` is "the reason when the operator approved but chose to merge
  manually later"; `skipped (verdict)` "names a soft-reject" (quoted verbatim, `handoff-format.md:58`).
- **Re-fetch the PR's latest state before the gate and before any merge (§12.0 step 1, §12a).** The
  operator may approve, comment, request changes, merge, or close the PR directly on GitHub while the
  run is in flight; acting on a stale snapshot could fire a merge the operator already handled, or
  double-merge (SKILL.md:595, :640, :829). This is explicitly **not** the forbidden "re-verify your own
  write" — it detects *external* operator action, not confirms this run's own post.
- **Record operator decisions on the PR with clear human attribution (§12.0 step 3).** An override of
  the skill's automated verdict must be visible in the PR's audit trail as a human decision, not folded
  invisibly into the same review shape as an automated one (SKILL.md:830).
- **Flip the PR back to draft on a real COMMENT verdict, but not on a self-approval-downgrade COMMENT
  (§11).** Leaving the PR "ready" after a soft-reject signals the wrong thing on GitHub and forces the
  resolver's existing-PR check to surface it as drift on every re-entry; a self-authored APPROVE posted
  as `--comment` for the 422 workaround is approval-equivalent and must stay ready for manual merge
  (SKILL.md:567, :840).
- **Issue-body un-ticks land before the PR review post (§11 "Issue-body un-ticks").** A reader following
  the review's `## DoD verification` section to the issue must see the un-tick already applied, not a
  stale tick (SKILL.md:571).
- **Doc-grounding and plan-adherence checks read bounded diff/doc slices, never the full diff (§6).**
  `diff_path` can point at 100+ KB; loading it whole would blow the evaluator's context on every PR —
  enumerate changed files first, map to implicated sections, then read only those slices (SKILL.md:403,
  :415, :837).
- **Read grounding docs at the PR's `HEAD_SHA`, not the working-tree copy (§6 "Doc grounding").** The
  evaluator's cwd holds the base-branch copy; a PR that legitimately edits a doc must be judged against
  its own post-edit version, or the check flags a violation the PR already resolved (SKILL.md:399).
- **A filed `## Follow-ups` deferral does not itself excuse an in-scope documented-constraint violation
  (§6 re-adjudication).** A follow-up can launder an in-scope violation past the gate behind a
  fix-later ticket; the severity axis is whether an in-scope constraint is violated, not whether a
  ticket exists for it (SKILL.md:406-409).
- **Plan adherence blocks only on an undisclosed reversal of a locked decision, never on harmless
  in-spirit implementation detail (§6 "Plan adherence").** The plan locks decisions, not lines — treating
  every deviation as a gap would make the evaluator a per-line nitpicker (SKILL.md:415, :844).
- **Never infer per-phase verification annotations that aren't present (Common pitfalls).** Synthesizing
  `## Phase tracker` + `closes-dod` into ad-hoc annotations would create a second, parallel projection
  authority and break the resolver/evaluator boundary the annotation scheme depends on (SKILL.md:834).
- **Story issues need an explicit close because `Fixes #<story-number>` never auto-fires (§13).**
  GitHub's auto-close-on-merge only triggers for a merge into the *default* branch; story PRs merge
  into `epic/<N>-<slug>`, so the linkage is recorded but the close event never happens without an
  explicit `gh issue close` (SKILL.md:687, :846).
- **The epic delivery log is a separate comment from the verified implementation plan.** The plan is
  verified and immutable; the delivery log changes on every story merge — conflating them would force
  either an immutable log or a plan that mutates after verification (`epic-delivery-log.md:12`).
- **Recovering from a failed epic-checkbox/issue-close edit does not block posting the PR review.** The
  verdict is the load-bearing signal; a failed secondary write is surfaced for manual reapplication
  rather than aborting the whole run (SKILL.md:571, :741).
- **Never use `--auto` or `--request-changes` by default.** The repo has `allow_auto_merge: false`, and
  `--comment` (not `--request-changes`) is the project-wide soft-reject convention — `--request-changes`
  is heavy-handed and reserved for an explicit user ask (SKILL.md:430, :473, :842).
- **Never silently write any of the four config blocks to `COMMANDS.md`/`CLAUDE.md`.** Always ask for
  confirmation before modifying project files, even after offering to persist a one-off command list
  the user supplied at the missing-config gate (SKILL.md:195, :847).
- **The draft-PR guard stops evaluation of a `DRAFT`-state PR (§3).** This is also the load-bearing half
  of the resolver/evaluator handoff contract: the resolver flips a PR ready immediately before its
  forward handoff, so a draft reaching here signals genuinely in-progress work, not a missed handoff
  (SKILL.md:92, :839).

## Sub-agents dispatched

| Sub-agent | Reference prompt file | Consumes | Returns |
|---|---|---|---|
| Test selection (`Explore`, read-only) | `skills/github-pr-evaluator/references/test-selection-sub-agent.md` | Worktree path, PR base branch, HEAD SHA, `pr_type`, matched escalation label, verbatim `<!-- pr-evaluator-test-target -->` block | Exactly two sections, literal headers `COMMAND:` and `RATIONALE:` |
| Build/test execution (only for xcodebuild-shaped commands) | `apple-platform-build-tools:builder` (external agent, not a plugin-owned reference file) | The exact test command + cwd, explicitly bounded to "run, report, do not fix" | Pass/fail; on fail, first error + failing test name(s) |
| Residual follow-up filing (§13a, per finding) | `skills/_shared/follow-up-filing.md` protocol, `general-purpose` sub-agent | One residual finding, its type (`bug \| incomplete-feature \| deferred-test \| revise-existing`), parent PR/issue(+epic) reference | Filed issue URL |
| `github-ops` (mechanical GitHub I/O, not a judgment sub-agent) | `agents/github-ops.md` | `GATHER_PR`, `GATHER_ISSUE`, `PERSIST_COMMENT` calls (and `PERSIST_ISSUE_BODY` where available) | Structured envelopes: scalars + scratch-file paths for verbatim content; canonical URLs on writes |

Neither the test-selection sub-agent nor the builder sub-agent can call `AskUserQuestion` (SKILL.md:34,
`skills/_shared/asking-the-user.md:24`); this skill does not dispatch a state-distiller or use the
`skills/_shared/subagent-decision-signal.md` closed-set codes — that vocabulary belongs to the resolver
and the `open-questions` sweep. The evaluator's sub-agents communicate via their own narrow output
contracts (`COMMAND:`/`RATIONALE:`; pass/fail + first error), not the shared decision-signal schema.

## Known bugs / gaps

- **Backward-compatibility fallback for a missing `pr-evaluator-test-target` block borrows the
  resolver's block with an assumed default.** When `pr-evaluator-test-target` is absent but
  `issue-resolver-test-target` is present, the evaluator reuses the resolver's block and assumes
  `full-suite-command` defaults to the bare wrapper command with no flags (SKILL.md:188). This is a
  self-documented assumption, not a verified fact about the project's actual full-suite invocation —
  a project whose full run needs extra flags (e.g. a coverage flag, an environment variable) would
  silently get an incomplete "full suite" on this fallback path.
- **The legacy single-block (`pr-evaluator-health-checks`) path always runs the full command list, with
  no way to get targeted selection until the project migrates.** Self-documented as an explicit tradeoff
  (SKILL.md:969), not treated as a defect requiring a fix, but it is a known behavioral gap relative to
  the split-block path.
- **A broken/force-pushed-away commit SHA in a projection annotation is treated as `unverifiable`, tick
  left in place (§6 "Per-phase verification mechanics" edge cases, SKILL.md:380).** This is a
  deliberate choice ("don't punish the contributor for unrelated branch hygiene") but it does mean a
  rebase-mangled annotation can permanently escape per-phase verification for that bullet — the file
  self-documents this as accepted risk, not an open bug, but it's worth recording as a spec line since
  it's a case where verification silently degrades to "trust the tick."
- **`PERSIST_ISSUE_BODY` availability is conditional** ("If `PERSIST_ISSUE_BODY` is not available in the
  local `github-ops` profile, fall back to a direct `gh issue edit`" — SKILL.md:393). The SKILL.md
  itself flags this as a fallback path rather than asserting the op is universally available, which
  means the un-tick write path has two distinct code paths depending on the `github-ops` profile in
  use — worth carrying into the v2 spec as a case the offline test harness should cover on both arms.
