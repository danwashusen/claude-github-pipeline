# github-pipeline — Architecture (v2)

Target architecture for the v2 rewrite. Prescriptive *how*; the *what/why* is
[prd.md](prd.md), the migration is [implementation.md](implementation.md). Rules here are
deviable defaults: departing from one requires an operator-approved deviation. The
[§12 invariants](#12-invariants-registry) are not deviable.

## §1 System overview & boundaries

One session = one skill = one pass through this shape:

```
operator ─▶ Claude Code session
              SKILL.md router ─▶ prep script (python, one call) ─▶ facts block (JSON + spilled files)
                │                                                        │
                ├── reads exactly one playbook (chosen via routing table + facts)
                ├── dispatches judgment sub-agents (workspace paths in, typed results out)
                └── persists via write scripts ─▶ GitHub (issues, PRs, comments)
```

Scripts own everything deterministic; the model owns judgment; GitHub artifacts and the handoff
are the only cross-session state ([prd.md §4.1](prd.md)).

**Pinned runtime:** Python ≥ 3.9 (the macOS Command Line Tools floor; **stdlib only** — no
third-party packages, no venv, no pip step), `git` ≥ 2.38, `gh` ≥ 2.40 authenticated with repo
scope. Those three are the whole dependency set (v1's shell-script dependencies retired with the
v1 scripts at S20). Scripts are executables (`#!/usr/bin/env python3`) invoked by absolute path via
`${CLAUDE_PLUGIN_ROOT}/scripts/...`; the install dir is read-only.

**Portability (macOS/BSD + Linux/GNU) is a requirement, not an aspiration.** Python is how the
BSD-vs-GNU userland divergence (`sed`/`awk`/`date`/`stat` dialects) is excluded by construction.
Rules: the only external processes a script may spawn are `git` and `gh`, via `subprocess` with
argument lists — never `shell=True` — with exactly one carve-out: `workspace.py`'s hook runner
executes the consuming repo's `<!-- worktree-setup/teardown -->` commands verbatim as repo-owned
opaque shell commands, cwd'd to the workspace; no other script spawns anything else. All text
I/O pins `encoding="utf-8"` (locale defaults differ across platforms); paths go through
`pathlib` and are compared via `os.path.realpath` (macOS `/tmp` is a symlink to
`/private/tmp`); nothing assumes a case-sensitive filesystem.
Module filenames use underscores so the test suite can import them.

**Repo layout (after rewrite):**

```
scripts/
  pipelib/            # shared package: envelope, spill, decisions, sha256, subprocess runner
  workspace.py        # ensure / gc / root-freshness; absorbs the function of worktree-hooks.sh
  parse.py            # dod | oq-links | phases subcommands
  gh_gather.py  gh_pr_gather.py  gh_persist.py  config_block.py   # executor ports (S21)
  prep_drafter.py  prep_researcher.py  prep_planner.py  prep_resolver.py  prep_evaluator.py
  prep_question_sweep.py  prep_question_resolver.py
skills/
  <name>/SKILL.md     # thin router (§9)
  <name>/playbooks/   # one file per behaviorally distinct flow (§5)
  <name>/references/  # judgment sub-agent prompts + contract renderings
  _shared/            # cross-skill contracts (external ones unchanged; see §11)
tests/
  run.py  shim/gh  fixtures/  test_*.py            # stdlib unittest; §10
```

## §2 Component model & where logic lives

Each layer has one job; the dependency rules between them are the architecture.

| Layer | Job | Must never |
|---|---|---|
| `scripts/pipelib/` | Shared envelope/spill/decision/subprocess primitives | Contain skill-specific logic |
| `scripts/*.py` | All deterministic work: fetch, parse, derive state, select refs, name branches, run hooks, write to GitHub | Author prose, classify meaning, make judgment calls |
| `SKILL.md` router | Run prep, apply the routing table, enforce universal invariants, emit the handoff | Contain per-type flow bodies or raw `gh`/`git` write commands |
| Playbooks | The behavioral flow for one route, read on demand | Do ref arithmetic, restate contracts owned by `_shared`, duplicate the router's invariants |
| Judgment sub-agents | Isolated reasoning over prepared inputs (audit, distill, review, select) | Write to GitHub, ask the user, receive raw refs instead of workspace paths |
| `_shared/` contracts | Single source of truth for cross-skill schemas | Be paraphrased in per-skill copies (render, don't restate) |

The governing rule: **facts by script, meaning by model.** A step whose inputs and correct output
are fully defined belongs in a script ([prd.md §9.1](prd.md)); if a needed operation has no
script, extend a script — never inline the operation in a prompt. Prep scripts compose the
executors **in-process** (module imports and function calls), so a session's state assembly is
one Python process, not a subprocess chain.

**The pure-core / thin-emit-wrapper pattern.** Every executor exposes a **pure, non-emitting core**
— `build_*(...) -> (payload, notices, decision | None)` — and its `main()` / `run_*` is a thin emit
wrapper over that core. `decision is None` means success (the caller uses `payload` + `notices`);
`decision is not None` is a `needs_decision` outcome the caller propagates; a partial-but-honest
degradation rides in `notices`, and a hard error still exits non-zero with stderr and no envelope
(the §3 contract). A prep script calls the cores **directly** and acts on the returned `decision`
channel, emitting exactly one envelope of its own — **no `redirect_stdout` capture** of another
script's stdout. `parse.py` (`parse_*`) and `gh_gather.run(stream=)` are the reference shapes; the
S6 pilot's `redirect_stdout` bridge — needed only while `gh_pr_gather` / `workspace` / `config_block`
still emitted-and-exited with no returnable core — was pilot-only and is retired (§4/§6 pilot;
[docs/specs/baseline.md](specs/baseline.md) §5).

## §3 The envelope contract

Every script emits exactly one JSON envelope on stdout.

- **Exit codes.** `0` — envelope present; consult `status`. `2` — usage error (malformed
  invocation; no envelope). Any other non-zero — hard failure (command/network); stderr carries
  the faithful error; no envelope is guaranteed.
- **`status`** is `ok` or `needs_decision`. `needs_decision` is a *valid outcome*, not an error:
  the script completed its read of the world and found a state only the operator can resolve.
- **Decision payload.** `{"status":"needs_decision","decision":{"code":"<CODE>","summary":"…",
  "context":{…},"options":["…"]}}`. The router's single universal rule: render `decision` as one
  `AskUserQuestion` card and act on the answer.
- **Closed decision-code set** (one vocabulary across scripts *and* judgment sub-agents;
  supersedes v1's `subagent-decision-signal.md`). Meaning + canonical emitter per code:
  - `AUTH_REQUIRED` — `gh` authentication/permission failure; detected by the pipelib runner,
    any script.
  - `EMPTY_BODY_FILE` — body-bearing write given an empty or missing staged file;
    `gh_persist.py`.
  - `MARKER_AMBIGUOUS` — more than one candidate marker comment/block where the contract expects
    one; the gathers + `config_block.py`.
  - `TARGET_IS_PR` — the requested issue number resolves to a pull request, not an issue;
    `gh_gather.py`, emitted before any further fetch so a composing prep forwards it before any
    workspace side effect (context carries the linked issue numbers derivable from the PR body).
  - `DOD_MALFORMED` — a DoD bullet or annotation outside the closed set; `parse.py dod`.
  - `PHASES_MALFORMED` — a plan `## Phases` section that doesn't parse; `parse.py phases`.
  - `ROOT_NOT_ON_MAIN` / `ROOT_DIRTY` / `ROOT_DIVERGED` — root-freshness failures;
    `workspace.py`.
  - `BRANCH_IN_USE` — the branch is checked out in another worktree; `workspace.py`.
  - `PLAN_MISSING` — a required plan is absent; prep scripts + the state-distiller.
  - `THREAD_SUPERSEDED_PLAN` — thread direction supersedes the recorded plan; the
    state-distiller.
  - `AMBIGUOUS` — residual non-marker ambiguity (e.g. multiple epic-branch matches); scripts +
    sub-agents.
  - `BLOCKED_ON_USER` — progress requires operator input beyond a listable option set;
    sub-agents.

  Adding a code is a contract change: update this section and the router rule together.
- **Notices** (non-blocking degradations) ride in `notices: []` — e.g. `DEPS_UNSUPPORTED` when
  native issue dependencies are unavailable and prose links are the fallback. Work proceeds.
- **Spill routing.** Any verbatim section (body, thread, diff, marker comment) is inline when
  ≤ threshold and written to the session scratch dir when larger; each section reports
  `*_bytes` + `*_mode: inline|path` (+ `*_path`). Threshold: `GH_PIPELINE_INLINE_THRESHOLD_BYTES`
  (default 25600; legacy `GH_OPS_INLINE_THRESHOLD_BYTES` honored). Diffs and line-comment sets
  are always `path`.
- **Write receipts.** Body-bearing writes return `body_bytes` + `body_sha256`; a zero exit with a
  URL is authoritative and is never re-read to verify (§12).

## §4 The facts block

The prep script's envelope payload is the **facts block**: the session's complete starting state,
assembled in one call ([prd.md §9.2](prd.md)). Common core, extended per skill — worked example
below is `prep_evaluator.py` (S6, the pilot prep script):

```json
{
  "status": "ok",
  "repo": "owner/name",
  "scratch": "/tmp/gh-evaluator-88",
  "root": { "path": "/abs/repo", "sha": "abc123…", "fresh": true },
  "target": { "kind": "pr", "number": 88, "title": "…", "state": "OPEN", "labels": ["story"] },
  "vector": { "type": "story", "mode": "continue", "pr_state": "open-by-you" },
  "suggested_playbook": "story.md",
  "workspace": { "path": "/abs/repo/.worktrees/88-fix-x", "branch": "88-fix-x",
                  "base_ref": "epic/42-journal", "sha": "def456…", "reused": true,
                  "dirty": false, "unpushed_commits": 2 },
  "read_workspaces": { "audit": { "path": "/abs/repo/.worktrees/ro-epic-42-journal", "sha": "0a1b2c…" } },
  "config": { "sha": "abc123…", "static_checks": ["…"], "static_checks_present": true,
               "test_target_present": true, "test_target_raw": "…", "test_target_source": "…",
               "escalation_labels": ["…"], "merge_policy": {"story": "ask", "epic-integration": "ask"},
               "merge_policy_present": true, "legacy_health_checks_present": false,
               "legacy_health_checks_source": null },
  "pr": { "headRefName": "88-fix-x", "baseRefName": "epic/42-journal", "headRefOid": "def456…",
           "isDraft": false, "author": {"login": "…"}, "mergeStateStatus": "CLEAN",
           "reviewDecision": null, "url": "…", "closingIssuesReferences": [{"number": 101}] },
  "pr_type": "story",
  "ci": { "class": "green", "fail_checks": [] },
  "health_cache": { "sha": "def456…", "hit": false },
  "self_review": false,
  "current_user": "…",
  "merge_config": { "allow_squash_merge": true, "allow_merge_commit": false,
                      "allow_rebase_merge": false, "delete_branch_on_merge": true,
                      "allow_auto_merge": false },
  "sections": { "issue_body_mode": "path", "issue_body_bytes": 41230,
                 "issue_body_path": "/tmp/gh-evaluator-88/body.md" },
  "dod": { "101": [ { "index": 1, "text": "…", "checked": true,
                        "annotation": { "form": "closed-by-phase-commit", "phase": 1, "sha": "…" } } ] },
  "blocked_by": { "101": [] },
  "deps_available": { "101": true },
  "attention": [ "work worktree has 2 unpushed commits" ],
  "notices": []
}
```

`dod`/`blocked_by`/`deps_available` are keyed by **closing-issue number** (a string key, since a
PR's `closingIssuesReferences` may name more than one issue) rather than a flat list — a PR that
closes issue #101 also carries #101's `## Definition of done` and native `blocked_by` state, so
the two ride together per issue rather than as an independent top-level list. `read_workspaces`
is present only for a skill that grounds on a second ref (e.g. the resolver's audit read); a
skill with no second view (the evaluator above) omits the key entirely.

Rules: every fact is **re-derivable** — prep supports `--refresh` and is re-run at the points
where currency matters (e.g. pre-merge PR state); `--refresh` re-derives only the volatile facts
named in the calling step's DoD (for the evaluator: PR state, `ci`, `health_cache`) and does
**not** re-run `workspace.py`'s setup hooks or re-read the four gate-config blocks — a `--refresh`
envelope therefore omits `workspace` entirely and reports `config: {}`, relying on the caller's
prior full-run facts block for those. Values the flow needs (`base_ref`, branch name, merge
strategy, audit SHA) appear as facts so playbooks consume them as data (§5). Ambiguities a script
can detect but not resolve surface in `attention` or as a `needs_decision` — never as prompt-side
re-derivation. Inline-mode sections carry the content in the bare field (`issue_body`) alongside
`*_bytes`; additional named read workspaces ride under `read_workspaces`, keyed by purpose.

## §5 Routing & playbooks

- **The state vector** (`vector`) is the tuple that selects behavior — for the pipeline skills:
  issue/PR *type* × session *mode* (fresh / revise / continue) × prior-work state. Every
  component is script-derived.
- **The routing table lives in `SKILL.md`, visibly**: `vector → playbooks/<file>` rows. Prep
  proposes (`suggested_playbook`); the router confirms against the table and may override only
  on evidence the script cannot see (e.g. thread supersedes labels; the drafter's promotion
  override, where the invocation asks a revise target to be re-shaped as an Epic — the receiving
  end of the planner's seam-gate off-ramp), stating why.
- **Parameterize before you playbook.** A branch that differs only in *values* (base ref, branch
  name, merge strategy, cleanup list) is not a branch — the values are facts. A playbook exists
  only for flows that differ in *actions taken* (epic bootstrap files stories; story completion
  ticks the epic checkbox and appends the delivery log).
- **One route per session.** The router selects exactly one playbook; a playbook may
  additionally pull in its skill's single shared spine file — nothing else, and never a second
  playbook. Playbooks are linear narratives with no `if epic … else if story …` interleaving.
  Shared behavior lives once — in the router's invariants or the spine — and playbooks reference
  it rather than restating it.
- **Contract renderings stay point-of-use.** A playbook that emits a shared-schema artifact
  (handoff, DoD annotation, delivery-log entry) renders it per the `_shared` contract file and
  cites it.

## §6 Workspace & grounding model

Two-tier trust topology ([prd.md §8](prd.md)): **project root** is the read-only vantage, always
clean `main`; **`.worktrees/`** holds all mutable and pinned-ref state; `main` changes only via
PR.

| | `work` workspace | `read` workspace |
|---|---|---|
| Path | `.worktrees/<branch>` | `.worktrees/ro-<ref-slug>` |
| Checkout | branch | detached HEAD at `origin/<ref>` |
| Hooks | setup on every ensure (fail-fast); teardown before removal (best-effort) | none |
| Lifecycle | resolver creates; persists across sessions; evaluator tears down + removes after merge (`remove --work`) | reuse per logical ref; **fetch, then reset to current `origin/<ref>` on every ensure**; `workspace.py gc` removes `ro-*` older than `--max-age` (default 7 days) — and only `ro-*` |
| Facts | branch, base_ref, path, SHA, reused, dirty/unpushed state | path + the exact SHA grounded on |

- **`workspace.py` owns the lifecycle**: `ensure --work|--read`, `remove --work` (teardown
  hooks best-effort, then `git worktree remove`; dirty or unpushed state is a decision, never a
  silent discard), `gc`, `root-status`, `lint`, root freshness (verify root on `main` + clean →
  fetch → `--ff-only` → record SHA; failures are `ROOT_NOT_ON_MAIN` / `ROOT_DIRTY` /
  `ROOT_DIVERGED` decisions, never auto-fixed), hook execution (discovering
  `<!-- worktree-setup/teardown -->` blocks via `config_block.py`), the `.worktrees/` exclusion, and
  branch-exclusivity handling (`BRANCH_IN_USE` when the branch is checked out elsewhere). The
  `.worktrees/` exclusion is maintained in the repo's `info/exclude` (resolved via `git rev-parse
  --git-common-dir`, so it applies uniformly whether `--root` is the main checkout or itself a
  linked worktree) — **never** a `<root>/.gitignore` edit: `info/exclude` lives under the git
  directory, outside the working tree, so the idempotent bootstrap write can never surface in
  `git status --porcelain` and can never trip root-freshness on its own write. This also means the
  consuming repo is never asked to commit a plugin-authored `.gitignore` line; a pre-existing
  `.worktrees/` line an earlier run left in a real `.gitignore` is inert and untouched.
- **The single-workspace invariant**: a session's prompt-visible rule is "your workspace is
  `facts.workspace.path`" — every Read/Grep/Explore/test/command targets it by absolute path.
  When a flow needs a second view, prep hands out an additional *named* read workspace in the
  facts block; prompts never select refs.
- **No ref arithmetic in prompts.** `git show ref:path` / `git grep <ref>` are script-internal
  tools only. Grounding SHAs come from the workspace facts (a plan's "planned at `<sha>`" *is*
  its read workspace's HEAD).
- **No ambient cwd.** Scripts `cd` internally (`git -C`); every command and sub-agent dispatch
  names its workspace absolutely; no step depends on where the session happens to sit.
- **Gate config is pinned to trust.** Test-target / checks / merge-policy / OQ-marker blocks are
  read by prep at the recorded root `main` SHA and embedded in facts — never from a PR head, and
  never re-read ambiently mid-session. This pinning binds **workspace-operating** skills (resolver /
  evaluator / planner — the ones that fork a PR-head or pinned-ref workspace off root); a
  **root-only** skill (the drafter) reads its OQ-marker detection hint from the ambient checkout
  instead (v1-faithful) — §12's threat model (a PR weakening its own gates) cannot apply where no
  PR head is ever read.

## §7 GitHub I/O & write discipline

- The four v1 executors are **ported to Python** — `gh_gather.py`, `gh_pr_gather.py`,
  `gh_persist.py`, `config_block.py` (implementation S21) — under the §3 envelope; their
  behavior contracts are otherwise unchanged. Prep scripts compose them in-process; playbooks
  call `gh_persist.py` (and `config_block.py`) directly via Bash for writes.
- **Write path:** the skill stages the verbatim body to its scratch dir
  (`/tmp/gh-<skill>-<N>/…`) and passes the path; `gh_persist.py` verifies the round-trip hash
  itself and reports `body_sha256` in the envelope, failing on mismatch — callers act on
  `status`, never re-hash prompt-side. The leading empty-body gate stays (the #626/#627 race
  fix); an empty staged file is an `EMPTY_BODY_FILE` decision.
- **Atomicity & idempotency stay as built:** marker replacement posts the new comment before
  deleting the old; `close` on a closed issue is a no-op; native-dependency writes are
  capability-gated (`DEPS_UNSUPPORTED` notice + prose-link fallback).
- **PR-only landing, operator-gated.** Skills that change tracked files (`setup` config blocks,
  `question-sweep` doc fixes, `doc-reviewer` applied findings, resolver code) do so only in a
  work workspace ([prd.md §8.2](prd.md)). The resolver opens its PR as part of its flow; the
  three maintenance tools stage approved edits and **offer** the landing (commit + push + PR) as
  one explicit final gate — on decline they perform no git actions and report the workspace path
  + ready-to-run commands in the summary. Consuming repos may set a merge-policy entry (e.g.
  `docs: auto`) to keep accepted maintenance PRs low-ceremony.
- **No executor agent.** v1's `github-ops` sub-agent is retired; its responsibilities land here:

| v1 `github-ops` rule | v2 owner |
|---|---|
| 1 Faithful, never summarized | Scripts emit verbatim sections + `sha256`; playbooks read spilled files directly |
| 2 Posts only what it's given | `gh_persist.py` staged-path convention + empty-body gate |
| 3 `DECISION_NEEDED`, can't ask user | `status: needs_decision` envelope + the router's universal card rule (§3) |
| 4 Report errors faithfully | Bash tool surfaces script stderr to the main loop unmediated |
| 5 No nesting | Moot — there is no executor agent |
| 6 Successful write is self-confirming | Unchanged rule, stated in §3/§12 |
| 7 Use the bundled scripts, never hand-roll `gh` | Unchanged, enforced on the main loop: prompts contain no raw `gh` write/fetch-envelope commands |
| 8 Spill threshold | Unchanged, in scripts (§3) |

## §8 Judgment sub-agents

The isolation architecture for reasoning that must not pollute the main loop's context. All are
context-blind, receive **workspace paths and prep-staged files** (never refs), return their
result or a typed §3 decision code, cannot call `AskUserQuestion`, and never write to GitHub.

| Sub-agent | Caller | Consumes | Returns |
|---|---|---|---|
| state-distiller | resolver | issue thread + plan text (paths) | current-state / effective-plan brief |
| fitness audit | resolver | read workspace + issue + plan | findings by dimension (incl. plan-vs-code currency) |
| plan reviewer | planner | plan draft + read workspace | findings by dimension |
| issue reviewer | drafter | draft + repo context | findings by dimension |
| research validator | researcher | dossier draft | findings by dimension |
| test-selection | resolver, evaluator | diff scope + pinned test config | `COMMAND:` + `RATIONALE:` |
| review-loop | resolver | PR + review verdict file | items-addressed JSON |
| question-status reader | question-sweep, question-resolver | question thread (path) | status or `AMBIGUOUS` |

Model pins carry over from v1 frontmatter verbatim (skills stay `opus` at their existing effort
levels); changing a pin is a deviation through the normal gate. There are no mechanical-relay
agents: if a task is deterministic it is a script, not a sub-agent.

## §9 Skill anatomy

Every `SKILL.md` is a router with the same four sections, in order (for the standalone tools:
Prep collapses to a no-prep note where the skill has none — currently doc-reviewer — and
section 4 is **Summary** per [prd.md §6](prd.md), not Handoff):

1. **Prep** — the one prep-script invocation and the `needs_decision` card rule.
2. **Route** — the visible `vector → playbook` table and the override rule (§5).
3. **Invariants** — the universal rules for every route: single-workspace, staged-body writes,
   gates-only-for-decisions, faithful reporting, handoff-on-clean-exit.
4. **Handoff** — pointer to the shared schema + this skill's rendering reference.

Size bar: a router fits comfortably in one default `Read` (≤ ~150 lines) — the v1 forced-read
workaround and the resolver-local `§P-ID` scheme are both retired.

Authorship rule: a v2 router + playbook set is written **from scratch** against the skill's S1
spec and this section — never derived by editing v1 `SKILL.md` prose down. Only two classes of
v1 text are carried: the [prd.md §7](prd.md)-frozen artifact renderings (byte-compatible by
requirement) and the judgment sub-agent prompts a cutover step explicitly marks as carried. Standalone tools keep
`disable-model-invocation: true`. Scratch dirs are uniformly `/tmp/gh-<skill>-<N>/`. Skill and
directory names are the [prd.md §2](prd.md) fixed names; nothing echoes the `github-pipeline`
namespace.

## §10 Testing architecture

The deterministic layer is tested offline ([prd.md §9.3](prd.md)); prompts are validated by
census greps.

- **Harness:** `tests/run.py`, stdlib `unittest` discovery — no third-party test framework,
  nothing to vendor or install. No network, no live repo. The suite must pass on **both macOS
  and Linux** (Linux via any container or host; invocation documented in `tests/README.md`).
- **`gh` shim:** `tests/shim/gh` (itself a small Python executable named `gh`) sits first on
  `PATH` and replays canned responses from
  `tests/fixtures/<case>/` keyed on the argv it receives; unexpected argv fails the test. Scripts
  under test never notice.
- **Git sandbox:** workspace/lifecycle tests run against a temp origin (bare repo) + clone built
  per test; no shim needed.
- **Coverage bar:** every script's happy path, every §3 decision code it can emit, and envelope
  schema conformance (shared assertion helpers) for every emitting script.
- **Prompt-side validators** (no offline harness exists for prose): the contract-token census
  and banned-pattern greps from `CLAUDE.md`, extended with: zero old-name hits, plus the two
  drift-class validators below.
  - **Raw-`gh` rule (the §7 rule-7 form).** Zero raw `gh` **write / fetch-envelope** invocations in
    `skills/` — any `gh` op that *has* a bundled script (writes → `gh_persist.py`; fetch-envelopes →
    `gh_gather.py` / `gh_pr_gather.py`) must go through it, never a hand-rolled `gh`. **Excepting three
    scriptless executors** (no `gh_persist.py` op covers them) — these are sanctioned raw-`gh`
    executors, not violations, because the behaviors they implement are spec'd: `gh pr merge` (merge
    execution) and `gh pr ready --undo` (the soft-reject draft-flip on Needs Revision / Reject), both
    the evaluator's and both cited to [docs/specs/evaluator.md](specs/evaluator.md) ("Merge execution"
    and its merge-approval decision-gate row, "flips PR to draft"); and `gh pr ready <N>` (the
    resolver's last-planned-phase-shipped draft→ready flip), cited to
    [docs/specs/resolver.md](specs/resolver.md) (its invariant: the flip runs immediately before the
    handoff, or the evaluator's draft-PR guard deadlocks it — carried from v1 SKILL.md:896). §7 rule 7
    is the source of truth for which ops are script-backed.
  - **`git`-ref rule (ref-arithmetic-scoped).** Zero `git show <ref>:<path>` / `git grep <ref>` in
    `skills/` — a bare `git show <commit>` single-commit diff view is permitted; only the
    `<ref>:<path>` extraction (and `git grep <ref>`) is the banned ref-arithmetic form.

## §11 Migration & coexistence

- Cutover is **per skill**, in the [implementation.md](implementation.md) order. Old and new
  skills interoperate through the [prd.md §7](prd.md) artifacts only, so a v2 evaluator works a
  PR a v1 resolver opened.
- A v1 skill directory is deleted only after its v2 replacement passes the parity protocol
  ([prd.md §9.5](prd.md)).
- `_shared/` files defining **external** artifacts (handoff format, DoD annotations,
  open-question links/detection, question-issue, epic-delivery-log, worktree block formats) are
  preserved; **internal** coordination files are superseded per §3 (`subagent-decision-signal.md`,
  removed at S20) and §6 (`worktree-lifecycle.md`'s mechanics folded into `workspace.py` at S20 —
  the file now carries only the consuming-repo block format; the ownership rules live here).
- The v1 executor sub-agent prompt under `agents/` and every v1 `scripts/*.sh` were removed in the
  final cleanup step (S20), after their last v1 caller was cut over. Nothing in the tree references
  them; `tests/test_v1_retirement.py` is the standing guard.

## §12 Invariants registry

Non-negotiable. Each carries its enforcement point; a change here is a constitution-level event,
not a deviation.

| Invariant | Why (short) | Enforced by |
|---|---|---|
| Empty-body gate: no body-bearing write without a non-empty staged file | #626/#627 empty-body race | `gh_persist.py` size check + `EMPTY_BODY_FILE` + tests |
| Bodies cross the prompt boundary as paths, never re-serialized | same race | staged-path convention (§7) |
| Byte fidelity: persists verify the round-trip hash and return `body_sha256` | silent mangling is invisible | `gh_persist.py` + tests |
| Successful write is self-confirming; never re-read to verify | re-reads reintroduce races | §3 rule + router invariant |
| Post-new-before-delete-old on marker replacement | a crash must not lose the marker | `gh_persist.py` + tests |
| Spill threshold on verbatim sections | context blowout | `pipelib` spill + tests |
| Capability-gated degradation (native deps) with notice | consuming repos vary | `gh_persist.py`/`gh_gather.py` + tests |
| Root is never written; skills never branch/commit/stash there | trust topology (§6) | `workspace.py` decisions + prompt invariant |
| Gate config is read only at the recorded root `main` SHA, never from a PR head | a PR must not weaken its own gates (§6) | prep scripts + tests |
| All tracked-file changes land via PR | write-protected `main` | prompt invariant + review |
| No ref arithmetic, no raw `gh` writes, no ambient cwd in prompts | the drift class the rewrite exists to kill | §10 prompt validators (carve-outs in §10: `gh pr merge` / `gh pr ready` [evaluator `--undo`; resolver draft→ready flip]; bare `git show <commit>`) |
| Contract tokens are frozen (marker strings, op names, closed sets) | cross-skill/GitHub parse compatibility | census greps (§10) |
| Skills are stack-agnostic (gated integrations + ≥2-stack examples only) | multi-stack product | banned-pattern greps (§10) |
| Session-per-skill; no autonomous stage chaining | context isolation is the design | prompt invariant + review |
| Scripts never author prose; sub-agents never write to GitHub | role separation (§2) | review + tests |
| Scripts are stdlib-only Python spawning only `git`/`gh` (sole carve-out: `workspace.py`'s hook runner, §1) | excludes the BSD/GNU userland divergence class | review + dual-platform suite runs (§10) |
