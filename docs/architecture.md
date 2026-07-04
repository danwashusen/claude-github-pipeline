# github-pipeline — Architecture (v2)

Target architecture for the v2 rewrite. Prescriptive *how*; the *what/why* is
[prd.md](prd.md), the migration is [implementation.md](implementation.md). Rules here are
deviable defaults: departing from one requires an operator-approved deviation. The
[§12 invariants](#12-invariants-registry) are not deviable.

## §1 System overview & boundaries

One session = one skill = one pass through this shape:

```
operator ─▶ Claude Code session
              SKILL.md router ─▶ prep script (bash, one call) ─▶ facts block (JSON + spilled files)
                │                                                        │
                ├── reads exactly one playbook (chosen via routing table + facts)
                ├── dispatches judgment sub-agents (workspace paths in, typed results out)
                └── persists via write scripts ─▶ GitHub (issues, PRs, comments)
```

Scripts own everything deterministic; the model owns judgment; GitHub artifacts and the handoff
are the only cross-session state ([prd.md §4.1](prd.md)).

**Pinned runtime:** `bash` 3.2+ (macOS default; no bash-4-only features), `git` ≥ 2.38,
`gh` ≥ 2.40 authenticated with repo scope, `jq` ≥ 1.6. Scripts are invoked by absolute path via
`${CLAUDE_PLUGIN_ROOT}/scripts/...`; the install dir is read-only.

**Repo layout (after rewrite):**

```
scripts/
  lib.sh              # envelope, spill, decision, sha256 helpers — sourced by every script
  workspace.sh        # ensure / gc / root-freshness; absorbs worktree-hooks.sh
  parse.sh            # dod | oq-links | phases subcommands
  gh-gather.sh  gh-pr-gather.sh  gh-persist.sh  config-block.sh   # retained executors
  prep-drafter.sh  prep-researcher.sh  prep-planner.sh  prep-resolver.sh  prep-evaluator.sh
  prep-question-sweep.sh  prep-question-resolver.sh
skills/
  <name>/SKILL.md     # thin router (§9)
  <name>/playbooks/   # one file per behaviorally distinct flow (§5)
  <name>/references/  # judgment sub-agent prompts + contract renderings
  _shared/            # cross-skill contracts (external ones unchanged; see §11)
tests/
  run.sh  vendor/bats-core/  shim/gh  fixtures/  *.bats            # §10
```

## §2 Component model & where logic lives

Each layer has one job; the dependency rules between them are the architecture.

| Layer | Job | Must never |
|---|---|---|
| `scripts/lib.sh` | Shared envelope/spill/decision primitives | Contain skill-specific logic |
| `scripts/*.sh` | All deterministic work: fetch, parse, derive state, select refs, name branches, run hooks, write to GitHub | Author prose, classify meaning, make judgment calls |
| `SKILL.md` router | Run prep, apply the routing table, enforce universal invariants, emit the handoff | Contain per-type flow bodies or raw `gh`/`git` write commands |
| Playbooks | The behavioral flow for one route, read on demand | Do ref arithmetic, restate contracts owned by `_shared`, duplicate the router's invariants |
| Judgment sub-agents | Isolated reasoning over prepared inputs (audit, distill, review, select) | Write to GitHub, ask the user, receive raw refs instead of workspace paths |
| `_shared/` contracts | Single source of truth for cross-skill schemas | Be paraphrased in per-skill copies (render, don't restate) |

The governing rule: **facts by script, meaning by model.** A step whose inputs and correct output
are fully defined belongs in a script ([prd.md §9.1](prd.md)); if a needed operation has no
script, extend a script — never inline the operation in a prompt.

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
  supersedes v1's `subagent-decision-signal.md`):
  `AUTH_REQUIRED`, `EMPTY_BODY_FILE`, `MARKER_AMBIGUOUS`, `DOD_MALFORMED`, `PHASES_MALFORMED`,
  `ROOT_NOT_ON_MAIN`, `ROOT_DIRTY`, `ROOT_DIVERGED`, `BRANCH_IN_USE`, `PLAN_MISSING`,
  `THREAD_SUPERSEDED_PLAN`, `AMBIGUOUS`, `BLOCKED_ON_USER`. Adding a code is a contract change:
  update this section and the router rule together.
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
assembled in one call ([prd.md §9.2](prd.md)). Common core, extended per skill:

```json
{
  "status": "ok",
  "repo": "owner/name",
  "root": { "path": "/abs/repo", "sha": "abc123…", "fresh": true },
  "target": { "kind": "pr", "number": 88, "title": "…", "state": "open", "labels": ["story"] },
  "vector": { "type": "story", "mode": "continue", "pr_state": "open-by-you" },
  "suggested_playbook": "story.md",
  "workspace": { "kind": "work", "path": "/abs/repo/.worktrees/88-fix-x", "branch": "88-fix-x",
                  "base_ref": "epic/42-journal", "sha": "def456…", "reused": true },
  "config": { "sha": "abc123…", "test_target": "…", "static_checks": ["…"], "merge_policy": {"story": "ask"} },
  "sections": { "issue_body_mode": "path", "issue_body_path": "/tmp/gh-evaluator-88/body.md" },
  "dod": [ { "index": 1, "text": "…", "checked": true, "annotation": { "form": "closed-by-phase", "phase": 1, "sha": "…" } } ],
  "open_questions": [ { "issue": 101, "disposition": "in-scope (blocked)", "tracker_state": "open", "decision_marker": false } ],
  "attention": [ "work worktree has 2 unpushed commits" ],
  "notices": []
}
```

Rules: every fact is **re-derivable** — prep supports `--refresh` and is re-run at the points
where currency matters (e.g. pre-merge PR state). Values the flow needs (`base_ref`, branch name,
merge strategy, audit SHA) appear as facts so playbooks consume them as data (§5). Ambiguities a
script can detect but not resolve surface in `attention` or as a `needs_decision` — never as
prompt-side re-derivation.

## §5 Routing & playbooks

- **The state vector** (`vector`) is the tuple that selects behavior — for the pipeline skills:
  issue/PR *type* × session *mode* (fresh / revise / continue) × prior-work state. Every
  component is script-derived.
- **The routing table lives in `SKILL.md`, visibly**: `vector → playbooks/<file>` rows. Prep
  proposes (`suggested_playbook`); the router confirms against the table and may override only
  on evidence the script cannot see (e.g. thread supersedes labels), stating why.
- **Parameterize before you playbook.** A branch that differs only in *values* (base ref, branch
  name, merge strategy, cleanup list) is not a branch — the values are facts. A playbook exists
  only for flows that differ in *actions taken* (epic bootstrap files stories; story completion
  ticks the epic checkbox and appends the delivery log).
- **One playbook per session.** The router reads exactly one; playbooks are linear narratives
  with no `if epic … else if story …` interleaving. Shared behavior lives once — in the router's
  invariants or a spine section — and playbooks reference it rather than restating it.
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
| Lifecycle | resolver creates; persists across sessions; evaluator tears down + removes after merge | reuse per logical ref; **reset to current `origin/<ref>` on every ensure**; `workspace.sh gc` removes `ro-*` older than `--max-age` (default 7 days) — and only `ro-*` |
| Facts | branch, base_ref, path, SHA, reused, dirty/unpushed state | path + the exact SHA grounded on |

- **`workspace.sh` owns the lifecycle**: `ensure --work|--read`, `gc`, root freshness
  (verify root on `main` + clean → fetch → `--ff-only` → record SHA; failures are
  `ROOT_NOT_ON_MAIN` / `ROOT_DIRTY` / `ROOT_DIVERGED` decisions, never auto-fixed), hook
  execution (discovering `<!-- worktree-setup/teardown -->` blocks via `config-block.sh`), the
  `.gitignore` entry, and branch-exclusivity handling (`BRANCH_IN_USE` when the branch is checked
  out elsewhere).
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
  never re-read ambiently mid-session.

## §7 GitHub I/O & write discipline

- The four retained executors (`gh-gather.sh`, `gh-pr-gather.sh`, `gh-persist.sh`,
  `config-block.sh`) move under the §3 envelope; their behavior contracts are otherwise
  unchanged. Prep scripts compose them; playbooks call `gh-persist.sh` (and `config-block.sh`)
  directly via Bash for writes.
- **Write path:** the skill stages the verbatim body to its scratch dir
  (`/tmp/gh-<skill>-<N>/…`), passes the path, and verifies the returned `body_sha256`. The
  leading `test -s` empty-body gate stays (the #626/#627 race fix); an empty staged file is an
  `EMPTY_BODY_FILE` decision.
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
| 2 Posts only what it's given | `gh-persist.sh` staged-path convention + empty-body gate |
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

Every `SKILL.md` is a router with the same four sections, in order:

1. **Prep** — the one prep-script invocation and the `needs_decision` card rule.
2. **Route** — the visible `vector → playbook` table and the override rule (§5).
3. **Invariants** — the universal rules for every route: single-workspace, staged-body writes,
   gates-only-for-decisions, faithful reporting, handoff-on-clean-exit.
4. **Handoff** — pointer to the shared schema + this skill's rendering reference.

Size bar: a router fits comfortably in one default `Read` (≤ ~150 lines) — the v1 forced-read
workaround and the resolver-local `§P-ID` scheme are both retired. Standalone tools keep
`disable-model-invocation: true`. Scratch dirs are uniformly `/tmp/gh-<skill>-<N>/`. Skill and
directory names are the [prd.md §2](prd.md) fixed names; nothing echoes the `github-pipeline`
namespace.

## §10 Testing architecture

The deterministic layer is tested offline ([prd.md §9.3](prd.md)); prompts are validated by
census greps.

- **Harness:** `tests/run.sh` runs bats-core (vendored under `tests/vendor/`). No network, no
  live repo.
- **`gh` shim:** `tests/shim/gh` sits first on `PATH` and replays canned responses from
  `tests/fixtures/<case>/` keyed on the argv it receives; unexpected argv fails the test. Scripts
  under test never notice.
- **Git sandbox:** workspace/lifecycle tests run against a temp origin (bare repo) + clone built
  per test; no shim needed.
- **Coverage bar:** every script's happy path, every §3 decision code it can emit, and envelope
  schema conformance (shared jq assertions) for every emitting script.
- **Prompt-side validators** (no offline harness exists for prose): the contract-token census
  and banned-pattern greps from `CLAUDE.md`, extended with: zero old-name hits, zero `git show`
  in `skills/`, zero raw `gh` write invocations in `skills/`.

## §11 Migration & coexistence

- Cutover is **per skill**, in the [implementation.md](implementation.md) order. Old and new
  skills interoperate through the [prd.md §7](prd.md) artifacts only, so a v2 evaluator works a
  PR a v1 resolver opened.
- A v1 skill directory is deleted only after its v2 replacement passes the parity protocol
  ([prd.md §9.5](prd.md)).
- `_shared/` files defining **external** artifacts (handoff format, DoD annotations,
  open-question links/detection, question-issue, epic-delivery-log, worktree block formats) are
  preserved; **internal** coordination files are superseded per §3 (`subagent-decision-signal.md`)
  and §6 (`worktree-lifecycle.md` mechanics fold into `workspace.sh`; the ownership rules move
  here).
- `agents/github-ops.md` and `scripts/worktree-hooks.sh` are removed in the final cleanup step,
  after their last caller is cut over.

## §12 Invariants registry

Non-negotiable. Each carries its enforcement point; a change here is a constitution-level event,
not a deviation.

| Invariant | Why (short) | Enforced by |
|---|---|---|
| Empty-body gate: no body-bearing write without a non-empty staged file | #626/#627 empty-body race | `gh-persist.sh` `test -s` + `EMPTY_BODY_FILE` + tests |
| Bodies cross the prompt boundary as paths, never re-serialized | same race | staged-path convention (§7) |
| Byte fidelity: persists return `body_sha256`; caller verifies | silent mangling is invisible | `lib.sh` + tests |
| Successful write is self-confirming; never re-read to verify | re-reads reintroduce races | §3 rule + router invariant |
| Post-new-before-delete-old on marker replacement | a crash must not lose the marker | `gh-persist.sh` + tests |
| Spill threshold on verbatim sections | context blowout | `lib.sh` spill + tests |
| Capability-gated degradation (native deps) with notice | consuming repos vary | `gh-persist.sh`/`gh-gather.sh` + tests |
| Root is never written; skills never branch/commit/stash there | trust topology (§6) | `workspace.sh` decisions + prompt invariant |
| All tracked-file changes land via PR | write-protected `main` | prompt invariant + review |
| No ref arithmetic, no raw `gh` writes, no ambient cwd in prompts | the drift class the rewrite exists to kill | §10 prompt validators |
| Contract tokens are frozen (marker strings, op names, closed sets) | cross-skill/GitHub parse compatibility | census greps (§10) |
| Skills are stack-agnostic (gated integrations + ≥2-stack examples only) | multi-stack product | banned-pattern greps (§10) |
| Session-per-skill; no autonomous stage chaining | context isolation is the design | prompt invariant + review |
| Scripts never author prose; sub-agents never write to GitHub | role separation (§2) | review + tests |
