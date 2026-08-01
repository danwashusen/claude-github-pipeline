# github-pipeline — Product Requirements (v2)

Product truth for the **github-pipeline** Claude Code plugin, authored as the baseline for the v2
rewrite: it states the behavior the rewrite must preserve (derived from v1) and the requirements it
adds. Authoritative-but-mutable; changes route through the normal conflict gate. *What* and *why*
live here; *how* lives in [architecture.md](architecture.md); the migration itself in
[implementation.md](implementation.md).

## §1 Product overview & goals

github-pipeline turns GitHub issue delivery into a conveyor of operator-driven Claude Code
sessions — **draft → research → plan → resolve → evaluate** — plus standalone maintenance tools.
Its outcomes:

- Every unit of work is captured as a well-formed, reviewed GitHub issue before code is written.
- Implementation happens against a verified, citable plan pinned to the code it was planned on.
- Every change lands on a write-protected `main` through a PR that has been health-checked and
  judged against the issue's Definition of done.
- The human operator decides at every consequential gate — and only there.

v2 goals, with the operator workflow preserved exactly: (1) every deterministic step is script
work, not model work; (2) the prompt surface is reduced to judgment and contracts; (3) a
session's loaded instructions contain no other type's flow — a router plus one playbook (§9.4);
(4) the deterministic layer is testable offline.

## §2 Personas & terminology

- **Operator** — the single human who starts each session, answers gates, and approves persists
  and merges. Exactly one; see §3 non-goals.
- **Consuming repo** — the GitHub repository the pipeline works on. Any tech stack. Provides
  configuration via marker blocks in its `CLAUDE.md`/`COMMANDS.md`. Its `main` is write-protected:
  every change lands via PR.
- **Skills** — fixed names. Pipeline stages: `drafter`, `researcher`, `planner`, `resolver`,
  `evaluator`. Standalone tools: `setup`, `question-sweep`, `question-resolver`, `doc-reviewer`,
  `workspace-open`, `workspace-close`. Invoked as `/github-pipeline:<name>`.
- **Session** — one Claude Code run of one skill. **Handoff** — the summary + copy-pasteable
  next-command block a pipeline session emits on clean exit; the only bridge between sessions.
- **Gate** — an explicit decision question put to the operator.
- **Router / playbook** — a skill's always-loaded routing prompt (the router) and the single
  on-demand flow document (the playbook) a session executes.
- **Currency** — whether recorded knowledge still matches the present state of the world (docs
  vs code, plan vs code, external facts vs today).
- **Workspace** — a git worktree under the consuming repo's `.worktrees/`. Two kinds: a **work
  workspace** (branch checkout, where changes are made — opened by the operator with
  `workspace-open`, the session started inside it, released with `workspace-close`) and a
  **read workspace** (a pinned, read-only checkout, script-internal grounding plumbing).
- **Question registry** — the set of `question`-labelled issues; the registry of record for open
  questions (docs are sources, never the registry).

## §3 Scope

**In scope for v2:** all nine skills (v3 adds the two workspace tools, making eleven), the bundled scripts, the shared cross-skill contracts, the
plugin manifests, and offline tests for the deterministic layer.

**Out of scope / non-goals:**

- No new pipeline stages, no reordering or merging of stages.
- No schema changes to persisted GitHub artifacts (§7); v1-written artifacts must remain readable
  by v2 and vice versa on the same issues and PRs.
- No autonomous chaining: a skill never starts another skill's session or crosses the session
  boundary itself; re-routes are carried by the handoff for the operator to run.
- No multi-operator concurrency features beyond what git and GitHub natively enforce.
- No stack-specific behavior in skills; stack knowledge lives only in consuming-repo
  configuration and gated integrations.
- Not a general-purpose GitHub client: a skill performs only the operations its stage requires.

## §4 Pipeline workflow requirements

- **§4.1 Session-per-stage.** Each pipeline stage runs in its own session with fresh context.
  Cross-session state travels only through GitHub artifacts (§7) and the handoff.
