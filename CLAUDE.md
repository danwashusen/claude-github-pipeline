# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is a **Claude Code plugin** (`github-pipeline`), not an application. There is no compiled
artifact and no package manager. The "source" is:

- **Skill prompts** — `skills/<name>/SKILL.md` (a thin router) plus `playbooks/` (one file per
  behaviorally distinct flow, read on demand) and `references/` (judgment sub-agent prompts +
  contract renderings).
- **Stdlib-only Python scripts** — `scripts/*.py`: the four GitHub/git executors (`gh_gather.py`,
  `gh_pr_gather.py`, `gh_persist.py`, `config_block.py`), `workspace.py` (worktree lifecycle),
  `parse.py` (DoD / open-question-links / phases), the eight `prep_*.py` state-assembly scripts,
  the `oq_tracker.py` helper the open-question preps compose, and `scripts/pipelib/` (envelope,
  spill, decision codes, hashing, the locked-down subprocess runner, the hook runner).
- **An offline test harness** — `tests/` (stdlib `unittest`, a fixture-replaying `gh` shim, a git
  sandbox); `python3 tests/run.py` is the one command.
- **Shared contracts** — `skills/_shared/*.md`.
- **Plugin manifests** — `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
- **The design docs** — `docs/prd.md` (what/why), `docs/architecture.md` (how; §12 is the
  non-deviable invariant registry), `docs/implementation.md` (the v1→v2 migration), and
  `docs/specs/` (the frozen v1 behavior specs + the parity records).

Editing this repo means editing prompts and Python. The README is the user-facing overview; this
file is for someone *modifying the plugin*.

Runtime dependencies: `python3` (≥ 3.9, **stdlib only** — no third-party packages, no venv, no pip
step), `git` (≥ 2.38), and `gh` (≥ 2.40, authenticated — `gh auth status`). Nothing else. Scripts
are executables (`#!/usr/bin/env python3`) invoked by absolute path via
`${CLAUDE_PLUGIN_ROOT}/scripts/...`.

## Commands

There is no build step. Validation is the offline suite plus a set of prompt-side greps
(prose has no compiler — the greps are the compiler):

```bash
python3 -m compileall -q scripts/                       # every script parses
python3 tests/run.py                                    # the whole offline suite; must exit 0
python3 -m json.tool .claude-plugin/plugin.json         # manifests parse
python3 -m json.tool .claude-plugin/marketplace.json

# One skill's gates, or one script's behavior, without the full suite:
python3 -m unittest tests.test_resolver_routing tests.test_v1_retirement
```

The suite must pass on **both macOS and Linux** (architecture.md §9.6); the container invocation is
documented in `tests/README.md`. Live behavior is exercised by the parity scenarios in
`docs/specs/parity/<skill>.md` against the sandbox repo recorded in `tests/SANDBOX.md` — never by
an offline test, which is hermetic (no network, no live repo).

The prompt-side validators are listed under "Validators" at the end of this file. Run them after
any prompt edit; they are cheap and they are the only regression net prose has.

## Architecture

### Nine skills: five pipeline stages, four standalone tools

```
draft ──▶ research ──▶ plan ──▶ resolve ──▶ evaluate
```

The **pipeline stages** are `drafter`, `researcher`, `planner`, `resolver`, `evaluator`; the
**standalone tools** are `setup`, `question-sweep`, `question-resolver`, `doc-reviewer`
([prd.md §2](docs/prd.md)).

**That is the conceptual order, not the handoff topology:** the drafter forwards to the
**planner**, and `research` is a conditional detour off `plan` — the planner re-routes to the
researcher only when the issue has no dossier and the plan turns on external truth with genuine
currency risk, and the researcher hands **back to the planner**, which ingests the dossier (a
declined research run hands back too, with `research: ✗`). The planner also re-routes **backward to
the drafter** when its seam gate finds a standard issue epic-shaped (most seams outside the issue's
DoD): it aborts with a lean seam-analysis comment and the drafter promotes #N into an Epic in place
(`skills/planner/references/seam-dispositions.md`). v1 behaved identically — the S15 parity
record's Scenario 4(b) has v1's drafter `Next:` pointing at its own planner — so this is doc truth
being corrected, not a behavior change. The stage/tool split is load-bearing, not cosmetic:

