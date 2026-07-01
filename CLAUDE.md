# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is a **Claude Code plugin** (`github-pipeline`), not an application. There is no compiled
code, no package manager, and no test framework. The "source" is:

- **Skill prompts** — `skills/<name>/SKILL.md` plus a `references/` folder of extracted prompt
  fragments per skill.
- **One sub-agent prompt** — `agents/github-ops.md`.
- **Five POSIX-ish bash scripts** — `scripts/*.sh`: three `gh-*` GitHub/git executors, plus
  `config-block.sh` (marker-block read/write) and `worktree-hooks.sh` (worktree setup/teardown).
- **Shared contracts** — `skills/_shared/*.md`.
- **Plugin manifests** — `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

Editing this repo means editing prompts and shell scripts. The README is an accurate
user-facing overview; this file is for someone *modifying the plugin*.

## Commands

There is no build/lint/test pipeline. Validation is manual:

```bash
# Validate the bundled scripts (shellcheck is the closest thing to a linter here)
shellcheck scripts/*.sh

# Validate the plugin manifests parse
jq . .claude-plugin/plugin.json .claude-plugin/marketplace.json

# Smoke-test a gather script directly (needs `gh` authed + a real issue/repo)
scripts/gh-gather.sh <issue> <owner/repo> "" /tmp/smoke

# Dry-run any persist op without writing to GitHub (--dry-run prints the gh command it WOULD run)
scripts/gh-persist.sh create <owner/repo> /path/to/body.md --title "..." --dry-run
```

Runtime dependencies (for the scripts and for the skills at use-time): `gh` (authenticated —
`gh auth status`), `jq`, `git`. The scripts are invoked by absolute path via
`${CLAUDE_PLUGIN_ROOT}/scripts/...` from the agent/skill bodies.

The real "tests" are the five skills run end-to-end against a live GitHub repo; there is no
offline harness.

## Architecture

### The pipeline is five session-per-step skills

```
draft ──▶ research ──▶ plan ──▶ resolve ──▶ evaluate
```

Each skill (`github-issue-drafter`, `github-issue-researcher`, `github-issue-planner`,
`github-issue-resolver`, `github-pr-evaluator`) runs in **its own Claude Code session**. The
only bridge between sessions is the `## Handoff` block each skill emits on a clean exit — a
cold-readable summary plus a copy-pasteable command to start the next session. There is no
shared runtime state. Re-routes (e.g. resolver → planner when the plan didn't survive contact
with the code) point the handoff at a *prior* skill but **do not** cross the session boundary by
calling the `Skill` tool — session-per-skill is the deliberate context-isolation choice, and the
handoff's `Why:` line is the load-bearing carrier of *why* the regression happened. See
`skills/_shared/handoff-format.md` — it is the single source of truth for the handoff schema, the
omission rules, and the **closed-set state-marker vocabulary** (don't invent synonyms for
`open`/`closed`, `APPROVE`/`COMMENT`, `squash`/`merge`, etc.). Per-skill renderings live in each
`SKILL.md`; the schema lives only in `_shared`.

Four skills sit **outside** the pipeline conveyor: `github-pipeline-setup` (writes the consuming
repo's config-block markers), `doc-reviewer` (guide-grounded review of a single doc), `open-questions`
(a project-wide sweep that reconciles the docs' open questions against the `question`-issue tracker —
the registry of record), and `question-resolver` (the assisted-closing path for one `question` issue —
evaluate it against the docs, record the operator's decision as a `<!-- question-decision:v1 -->`
comment, optionally close the issue, and *propose* the doc fold-back). These run standalone on explicit
invocation (`doc-reviewer`, `open-questions`, and `question-resolver` are `disable-model-invocation:
true`, report-then-apply/record), emit a plain summary rather than a pipeline `## Handoff`, and are not
stages in draft→…→evaluate. The `open-questions` sweep owns the open-question registry and
`question-resolver` closes its entries — the operator decides, the skill records; the drafter/planner
are thin consumers of the registry (see the shared contracts below).

### `github-ops` is the mechanical executor

`agents/github-ops.md` is a Sonnet sub-agent that all five skills delegate their **judgment-free
GitHub/git I/O** to (`subagent_type: "github-pipeline:github-ops"`, spawned with **no `model`
override**). The point is to keep the expensive Opus skills from spending context on `gh`/`git`
round-trips. It runs named operations (`GATHER_ISSUE`, `GATHER_PR`, `GATHER_EPIC`, `LIST_OPEN`,
`STATUS`, `PERSIST_CREATE`, `PERSIST_BODY`, `PERSIST_LINK`, `PERSIST_COMMENT`, `PERSIST_CLOSE`/`PERSIST_REOPEN`) and returns faithful structured
results. It never plans, classifies, drafts prose, makes merge decisions, or runs codebase
searches (those stay with the caller, which uses `Explore`/`Grep`/`Glob`). When blocked or
ambiguous it returns a `DECISION_NEEDED:` block and writes nothing — it cannot call
`AskUserQuestion`.

The caller's own **judgment** reading is itself delegated to isolated `Explore` sub-agents. The
resolver splits its context-heavy reading along a **read-type seam**: the **state-distiller**
(`skills/github-issue-resolver/references/state-distiller-prompt.md`, §P6) reasons over the issue's
thread + plan *text* and returns the current-state / effective-plan brief; the **fitness audit**
(`references/issue-audit-prompt.md`, §4.5) reasons over *code and docs* at a git ref and folds in
the plan-vs-code currency check (dimension 7). Both are context-blind and, like `github-ops`, cannot
call `AskUserQuestion` — they return the typed decision signal defined in
`skills/_shared/subagent-decision-signal.md` instead.

Two invariants in that agent are load-bearing and easy to break when editing:

- **Rule 7 — use the bundled scripts, never roll your own `gh`.** Every op with a script MUST go
  through it. Hand-rolled `gh issue view`/`mktemp + Write + gh ... --body-file` re-opens the
  empty-body race (the #626/#627 incident) and breaks the threshold routing below.
- **Rule 8 — byte-threshold spill routing (~25 KB).** Verbatim sections (issue/PR bodies,
  threads, marker comments, diffs) stay inline in the result when small and are written through to
  a scratch-dir file when large, so neither the agent nor the caller holds a 130 KB diff in
  context. The scripts apply this internally and surface a `*_mode: inline|path` per section;
  override via `GH_OPS_INLINE_THRESHOLD_BYTES`.

### The scripts encode the cross-skill contract

The three `gh-*` scripts are routed through `github-ops` (Rule 7); the worktree pair is routed
through the **calling skill's main loop** instead (the worktree lifecycle is cwd-stateful — see the
`github-ops` boundary above).

- `scripts/gh-gather.sh` — the fixed issue-fetch envelope (`GATHER_ISSUE`): one round-trip instead
  of three, with threshold routing. Also surfaces GitHub's **native issue dependencies**
  (`blocked_by` / `blocking` + a `deps_available` flag), capability-gated: on a gh/repo without the
  feature it returns empty lists + `deps_available: false` so callers degrade to prose linking.
- `scripts/gh-pr-gather.sh` — the PR-fetch envelope (`GATHER_PR`), with optional `--with-diff` /
  `--with-line-comments` (always spilled to disk).
- `scripts/gh-persist.sh` — the single write path (`create`/`edit-body`/`link`/`comment`/`close`/`reopen`).
  The `close`/`reopen` subcommands are bodyless issue-state changes (`gh issue close [--reason …]` /
  `gh issue reopen`) — no empty-body gate; `close` on an already-closed issue is a no-op (safe for a
  reentrant caller like `question-resolver`). Its leading
  `test -s <body_path>` is the **empty-body gate**: the caller stages the verbatim body to its own
  scratch dir and passes the path, so nothing re-serializes the body across the prompt boundary.
  An empty/missing file exits 2 with `EMPTY_BODY_FILE:` and forces a `DECISION_NEEDED`. Supports
  `--dry-run` and returns a `body_sha256` so callers can verify byte-for-byte. The `create`
  (`--blocked-by`/`--blocking`) and `link` (`--add/remove-blocked-by/blocking`, relationship-only,
  no body) paths set **native issue dependencies**, capability-gated by attempting the write and
  classifying failures: an unsupported gh **or** a repo without the feature drops the
  flag with a `DEPS_UNSUPPORTED:` notice rather than failing, and the caller's prose link is the
  fallback. Keep these `gh-*`
  scripts as the single execution path for all four caller skills — that is what makes the contract
  self-consistent. If a real op doesn't fit a script, extend the script; don't bypass it.
- `scripts/worktree-hooks.sh` — the worktree setup/teardown executor (`setup`/`teardown`
  subcommands), shared by the **resolver** (setup on every create/reuse) and the **evaluator**
  (teardown before removal, §14). It discovers the consuming repo's `<!-- worktree-setup -->` /
  `<!-- worktree-teardown -->` block (delegating the per-file block read to `config-block.sh`), runs
  the commands inside the worktree (setup fail-fast → exit 1; teardown best-effort → always exit 0),
  and returns a JSON result. It does **not** create or remove the worktree — those cwd-stateful git
  ops stay in the caller. The shared contract lives in `skills/_shared/worktree-lifecycle.md`; both
  skills cite it rather than restating the discover/parse/run loop inline.
- `scripts/config-block.sh` — deterministic marker-block `read`/`list`/`upsert`/`remove`, the single
  execution path for `github-pipeline-setup` and the block reader `worktree-hooks.sh` delegates to.

### Shared contracts in `skills/_shared/`

- `handoff-format.md` — the cross-session `## Handoff` schema, omission rules, Epic/Story variants,
  terminal endings, and re-route rules.
- `dod-annotations.md` — the closed set of `## Definition of done` checkbox annotation forms and
  the parser. Three skills share it: the **resolver** projects ticks as phases ship, the
  **evaluator** verifies and writes sticky-veto un-ticks, the **planner** reconciles during revise
  mode. Annotation form and checkbox state must always agree; a bullet never stacks two
  annotations.
- `worktree-lifecycle.md` — the worktree contract (path convention, reuse/nesting rules, the
  idempotent setup-on-every-entry guarantee, the `<!-- worktree-setup/teardown -->` block format,
  status-line strings, and the ownership split). The **resolver** creates worktrees and runs setup
  (§P1/§P2, never removes); the **evaluator** runs teardown and removes (§5.5.0, §14). Both cite
  this file and call `scripts/worktree-hooks.sh` rather than restating the mechanics inline.
- `subagent-decision-signal.md` — the closed-set typed-exception vocabulary an `Agent`-spawned
  judgment sub-agent returns to its caller's main loop in lieu of `AskUserQuestion` (which sub-agents
  can't call). Names each code (`THREAD_SUPERSEDED_PLAN`, `PHASES_MALFORMED`, `AMBIGUOUS`,
  `PLAN_MISSING`, `BLOCKED_ON_USER`) and the main-loop action it maps to. Produced by the
  resolver's **state-distiller** (§P6) and the `open-questions` skill's **question-status reader**
  (`AMBIGUOUS`); referenced by `asking-the-user.md`.
- `epic-delivery-log.md` — the `<!-- epic-delivery-log:v1 -->` comment contract: its format and the
  writer/reader ownership split. The **evaluator** is the sole writer (appends one entry per story at
  merge, §13); the **planner** reads it (Just-in-time story planning + Dimension 8's "consumes only
  what's shipped" check). It is a *separate* comment from the verified `<!-- implementation-plan:v1 -->`
  epic plan precisely because it changes on every merge while the plan stays immutable.
- `open-question-detection.md` — how to **find** an OQ in any project doc (the
  `<!-- drafter-open-question-markers -->` config-block hint + heuristic cues; OQs aren't centralized)
  and **match** it to a tracker issue (the de-dup search — search before filing, `Read` to confirm).
  Shared by the **`open-questions` sweep** (project-wide), the **drafter** (issue-scoped, thin), and
  the **planner** (grounding).
- `question-issue.md` — the `question`-issue body schema (`## Question` / `## Audience` /
  `## Constraints` / `## Context` / `## References` / `## Why this matters` / `## Tracked in`), the
  `audience:*` label rule, and the `## Tracked in` doc↔issue bridge. Shared by the **drafter** and the
  **`open-questions` sweep**, which file identical question issues; each keeps its own orchestration
  (review / gate / snippet / handoff).
- `open-question-links.md` — the `## Open questions` body section (marker `<!-- open-question-links:v1 -->`)
  a **build** issue carries when drafted from a source with unresolved open questions: its per-entry
  schema, the closed disposition set (`scoped-out` / `in-scope (blocked)` / `provisional-default`), the
  rule that `in-scope (blocked)` also sets a native `blocked by` dependency, and the **tiered status
  read** (an OQ's resolution comes from the *tracker* — Tier 1 issue `state` **or** a
  `<!-- question-decision:v1 -->` comment, Tier 2 the question-status reader — not a doc register
  field). The **registry of record is the set of `question` issues**; docs are sources. Ownership: the
  **`open-questions` sweep** owns the registry (detect across all docs, file/reconcile, maintain the
  doc↔issue back-links); the **`question-resolver`** closes a registry entry (records the operator's
  decision as the `<!-- question-decision:v1 -->` comment, optionally closes the issue, proposes the doc
  fold-back — never deciding or applying doc edits); the **drafter** is a thin writer (writes a build
  issue's entry + sets the native dep, never silently freezing an untracked OQ); the **planner**
  reads/extends it (into the plan's own `## Open questions`, never resolving an OQ); the **resolver** +
  **evaluator** read the native `blocked_by` and hard-gate the in-scope-blocked case, treating the
  section as a tracked-dependency registry, not buildable/DoD scope.

When changing behavior that touches handoffs, DoD annotations, the worktree lifecycle, the
sub-agent decision signal, the epic delivery log, or the open-question contracts (links / detection /
question-issue), edit the `_shared` file (the single source of truth) and keep the per-skill
renderings consistent with it.

### Coupling to a consuming repo is convention-driven

The skills are extracted from a real project and degrade gracefully when conventions are absent,
but key behaviors are driven by markers the *consuming* repo provides — not by config:

- **Marker comment blocks** in the consuming repo's `CLAUDE.md`/`COMMANDS.md` tell the resolver and
  evaluator how to test/gate: `<!-- issue-resolver-test-target -->`,
  `<!-- issue-resolver-fast-checks -->`, `<!-- issue-resolver-canonical-suite -->`,
  `<!-- pr-evaluator-health-checks -->`, `<!-- pr-evaluator-static-checks -->`,
  `<!-- pr-evaluator-test-target -->`, `<!-- pr-evaluator-escalation-labels -->`. The evaluator also
  reads `<!-- pr-evaluator-merge-policy -->` (per-PR-type `ask | auto`) to decide whether its merge
  step gates on a human operator — **default `ask`** when the block is absent. The **drafter** (and
  the planner, for in-scope provisional markers) reads `<!-- drafter-open-question-markers -->` to
  learn how this repo marks unresolved open questions (register location + inline-marker pattern +
  open-status rule); it **degrades gracefully** to built-in heuristic cues when the block is absent.
- **Epic integration branches** named `epic/<N>-<slug>` — the resolver/evaluator discover and
  classify Epic vs story PRs by this pattern.
- **Durable marker comments** the skills post/read: `<!-- implementation-plan:v1 -->` (planner),
  `<!-- issue-research:v1 -->` (researcher), `<!-- epic-delivery-log:v1 -->` (evaluator-written,
  planner-read), `<!-- question-decision:v1 -->` (the recorded decision on a `question` issue —
  `question-resolver`-written; read by the tiered status read's Tier 1, so the sweep/planner/drafter
  treat a marked question as resolved deterministically), and the `<!-- open-question-links:v1 -->`
  build-issue body section (drafter-written, planner/resolver/evaluator-read). For an **epic**, the planner's `<!-- implementation-plan:v1 -->` comment pins the
  cross-story contracts (`## Story contracts`) and sequencing up front and stays verified/immutable;
  per-story plans are authored **just-in-time** against current epic HEAD (planner "Just-in-time story
  planning"), not fanned out, so a later story never grounds on code a predecessor has since moved. What
  each story *actually* delivered is tracked separately in the `<!-- epic-delivery-log:v1 -->` comment —
  the evaluator appends to it on each story merge, and the planner reads it when planning the next story
  (kept out of the verified plan comment on purpose, since it changes on every merge).
- **Optional grounding docs** read if present: `docs/prd.md`, `docs/architecture.md`,
  `docs/constitution.md`, `CLAUDE.md`.
- **Setup-authored operating guidance** (distinct from the machine-parsed config blocks above):
  `github-pipeline-setup` proposes a `<!-- claude-code-stack-profile -->` block in the consuming
  repo's `CLAUDE.md` — concise, currency-checked guidance on running that stack efficiently in a
  Claude Code session (background slow commands, log verbose output instead of flooding context). No
  skill parses it; *every* session consumes it via the CLAUDE.md auto-load, which is why it lives in
  `CLAUDE.md`, not `COMMANDS.md`. Because nothing parses it, it is **user-owned**, not plugin-owned:
  setup seeds it when absent and re-ingests the user's edits as the base on re-run — proposing only
  currency refinements, never overwriting — unlike the machine-parsed blocks it reconciles to
  canonical. The resolver's §P3.4 defers to it rather than assuming non-Apple test output is compact.

## Editing conventions for this repo

- **`${CLAUDE_PLUGIN_ROOT}` substitution.** Skill/agent bodies reference bundled files as
  `${CLAUDE_PLUGIN_ROOT}/...`; Claude Code substitutes the real install path inline before the
  model reads it. That path changes on every plugin update and is **read-only** — never write
  state there (scratch dirs go under `/tmp/`). Where a path must reach a *raw-read* reference file
  or a *dispatched sub-agent prompt* (which are **not** substituted), the orchestrating skill
  resolves the path itself and passes it as an explicit placeholder — e.g. `<RESOLVER_DIR>` in the
  resolver's review-loop dispatch.
- **Plugin namespace is baked in.** Skills resolve as `/github-pipeline:<skill>` and the executor
  as `github-pipeline:github-ops`; cross-session handoff commands and `subagent_type` references
  are namespaced to match. Renaming the plugin means updating every such reference.
- **Model/effort are pinned per skill** in frontmatter (skills: `opus` at `medium`/`high`/`xhigh`;
  `github-ops`: `sonnet`/`medium`). The Sonnet pin on `github-ops` is intentional — it's the cheap
  executor — so don't add a `model` override when spawning it.
- **`github-ops` must stay judgment-free.** Don't push classification, triage, drafting, or
  codebase-locate searches into it; those belong to the calling skill.
- **A long `SKILL.md` exceeds the default Read cap.** The resolver/evaluator deliberately force a
  `Read` of certain `references/*.md` files mid-flow so the needed renderings are in context
  regardless of where the initial load truncated. Preserve those forced reads when refactoring.
- **Stable §-anchors over positional cross-references.** Skills navigate themselves and each other
  by stable anchors — workflow steps as `§N`/`step N`, and (resolver-only) reusable primitives as
  `§P-IDs` under the resolver's `## Procedures` band (`§P1`–`§P5`, cited as "per §P2" the way the
  flows cite "per §10.6"). Never reference a section by position ("the section above", "per X
  below") or by a hard line range (`§1015–1017`) — both silently dangle or invert the moment
  content is moved. When you add or move a reusable resolver primitive, give it a §P-ID and point
  every caller at the ID; when you reference another skill's section, name it (`§9 "DoD projection
  rule"`), don't cite its line number. There is no build/test, so a grep is the validator: the
  referenced set must be a subset of the defined set —
  `grep -oE '§P[0-9]+(\.[0-9]+)?' skills/github-issue-resolver/SKILL.md | sort -u` (referenced)
  vs `grep -nE '^#+ .*§P[0-9]' skills/github-issue-resolver/SKILL.md` (defined headings), and
  `grep -nE '\b(above|below)\b' skills/github-issue-resolver/SKILL.md` should surface only genuine
  prose, never a cross-reference. **The §P-ID scheme is resolver-local** — it exists because the
  resolver is the one file long and reorder-prone enough to need it; do not roll §P-IDs out to the
  other skills, which navigate fine by `§N` alone.
- **Skills stay tech-stack-agnostic; stack specifics live in the consuming repo, not the prompts.**
  The pipeline was extracted from a Swift/iOS project (`food-journal`) and is also run against other
  stacks (e.g. Ruby on Rails), so a prompt that *assumes* one stack is a bug, not a quirk. Stack
  specifics are meant to be carried out-of-band — the consuming repo's marker-comment config
  (`<!-- issue-resolver-test-target -->` etc.), the worktree setup/teardown hooks, and the **gated**
  `xcodebuild`→`apple-platform-build-tools:builder` delegation — so prompt bodies must not hard-code a
  language, framework, test runner, or file convention as *the* default. Three forms of tech-mention
  are allowed; one is banned:
  - **Banned — assumed default.** An instruction that only parses for one stack: "for each modified
    *Swift* file", "the wrapper supports `-only-testing FoodJournalTests`", "capture
    `app.debugDescription`". On the wrong repo these are wrong instructions the model will try to
    follow. Rewrite to the stack-neutral principle (the universal concept stated first, e.g.
    "high-fanout integration-surface file", "the wrapper's targeted-run syntax").
  - **Allowed — conditional integration** gated on a runtime signal that no-ops elsewhere ("if the
    command begins with `xcodebuild`, delegate to the Apple builder; otherwise run inline"). Keep
    these — it's how a stack-specific optimization stays agnostic.
  - **Allowed — labeled multi-stack example.** Name concrete stacks *as examples*, and show **≥2**
    (the convention here is Swift *and* Rails) so the schema reads as neutral; never present one
    stack's worked example as "the canonical shape." State the generic principle first, then
    illustrate. The `block-authoring.md` worked examples and the test-selection sub-agent's step-5
    SwiftUI/Rails branches are the reference patterns.
  - No build/test here, so a grep is the validator:
    `grep -rniE 'swift|xcode|xcb\.sh|foodjournal|rails|rspec|pytest' skills/ agents/` — every hit must
    be a gated integration or a labeled multi-stack example; a bare assumption is a regression.
- **Compressing a prompt without losing precision.** These skill/agent bodies are Opus instruction
  prompts (skills: `opus` at `medium`/`high`/`xhigh`; `github-ops`: `sonnet`), not chat prompts — so
  when reducing tokens the target is the *smallest set of high-signal tokens that fully specifies the
  behaviour*, **not the shortest text** (Anthropic's "minimal ≠ short"; corroborated by OpenAI and
  Google prompt guidance). This is load-bearing because Opus 4.8 follows instructions **literally** at
  these effort levels: it will not silently generalise a scope you trimmed or re-infer an intent you
  dropped, and there is no offline harness to catch the regression. Cut low-signal prose; keep every
  token that carries scope, intent, or contract.
  - **Compress — token wins with no precision cost:** delete filler and hedging ("in order to",
    "it's worth noting", restated context); de-duplicate against the point-of-use copy (an intro may
    lean on a fact restated at its `§N` *only when that copy is actually present*); use imperative
    action verbs ("Delegate", "Read from the path") over "you should consider…"; structure with
    Markdown headers / labelled blocks / lists; state what to do, not a list of what not to do.
  - **Do NOT — looks like compression, costs precision:**
    - **Word-for-symbol shorthand** — `w/`→"with", `&`→"and", `->`→"leads to" *in prose*. No vendor
      endorses it, the token saving is ~zero, and it reads ambiguously next to `gh` flags and code. (A
      flow arrow in a structured list — `Broad search → spawn Explore` — and `+` as a list-join —
      `PR + diff`, `Sonnet + medium` — are existing house style and fine; the ban is on substituting
      symbols for words in running prose.)
    - **Paraphrasing a contract token** — a synonym for a parsed identifier is a contract break, not a
      compression. Preserve verbatim: op names (`GATHER_ISSUE`, `PERSIST_COMMENT`, …), `subagent_type`
      strings (`github-pipeline:github-ops`), the `no model override` pin, marker comments
      (`<!-- … -->`), §-anchors / §P-IDs, scratch-dir/path conventions (`/tmp/gh-resolver-<N>/`), and
      the closed-set vocabularies in `skills/_shared/handoff-format.md` and `dod-annotations.md`
      (`open`/`closed`, `APPROVE`/`COMMENT`, `squash`/`merge`, the DoD annotation forms). Rule of
      thumb: if another skill or a script parses it, it's contract; the prose around it is compressible.
    - **Dropping the "why"** — a rationale clause (`#626/#627 race`, "cwd-stateful", "single source of
      truth") is high-signal: it's what stops a later editor reintroducing the bug. Compressing an
      explained invariant down to a bare command is the exact failure Anthropic warns against.
    - **Collapsing a scope qualifier** — "on every dispatch", "across GATHER calls", "first phase
      only", "before any code work begins" are the words Opus 4.8 won't re-infer.
  - **Phrasing:** prefer plain imperatives over `CRITICAL`/`MUST`/ALL-CAPS (these over-trigger on
    current models); reserve **bold** for genuinely load-bearing invariants, not default emphasis.
    Don't add a blanket "be concise" directive to a skill body — the models are already terse; put the
    concision where you want it.
  - No build/test here, so a grep is the validator: the contract-token set must not shrink across a
    compression pass —
    `grep -roE '<!-- [a-z0-9:-]+ -->|§P?[0-9]+(\.[0-9]+)?|GATHER_[A-Z]+|PERSIST_[A-Z]+|github-pipeline:[a-z-]+' skills/ agents/ | sort | uniq -c`
    before and after (no count drops unless you deliberately removed that op/anchor); and
    `grep -rnE '\bw/' skills/ agents/` should return nothing (banned shorthand).
  - The **`compress-skill-section`** skill (in `.claude/skills/`) automates this rule end-to-end: it
    drafts a denser version, runs an adversarial review→fix loop and a whole-document coherence check
    against these rules, runs the validators above, and proposes the result — it never edits the file.