- **§4.2 Handoff.** On clean exit a pipeline skill emits a `## Handoff` per the shared handoff
  schema: cold-readable state using the closed-set state markers, plus the exact next command.
  A re-route to a prior stage carries a `Why:` line stating the evidence for the regression.
- **§4.3 Gates only for genuine decisions.** The operator is asked when a choice changes the
  outcome (scope, deviation, merge, destructive action) — never to confirm a fact a tool can
  derive. A mechanical blocker (auth failure, ambiguous state, dirty root) is presented as a
  single decision card with concrete options.
- **§4.4 Faithful reporting.** Sessions lead with the outcome; failures are reported verbatim
  with their evidence; skipped work is declared, not implied done.

## §5 Pipeline stage requirements

Operator-visible behavior each stage must provide. The detailed v1 behavior inventories that
ground these are produced by implementation step S1. Lettered items are individually citable
(e.g. §5.4(b)).

- **§5.1 drafter.**
  - (a) Captures informal feedback as a filed, template-conformant issue.
  - (b) Classifies bug / incomplete / feature / epic / question, asking only when signals
    genuinely conflict.
  - (c) Grounds framing in the consuming repo's PRD, surfacing contradicts / extends / gap
    tensions as a `## PRD impact` note and conflict gate.
  - (d) Runs an adversarial draft review before filing.
  - (e) Splits an epic into story issues with the epic body linking them.
  - (f) Never silently absorbs an unresolved open question from a source doc: each is matched
    against the question registry (search before file), filed if untracked, and recorded on the
    build issue per disposition — `scoped-out`, `in-scope (blocked)` (with a native `blocked by`
    dependency), or `provisional-default`.
  - (g) Revise mode updates an existing issue while preserving its plan pointer.
  - (h) Nothing is filed or edited without operator confirmation.
- **§5.2 researcher.**
  - (a) Currency-driven external research: declines when no currency risk exists; otherwise
    derives research questions (broad mode) or answers the given ones (targeted mode).
  - (b) Produces a dossier comment with tiered, dated sources, validated by an isolated review
    before persisting.
  - (c) The dossier is input-not-authority: implications and tensions, never settled decisions.
  - (d) Revise mode refreshes an existing dossier — re-fetching moved sources, re-dating claims,
    answering newly posed questions — and replaces the prior comment.
- **§5.3 planner.**
  - (a) Produces a reviewed implementation plan as a durable issue comment, grounded on an
    explicitly recorded commit SHA (§8.4), citing docs by stable anchor and code by precedent.
  - (b) Locks its decisions and gates genuine tradeoffs to the operator.
  - (c) Declines to plan a change that requires no design decision (a single obvious edit with
    no alternatives worth recording).
  - (d) Epic plans pin cross-story contracts and stay immutable; story plans are authored
    just-in-time against the epic's current state, including what prior stories actually
    delivered.
  - (e) Revise mode reconciles the existing plan against thread, PR, and DoD state.
  - (f) Never resolves an open question itself.
  - (g) Before recording any open question as unfiled it searches the question registry; a
    tracked question is always cited by its issue number.
  - (h) Handoffs render the open-questions line in every session shape, including combined
    epic + story sessions.
- **§5.4 resolver.**
  - (a) Implements exactly one issue per session against its verified plan.
  - (b) Before building: audits fitness (including plan-vs-code currency) and hard-refuses an
    issue whose open questions leave it `in-scope (blocked)` with the blocking question still
    open.
  - (c) Builds only in the work workspace the session was started in, verified at session
    start (§8.3); refuses on a mismatched, stale, or root-seated checkout.
  - (d) Projects Definition-of-done ticks with annotations as phases ship.
  - (e) Loops with code review until approved.
  - (f) Multi-phase issues ship one phase per PR, tracked in a `## Phase tracker` section of the
    PR body (§7).
  - (g) Comment-only outcomes are supported without code changes.
  - (h) When the plan does not survive contact with the code, re-routes to the planner or
    drafter with the evidence.