- A pipeline stage runs in **its own Claude Code session** and ends with a `## Handoff` — a
  cold-readable summary plus the copy-pasteable command that starts the next session. There is no
  shared runtime state; the handoff and the GitHub artifacts are the only bridge. Re-routes (e.g.
  resolver → planner when the plan didn't survive contact with the code) point the handoff at a
  *prior* stage but **never** cross the session boundary by calling the `Skill` tool —
  session-per-skill is the deliberate context-isolation choice, and the handoff's `Why:` line is
  the load-bearing carrier of *why* the regression happened.
- A standalone tool runs only on explicit invocation, is report-then-apply (nothing changes without
  the operator seeing the proposal), and ends with a **plain summary**, not a handoff. Tools that
  edit tracked files (`setup`, `question-sweep`, `doc-reviewer`) stage edits in a workspace and
  **offer** the landing (commit + push + PR) as one final gate; on decline they perform zero git
  actions and print the workspace path plus the ready-to-run commands ([prd.md §8.2](docs/prd.md)).
- The split also scopes the [prd.md §10](docs/prd.md) prompt-economy metric: "router + the one
  playbook ≤ half the v1 `SKILL.md` line count" is a **pipeline-stage** bar. The standalone tools
  are measured and recorded, never force-trimmed — the leanest v1 tools had no fat to cut and v2
  added the §8.2 landing gate, so a tool legitimately exceeds half (the S19 doc-reviewer ruling:
  record the metric, never trim a tool to hit it).

`skills/_shared/handoff-format.md` is the single source of truth for the handoff schema, the
omission rules, and the **closed-set state-marker vocabulary** (don't invent synonyms for
`open`/`closed`, `APPROVE`/`COMMENT`, `squash`/`merge`). Per-skill renderings live in each skill's
`references/handoff-renderings.md`; the schema lives only in `_shared`.

### One session = router + prep + one playbook

Every `SKILL.md` is a router with the same four sections, in order
([architecture.md §9](docs/architecture.md)):

1. **Prep** — the one prep-script invocation, plus the universal `needs_decision` rule (or an
   explicit no-prep note where a skill genuinely has nothing to gather — currently only
   `doc-reviewer`, where the operator names the doc).
2. **Route** — the visible `vector → playbooks/<file>` table and the override rule.
3. **Invariants** — the rules that hold for every route (single workspace, staged-body writes,
   gates only for genuine decisions, faithful reporting, handoff on clean exit).
4. **Handoff** (pipeline) or **Summary** (standalone tools).

The governing rule is **facts by script, meaning by model**. A step whose inputs and correct output
are fully defined — fetching, parsing, state derivation, ref selection, branch naming, hook
execution, writing — is a script. The model classifies, drafts, plans, reviews, and judges. If a
needed operation has no script, **extend a script**; never inline the operation in a prompt. There
is no intermediary agent between a skill and its scripts (v1's mechanical executor sub-agent, which
lived under `agents/`, was retired at S20 — its eight rules landed on the scripts and the router,
per [architecture.md §7](docs/architecture.md)'s mapping table).

- **The facts block.** `prep_<skill>.py` assembles the session's entire starting state in **one
  call** and emits it as the envelope payload ([prd.md §9.2](docs/prd.md)): repo, scratch dir, root
  SHA, target, the state `vector`, `suggested_playbook`, workspaces, pinned config, parsed DoD,
  native `blocked_by`, `attention`, `notices`. Preps compose the executor cores **in-process**
  (module imports, not a subprocess chain). Values the flow needs are **facts**, so playbooks
  consume them as data instead of re-deriving them.
- **The envelope** ([architecture.md §3](docs/architecture.md)). Every script emits exactly one
  JSON envelope on stdout. `status` is `ok` or `needs_decision`; `needs_decision` is a *valid
  outcome*, not an error — the router's single universal rule is to render `decision` as one
  `AskUserQuestion` card and act on the answer. Exit `0` = envelope present, `2` = usage error, any
  other non-zero = hard failure (stderr carries it, no envelope). The **closed decision-code set**
  lives in §3 and spans scripts *and* judgment sub-agents (it supersedes v1's
  `subagent-decision-signal.md`); adding a code is a contract change — amend §3 and the router rule
  together. Non-blocking degradations ride in `notices` (e.g. `DEPS_UNSUPPORTED` when native issue
  dependencies are unavailable and prose links are the fallback).
- **Spill routing** (~25 KB). Any verbatim section (body, thread, marker comment, diff) is inline
  when small and written to the session scratch dir when large; each reports `*_bytes` +
  `*_mode: inline|path` (+ `*_path`). Diffs and line-comment sets are always `path`. Threshold:
  `GH_PIPELINE_INLINE_THRESHOLD_BYTES` (legacy `GH_OPS_INLINE_THRESHOLD_BYTES` still honored).
  This is what keeps a 130 KB diff out of the session's context.
- **Judgment sub-agents** ([architecture.md §8](docs/architecture.md)) isolate reasoning that would
  otherwise pollute the main loop: the resolver's state-distiller (thread + plan *text*) and
  fitness audit (*code and docs* at a pinned ref), the planner's plan reviewer, the drafter's issue
  reviewer, the researcher's dossier validator, the test-selection and review-loop sub-agents, and
  the question-status reader. All are context-blind, receive **workspace paths and prep-staged
  files** (never refs), cannot call `AskUserQuestion` (they return a §3 decision code instead), and
  never write to GitHub.

### The scripts encode the cross-skill contract

- `gh_gather.py` — the fixed issue-fetch envelope: body + full thread + labels + marker-comment
  lookup in one round-trip, with spill routing. Surfaces GitHub's **native issue dependencies**
  (`blocked_by` / `blocking` + a `deps_available` flag), capability-gated: on a `gh`/repo without
  the feature it returns empty lists + `deps_available: false` so callers degrade to prose linking.
- `gh_pr_gather.py` — the PR-fetch envelope, with optional `--with-diff` / `--with-line-comments`
  (always spilled to disk) and the PR's own `labels`.
- `gh_persist.py` — the single write path (`create` / `edit-body` / `edit-labels` / `link` /
  `comment` / `close` / `reopen` / `create-pr` / `close-pr`). Its leading size check is the
  **empty-body gate**: the caller stages the verbatim body to its scratch dir and passes the
  *path*, so nothing re-serializes a body across the prompt boundary; an empty or missing file is
  an `EMPTY_BODY_FILE` decision **before** any `gh` write (the #626/#627 empty-body race). Returns
  `body_bytes` + `body_sha256` and verifies the round-trip itself. `close` on a closed issue is a
  no-op (safe for a reentrant caller like `question-resolver`); marker replacement posts the new
  comment **before** deleting the old (a crash must not lose the marker); native-dependency writes
  are capability-gated with a `DEPS_UNSUPPORTED` notice and a prose-link fallback.
- `config_block.py` — deterministic marker-block `read`/`list`/`upsert`/`remove`; the single
  execution path for `setup`, and the block reader `workspace.py` composes in-process.
- `workspace.py` — the workspace lifecycle owner: `ensure --work|--read`, `remove --work`, `gc`,
  `root-status`, `lint`. It runs the consuming repo's `<!-- worktree-setup/teardown -->` commands
  (setup fail-fast on every ensure, teardown best-effort before removal), enforces root freshness
  (`ROOT_NOT_ON_MAIN` / `ROOT_DIRTY` / `ROOT_DIVERGED` are decisions, never auto-fixes), handles
  branch exclusivity (`BRANCH_IN_USE`), and maintains the `.worktrees/` exclusion in the repo's
  `info/exclude` — **never** a `.gitignore` edit, because `info/exclude` lives outside the working
  tree and so can never surface in `git status` or trip root-freshness on its own write.
- `parse.py` — `dod` / `oq-links` / `phases`: the three contract parsers, each with a malformed
  decision code (`DOD_MALFORMED`, `PHASES_MALFORMED`).

Every executor exposes a **pure, non-emitting core** — `build_*(...) -> (payload, notices,
decision | None)` — with `main()` as a thin emit wrapper. A prep calls those cores directly and
emits exactly one envelope of its own; **no `redirect_stdout` capture** of another script's stdout
(the S8 pattern lock — `docs/specs/baseline.md` §5.1).

### Workspaces and the trust topology

Two tiers ([prd.md §8](docs/prd.md), [architecture.md §6](docs/architecture.md)): the **project
root** is the read-only vantage, always clean `main`; **`.worktrees/`** holds every mutable and
pinned-ref checkout. `main` changes only via PR. A `work` workspace is `.worktrees/<branch>`
(branch checkout, setup hooks on every ensure, torn down and removed by the evaluator after merge);
a `read` workspace is `.worktrees/ro-<ref-slug>` (detached HEAD at `origin/<ref>`, reset on every
ensure, `gc`'d by age — and only `ro-*` is ever gc'd).

The prompt-visible rule is: **your workspace is `facts.workspace.path`**. Every Read / Grep /
Explore / test / command names it by absolute path. When a flow needs a second view, prep hands out
a named read workspace — prompts never select refs, never do ref arithmetic, and never depend on
ambient cwd. Gate config (test target, checks, merge policy, OQ markers) is read by prep **at the
recorded root `main` SHA** and embedded in the facts, so a PR can never weaken the gates that judge
it; the drafter is the one root-only skill and reads its OQ-marker hint from the ambient checkout,
where that threat model cannot apply.

### Shared contracts in `skills/_shared/`

- `handoff-format.md` — the cross-session `## Handoff` schema, omission rules, Epic/Story variants,
  terminal endings, re-route rules, and the closed-set state-marker vocabulary.
- `dod-annotations.md` — the closed set of `## Definition of done` checkbox annotation forms and
  the parser. Three skills share it: the **resolver** projects ticks as phases ship, the
  **evaluator** verifies and writes sticky-veto un-ticks, the **planner** reconciles during revise
  mode. Annotation form and checkbox state must always agree; a bullet never stacks two
  annotations.
- `worktree-lifecycle.md` — the **external** `<!-- worktree-setup -->` / `<!-- worktree-teardown -->`
  block format a consuming repo declares, and what those commands must guarantee (setup idempotent
  because it runs on *every* ensure; teardown best-effort and before removal). The *mechanics*
  belong to `workspace.py` and architecture §6 — this file does not restate them.
- `epic-delivery-log.md` — the `<!-- epic-delivery-log:v1 -->` comment contract and its
  writer/reader split. The **evaluator** is the sole writer (one entry per story at merge); the
  **planner** reads it (just-in-time story planning + the "consumes only what's shipped" check). It
  is a *separate* comment from the verified `<!-- implementation-plan:v1 -->` epic plan precisely
  because it changes on every merge while the plan stays immutable.
- `open-question-detection.md` — how to **find** an open question in any project doc (the
  `<!-- drafter-open-question-markers -->` config-block hint + heuristic cues; OQs aren't
  centralized) and **match** it to a tracker issue (search before filing, `Read` to confirm).
  Shared by **`question-sweep`** (project-wide), the **drafter** (issue-scoped, thin), and the
  **planner** (grounding).
- `question-issue.md` — the `question`-issue body schema (`## Question` / `## Audience` /
  `## Constraints` / `## Context` / `## References` / `## Why this matters` / `## Tracked in`), the
  `audience:*` label rule, and the `## Tracked in` doc↔issue bridge. Shared by the **drafter** and
  **`question-sweep`**, which file identical question issues; each keeps its own orchestration.
- `open-question-links.md` — the `## Open questions` body section (marker
  `<!-- open-question-links:v1 -->`) a **build** issue carries when drafted from a source with
  unresolved open questions: the per-entry schema, the closed disposition set (`scoped-out` /
  `in-scope (blocked)` / `provisional-default`), the rule that `in-scope (blocked)` also sets a
  native `blocked by` dependency, and the **tiered status read** (an OQ's resolution comes from the
  *tracker* — Tier 1 issue `state` **or** a `<!-- question-decision:v1 -->` comment, Tier 2 the
  question-status reader — never a doc register field). **The registry of record is the set of
  `question` issues**; docs are sources. `question-sweep` owns the registry; `question-resolver`
  closes an entry (records the operator's decision, optionally closes the issue, *proposes* the doc
  fold-back — never deciding, never applying doc edits); the drafter is a thin writer; the planner
  reads and extends it, never resolving an OQ; the resolver and evaluator read the native
  `blocked_by` and hard-gate the in-scope-blocked case, treating the section as a
  tracked-dependency registry, not buildable scope or DoD.
- `follow-up-filing.md` — the drafter-proxy sub-agent protocol the resolver, the evaluator, and the
  planner (seam-disposition follow-ups) use to file a follow-up issue (never a hand-crafted
  `gh issue create` body).
- `asking-the-user.md` — the `AskUserQuestion` card shape, and the rule that a sub-agent returns a
  §3 decision code instead of asking.

When changing behavior that touches handoffs, DoD annotations, the worktree block format, the epic
delivery log, or the open-question contracts, edit the `_shared` file (the single source of truth)
and keep the per-skill renderings consistent with it — **render, don't restate**.

### Coupling to a consuming repo is convention-driven

The skills degrade gracefully when conventions are absent, but key behaviors are driven by markers
the *consuming* repo provides — not by plugin config:

- **Marker comment blocks** in the consuming repo's `CLAUDE.md`/`COMMANDS.md` tell the resolver and
  evaluator how to test and gate: `<!-- issue-resolver-test-target -->`,
  `<!-- issue-resolver-fast-checks -->`, `<!-- issue-resolver-canonical-suite -->`,
  `<!-- pr-evaluator-health-checks -->` (legacy, split on migration),
  `<!-- pr-evaluator-static-checks -->`, `<!-- pr-evaluator-test-target -->`,
  `<!-- pr-evaluator-escalation-labels -->`. The evaluator also reads
  `<!-- pr-evaluator-merge-policy -->` (per-PR-type `ask | auto`) to decide whether its merge step
  gates on the operator — **default `ask`** when the block is absent. The **drafter** (and the
  planner, for in-scope provisional markers) reads `<!-- drafter-open-question-markers -->` to
  learn how this repo marks unresolved open questions; it **degrades gracefully** to built-in
  heuristic cues when the block is absent.
- **Worktree hooks** — `<!-- worktree-setup -->` / `<!-- worktree-teardown -->`, run by
  `workspace.py` inside the workspace.
- **Epic integration branches** named `epic/<N>-<slug>` — the resolver creates them; the
  resolver/evaluator classify Epic vs story PRs by this pattern.
- **Durable marker comments** the skills post and read: `<!-- implementation-plan:v1 -->`
  (planner), `<!-- issue-research:v1 -->` (researcher), `<!-- epic-delivery-log:v1 -->`
  (evaluator-written, planner-read), `<!-- pr-evaluator-health-cache:v1 -->` (evaluator, keyed on
  head SHA), `<!-- question-decision:v1 -->` (question-resolver-written; the tiered status read's
  Tier 1, so a marked question reads as resolved deterministically), and the
  `<!-- open-question-links:v1 -->` build-issue body section (drafter-written;
  planner/resolver/evaluator-read). For an **epic**, the planner's plan comment pins the
  cross-story contracts (`## Story contracts`) and sequencing up front and stays verified and
  immutable; per-story plans are authored **just-in-time** against current epic HEAD, not fanned
  out, so a later story never grounds on code a predecessor has since moved.
- **Optional grounding docs** read if present: `docs/prd.md`, `docs/architecture.md`,
  `docs/constitution.md`, `CLAUDE.md`.
- **Setup-authored operating guidance** (distinct from the machine-parsed blocks above): `setup`
  proposes a `<!-- claude-code-stack-profile -->` block in the consuming repo's `CLAUDE.md` —
  concise, currency-checked guidance on running that stack efficiently in a Claude Code session
  (background slow commands, log verbose output instead of flooding context). No skill parses it;
  *every* session consumes it via the CLAUDE.md auto-load, which is why it lives in `CLAUDE.md`,
  not `COMMANDS.md`. Because nothing parses it, it is **user-owned**: setup seeds it when absent and
  re-ingests the user's edits as the base on re-run, proposing only currency refinements — unlike
  the machine-parsed blocks, which it reconciles to canonical.

## Editing conventions for this repo

- **`${CLAUDE_PLUGIN_ROOT}` substitution.** Skill bodies reference bundled files as
  `${CLAUDE_PLUGIN_ROOT}/...`; Claude Code substitutes the real install path inline before the
  model reads it. That path changes on every plugin update and is **read-only** — never write state
  there. Scratch dirs are uniformly `/tmp/gh-<skill>-<N>/`, and prep reports the one in use as
  `facts.scratch`. Where a path must reach a *raw-read* reference file or a *dispatched sub-agent
  prompt* (which are **not** substituted), the orchestrating skill resolves the path itself and
  passes it as an explicit placeholder.
- **Plugin namespace is baked in.** Skills resolve as `/github-pipeline:<skill>`; cross-session
  handoff commands are namespaced to match. Renaming the plugin means updating every such
  reference.
- **Model/effort are not pinned.** Skill frontmatter carries no `model:` or `effort:` keys — every
  skill inherits the invoking session's model and effort level. The v1 per-skill pins were removed
  2026-08-01; reintroducing one is a deviation through the normal gate.
- **`disable-model-invocation: true` is exactly the three-tool trio** — `doc-reviewer`,
  `question-sweep`, `question-resolver`. **`setup` is the deliberate exception**: it is a
  standalone tool but stays model-invocable, because v1 never carried the key on it and the S17
  parity run adjudicated the difference rather than "fixing" it (`docs/specs/parity/setup.md`,
  "ADJUDICATION RECORD"). Don't add the key to `setup` on the assumption that all four tools match.
- **v2 was written from scratch; v1 lives in git history.** A skill's router + playbooks were
  authored against its `docs/specs/<skill>.md` spec, the PRD, and architecture §9 — never by
  editing v1 prose down. The v1 tree was removed at S20; the last commit carrying the seven
  renamed v1 skill directories, the `agents/` executor prompt, and the five `scripts/*.sh` is
  `d29ec1b`.
  Two skills kept their v1 *name*, so their v1 file is only visible at the commit before their own
  retire-rebuild: **`f9f1623`** (v1 `question-resolver`) and **`7bffb90`** (v1 `doc-reviewer`).
  Cite those SHAs when you need the v1 behavior; the frozen behavioral record is `docs/specs/`.
- **Frozen artifact provenance strings.** A handful of persisted artifacts still carry a footer
  naming the *v1* skill that authored them (the plan comment, the research dossier, the health
  cache, the review comment, and the `<!-- github-pipeline-config -->` header body's "re-run setup"
  line). Those are **byte-compatibility contract tokens** a cross-consuming v1 reader matches
  verbatim ([prd.md §7](docs/prd.md); the S7 adjudication in `docs/specs/baseline.md` §5.3) —
  **not** skill names awaiting a rename, and the v2 rename deliberately did not propagate into the
  artifact bytes. `tests/support/retired_tokens.py` is the one file allowed to spell a retired v1
  name: it holds the literals and the exemption table (file + exact fragment). Every *other* v1
  name under `skills/`, `scripts/`, `tests/`, `README.md`, `.claude-plugin/`, or this file is a
  stale reference and fails `tests/test_v1_retirement.py` — which is why the paragraphs here name
  the retired surfaces descriptively instead of quoting them.
- **Stable §-anchors over positional cross-references.** Skills navigate themselves and each other
  by stable anchors — workflow steps as `§N`/`step N`. Never reference a section by position ("the
  section above", "per X below") or by a hard line range: both silently dangle or invert the moment
  content moves. When you reference another skill's section, name it (`§9 "DoD projection rule"`),
  don't cite its line number. **The resolver-local `§P-ID` scheme is retired** — it existed because
  the v1 resolver was one 1169-line file; the v2 router + playbook split removed the need, and
  nothing under `skills/` or `scripts/` defines a `§P` of its own. Outside `docs/specs/**` (the
  frozen v1 record, which keeps its `§P` rows) the only occurrences are this rule, the validators
  that forbid it, and script comments citing one of those frozen spec rows. Reintroducing a live
  `§P` is a regression the per-skill grep gates catch.
- **Routers stay thin, playbooks stay linear.** A router fits in one default `Read` (≤ ~150 lines),
  so the v1 forced-mid-flow-`Read` workaround is retired too. One route per session: the router
  selects exactly one playbook, which may pull in its skill's single shared spine file — nothing
  else, never a second playbook. **Parameterize before you playbook**: a branch that differs only
  in *values* (base ref, branch name, merge strategy, cleanup list) is not a branch — the values
  are facts. A playbook exists only for flows that differ in *actions taken*, and carries no
  `if epic … else if story …` interleaving.
- **Skills stay tech-stack-agnostic; stack specifics live in the consuming repo, not the prompts.**
  The pipeline was extracted from a Swift/iOS project and is also run against other stacks (e.g.
  Ruby on Rails), so a prompt that *assumes* one stack is a bug, not a quirk. Stack specifics are
  carried out-of-band — the consuming repo's marker-comment config, the worktree hooks, and the
  **gated** `xcodebuild`→`apple-platform-build-tools:builder` delegation. Three forms of
  tech-mention are allowed; one is banned:
  - **Banned — assumed default.** An instruction that only parses for one stack: "for each modified
    *Swift* file", "the wrapper supports `-only-testing FoodJournalTests`", "capture
    `app.debugDescription`". On the wrong repo these are wrong instructions the model will try to
    follow. Rewrite to the stack-neutral principle (the universal concept first, e.g. "high-fanout
    integration-surface file", "the wrapper's targeted-run syntax").
  - **Allowed — conditional integration** gated on a runtime signal that no-ops elsewhere ("if the
    command begins with `xcodebuild`, delegate to the Apple builder; otherwise run inline"). Keep
    these — it's how a stack-specific optimization stays agnostic.
  - **Allowed — labeled multi-stack example.** Name concrete stacks *as examples*, and show **≥2**
    (the convention here is Swift *and* Rails) so the schema reads as neutral; never present one
    stack's worked example as "the canonical shape". State the generic principle first, then
    illustrate. `skills/setup/references/block-authoring.md`'s worked examples and the
    test-selection sub-agent's SwiftUI/Rails branches are the reference patterns.
- **Compressing a prompt without losing precision.** These skill bodies are agent instruction
  prompts run at whatever model/effort the invoking session uses (typically a frontier model at
  medium-or-higher effort), not chat prompts — so when reducing tokens the
  target is the *smallest set of high-signal tokens that fully specifies the behaviour*, **not the
  shortest text** (Anthropic's "minimal ≠ short"; corroborated by OpenAI and Google prompt
  guidance). This is load-bearing because these models follow instructions **literally** at these
  effort levels: they will not silently generalise a scope you trimmed or re-infer an intent you
  dropped, and no offline test reads prose. Cut low-signal prose; keep every token that carries scope,
  intent, or contract.
  - **Compress — token wins with no precision cost:** delete filler and hedging ("in order to",
    "it's worth noting", restated context); de-duplicate against the point-of-use copy (an intro
    may lean on a fact restated at its `§N` *only when that copy is actually present*); use
    imperative action verbs ("Delegate", "Read from the path") over "you should consider…";
    structure with Markdown headers / labelled blocks / lists; state what to do, not a list of what
    not to do.
  - **Do NOT — looks like compression, costs precision:**
    - **Word-for-symbol shorthand** — `w/`→"with", `&`→"and", `->`→"leads to" *in prose*. No vendor
      endorses it, the token saving is ~zero, and it reads ambiguously next to `gh` flags and code.
      (A flow arrow in a structured list — `Broad search → spawn Explore` — and `+` as a list-join
      — `PR + diff` — are existing house style and fine; the ban is on substituting symbols for
      words in running prose.)
    - **Paraphrasing a contract token** — a synonym for a parsed identifier is a contract break,
      not a compression. Preserve verbatim: marker comments (`<!-- … -->`), §3 decision codes
      (`EMPTY_BODY_FILE`, `ROOT_DIRTY`, `AMBIGUOUS`, …), facts-block key names the playbooks read,
      script names and subcommands, `/github-pipeline:<skill>` invocation strings, scratch-dir
      conventions (`/tmp/gh-resolver-<N>/`), §-anchors, and the closed-set vocabularies in
      `skills/_shared/handoff-format.md` and `dod-annotations.md` (`open`/`closed`,
      `APPROVE`/`COMMENT`, `squash`/`merge`, the DoD annotation forms). Rule of thumb: if another
      skill, a script, or a GitHub consumer parses it, it's contract; the prose around it is
      compressible.
    - **Dropping the "why"** — a rationale clause (`#626/#627 race`, "a PR must not weaken its own
      gates", "single source of truth") is high-signal: it's what stops a later editor
      reintroducing the bug. Compressing an explained invariant down to a bare command is the exact
      failure Anthropic warns against.
    - **Collapsing a scope qualifier** — "on every ensure", "first phase only", "before any code
      work begins", "at the recorded root SHA" are the words Opus won't re-infer.
  - **Phrasing:** prefer plain imperatives over `CRITICAL`/`MUST`/ALL-CAPS (these over-trigger on
    current models); reserve **bold** for genuinely load-bearing invariants, not default emphasis.
    Don't add a blanket "be concise" directive to a skill body — the models are already terse; put
    the concision where you want it.
  - The **`compress-skill-section`** skill (in `.claude/skills/`) automates this rule end-to-end: it
    drafts a denser version, runs an adversarial review→fix loop and a whole-document coherence
    check against these rules, runs the validators below, and proposes the result — it never edits
    the file.

## Validators

Prose has no compiler, so these greps are it. Run them after any prompt edit; `docs/specs/**` and
`docs/implementation.md` are exempt from all of them as the historical record.

```bash
# 1. Contract-token census — the set must not shrink across an edit (S1 baseline + the S20 v2-only
#    re-baseline are in docs/specs/baseline.md §2 and §6).
grep -roE '<!-- [a-z0-9:-]+ -->|§P?[0-9]+(\.[0-9]+)?|GATHER_[A-Z]+|PERSIST_[A-Z]+|github-pipeline:[a-z-]+' \
  skills/ | sort | uniq -c

# 2. Retired v1 names — zero hits across skills/ scripts/ tests/ README.md .claude-plugin/
#    CLAUDE.md, outside the exemption table. The literals and the exemptions live in
#    tests/support/retired_tokens.py; this file is itself inside the scanned set, so run the scan
#    in its committed form rather than retyping the grep here.
python3 -m unittest tests.test_v1_retirement

# 3. Ref arithmetic in prompts — zero `git show <ref>:<path>` / `git grep <ref>` under skills/.
#    A bare `git show <commit>` single-commit diff view is permitted; only <ref>:<path> extraction
#    and `git grep <ref>` are banned (architecture.md §10; S7 adjudication (c)).
grep -rnE 'git +show +[^ ]+:|git +grep +[^-]' skills/

# 4. Raw `gh` writes / fetch-envelopes in prompts — every op that HAS a bundled script must go
#    through it (architecture.md §7 rule 7). Three sanctioned scriptless executors are the only
#    exceptions, all spec'd: `gh pr merge` (evaluator, merge execution), `gh pr ready --undo`
#    (evaluator, the soft-reject draft flip), `gh pr ready <N>` (resolver, the last-phase
#    draft→ready flip, without which the evaluator's draft guard deadlocks). Label creation
#    (`gh label create`) is likewise scriptless by design and stays inline.
grep -rnE 'gh +(issue|pr) +(create|edit|comment|review|close|reopen)|gh +api[^\n]*DELETE' skills/

# 5. Stack assumptions — every hit must be a gated integration or a labeled ≥2-stack example.
grep -rniE 'swift|xcode|xcb\.sh|foodjournal|rails|rspec|pytest' skills/

# 6. Banned shorthand — must return nothing.
grep -rnE '\bw/' skills/

# 7. Executable bit on every dispatched script (a 0644 script exits 126 at
#    ${CLAUDE_PLUGIN_ROOT} dispatch time, with no traceback).
python3 -m unittest tests.test_script_modes
```

Greps 3 and 4 are approximations run over the whole file; the committed per-skill tests
(`tests/test_<skill>_routing.py`) apply the same rules **fence-scoped**, so prose that *describes* a
banned form doesn't false-positive while a real command in a code fence does. When the grep and the
test disagree, the test is the contract.