- **§5.5 evaluator.**
  - (a) The verdict-and-merge authority.
  - (b) Runs the health gate (CI plus the consuming repo's configured checks), caching the
    result per head SHA in the `<!-- pr-evaluator-health-cache:v1 -->` comment (§7).
  - (c) Verifies DoD ticks against their annotations, un-ticking with a sticky veto on mismatch.
  - (d) Judges scope match, doc grounding, and plan adherence.
  - (e) Issues APPROVE or COMMENT review actions and never approves its own PR.
  - (f) Merges per the configured per-PR-type policy (default `ask`) and the strategy rules for
    the PR's shape.
  - (g) On story merge: closes the story, ticks the epic checkbox, appends the epic delivery
    log.
  - (h) Leaves the work workspace in place after merge and hands the operator the
    `workspace-close` command (the one reclamation path — merged, abandoned, or mis-opened).

## §6 Standalone tool requirements

All six run only on explicit invocation and end with a plain summary — not a pipeline handoff.
The four report-then-apply tools change nothing without the operator seeing the proposal;
tracked-file edits follow §8.2: staged in a workspace, with the landing offered as a final gate.
The two workspace tools (§6.5/§6.6) edit no tracked files — their action is the workspace
lifecycle itself, and the explicit invocation is the authorization.

- **§6.1 setup.** Proposes and reconciles the consuming repo's configuration blocks: inventories
  existing blocks, drafts grounded candidates from repo evidence, interviews the operator for
  what can't be inferred, and validates what it wrote.
- **§6.2 question-sweep.** Reconciles the open questions found across the consuming repo's docs
  against the question registry: files untracked questions, repairs doc↔issue links in both
  directions, flags stale doc state, and reports orphans.
- **§6.3 question-resolver.** Assisted closing of one question issue: grounds the constraints and
  decision space in the pinned docs, records the operator's decision as a durable marker comment,
  optionally closes the issue, and proposes — never applies — the doc fold-back. The operator
  decides; the skill records.
- **§6.4 doc-reviewer.** Reviews a single project doc against its bundled authoring guide and
  offers to apply accepted findings.
- **§6.5 workspace-open.** Opens the work workspace for an issue: adopts or creates the issue's
  GitHub-linked branch (the native "create a branch for this issue"; degrades to a local branch
  with a notice where linking is unsupported), owns epic integration-branch creation, creates or
  reuses the worktree under `.worktrees/`, runs the repo's worktree-setup hooks, and tells the
  operator where to start the next session. A foreign open/draft PR gates before any side
  effect. Never plans or resolves anything itself.
- **§6.6 workspace-close.** Releases a work workspace (branch name or issue number): runs the
  worktree-teardown hooks, then removes the worktree — gated on dirty/unpushed state (never a
  silent discard; merged-PR-aware so the routine post-merge close isn't false-flagged), and
  refused from inside the target worktree. Removes worktrees, never remote branches.

## §7 Persisted artifacts (the compatibility contract)

The rewrite must not change the schema or semantics of any artifact below. **Falsifiable form:**
an artifact written by a v1 skill is consumed correctly by its v2 counterpart, and vice versa.

| Artifact | Where it lives |
|---|---|
| `<!-- implementation-plan:v1 -->` plan comment | issue comment |
| `<!-- issue-research:v1 -->` dossier comment | issue comment |
| `<!-- epic-delivery-log:v1 -->` delivery log | epic issue comment |
| `<!-- question-decision:v1 -->` recorded decision | question issue comment |
| `<!-- open-question-links:v1 -->` section + closed disposition set | build-issue body |
| Definition-of-done checkbox annotations (closed set) | issue body |
| `<!-- pr-evaluator-health-cache:v1 -->` health-cache comment | PR comment |
| `## Phase tracker` section (multi-phase issues) | PR body |
| `question`-issue body schema + `audience:*` labels | question issues |
| `## Handoff` schema + closed-set state markers | session output |
| Config marker blocks (`issue-resolver-*`, `pr-evaluator-*`, `drafter-open-question-markers`, `worktree-setup`/`-teardown`, `claude-code-stack-profile`) | consuming repo `CLAUDE.md`/`COMMANDS.md` |
| `epic/<N>-<slug>` integration-branch naming | consuming repo branches |

## §8 Grounding & workspace requirements

- **§8.1 `main` is write-protected.** No skill commits to a checkout other than its own
  session's workspace; the landing tools treat the checkout they were started in as read-only;
  every change reaches `main` through a PR.
- **§8.2 Everything lands via PR; landing is operator-gated.** All tracked-file changes a skill
  produces — code, docs, and configuration blocks — are made in a workspace on a branch, never
  in the root, and reach `main` only through a PR, gated per change or by a standing
  per-PR-type merge policy the operator configured (§5.5(f), default `ask`). The resolver opens
  its PR as part of its flow. The standalone tools that edit tracked files (`setup`,
  `question-sweep`, `doc-reviewer`) stage approved edits in the workspace and **offer** the
  landing (commit + push + PR) as one explicit final gate: on decline they perform no git
  actions, and the summary reports the workspace path and the ready-to-run landing commands.
- **§8.3 Workspaces.** A building or evaluating session runs **inside** the work worktree the
  operator opened (`workspace-open`) and starts the session in; its prep asserts that checkout
  before judgment runs and reports it as the session's workspace. Gate config is read at the
  `origin/main` pin via git plumbing — checkout-independent — and pinned-ref grounding views are
  script-internal.
- **§8.4 Pinned grounding.** Plans, audits, and evaluations ground on an explicitly recorded
  commit SHA, and their artifacts state it.
- **§8.5 Checkout state is respected.** A mismatched, stale, diverged, or root-seated session
  checkout is surfaced as a decision gate (`WORKSPACE_MISMATCH`); a dirty or off-`main` checkout
  on a workspace-creating path is likewise a gate (`ROOT_*`); neither is ever auto-corrected.

## §9 Engineering-quality requirements

- **§9.1 Deterministic/judgment split.** Any step whose inputs and correct output are fully
  defined (fetching, parsing, state derivation, ref selection, naming, command execution) is
  performed by scripts. Model reasoning is reserved for classification, drafting, planning,
  review, and verdicts. No intermediary agent relays between a skill and its scripts; skills
  invoke scripts directly.
- **§9.2 One-shot state assembly.** A session that needs starting state obtains all of it from
  a single script invocation; no session assembles state across multiple model-mediated calls.
- **§9.3 Offline testability.** The deterministic layer runs and is tested without network
  access or a live GitHub repo.
- **§9.4 Prompt economy.** A session loads only its router plus the one playbook it is
  executing; alternative playbooks stay on disk.
- **§9.5 Behavior parity.** A rewritten skill replaces its predecessor only after passing the
  parity protocol defined in [implementation.md](implementation.md).
- **§9.6 Portability.** The deterministic layer behaves identically on macOS (BSD userland) and
  Linux (GNU userland); no skill step depends on platform-specific tooling.

## §10 Success metrics

- Prompt text a pipeline session loads (router + the one playbook) is at most half of the v1
  `SKILL.md` line count for that skill (v1 baseline recorded by implementation step S1).
- Session startup performs at most one state-assembly invocation — exactly one for the pipeline
  stages (§9.2).
- The contract-token census (S1 baseline) shows zero unintended losses after each skill cutover.
- The offline suite exercises every script decision code and passes on both macOS and Linux.
- All nine skills pass the parity protocol before v1 removal.

## §11 Constraints & assumptions

- One operator per consuming repo at a time; concurrent sessions share only git/GitHub-enforced
  state.
- `gh` is installed and authenticated with repo scope; `git` and Python 3 are present (versions
  pinned in [architecture.md §1](architecture.md)). The skills require no other runtimes,
  interpreters, or packages.
- Consuming repos may lack optional capabilities (native issue dependencies, grounding docs,
  config blocks); skills degrade gracefully and say so.
- The plugin install directory is read-only at runtime; nothing is ever written there.
