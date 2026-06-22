# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is a **Claude Code plugin** (`github-pipeline`), not an application. There is no compiled
code, no package manager, and no test framework. The "source" is:

- **Skill prompts** — `skills/<name>/SKILL.md` plus a `references/` folder of extracted prompt
  fragments per skill.
- **One sub-agent prompt** — `agents/github-ops.md`.
- **Three POSIX-ish bash scripts** — `scripts/gh-*.sh`.
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

### `github-ops` is the mechanical executor

`agents/github-ops.md` is a Sonnet sub-agent that all five skills delegate their **judgment-free
GitHub/git I/O** to (`subagent_type: "github-pipeline:github-ops"`, spawned with **no `model`
override**). The point is to keep the expensive Opus skills from spending context on `gh`/`git`
round-trips. It runs named operations (`GATHER_ISSUE`, `GATHER_PR`, `GATHER_EPIC`, `LIST_OPEN`,
`STATUS`, `PERSIST_CREATE`, `PERSIST_BODY`, `PERSIST_COMMENT`) and returns faithful structured
results. It never plans, classifies, drafts prose, makes merge decisions, or runs codebase
searches (those stay with the caller, which uses `Explore`/`Grep`/`Glob`). When blocked or
ambiguous it returns a `DECISION_NEEDED:` block and writes nothing — it cannot call
`AskUserQuestion`.

Two invariants in that agent are load-bearing and easy to break when editing:

- **Rule 7 — use the bundled scripts, never roll your own `gh`.** Every op with a script MUST go
  through it. Hand-rolled `gh issue view`/`mktemp + Write + gh ... --body-file` re-opens the
  empty-body race (the #626/#627 incident) and breaks the threshold routing below.
- **Rule 8 — byte-threshold spill routing (~25 KB).** Verbatim sections (issue/PR bodies,
  threads, marker comments, diffs) stay inline in the result when small and are written through to
  a scratch-dir file when large, so neither the agent nor the caller holds a 130 KB diff in
  context. The scripts apply this internally and surface a `*_mode: inline|path` per section;
  override via `GH_OPS_INLINE_THRESHOLD_BYTES`.

### The three scripts encode the cross-skill contract

- `scripts/gh-gather.sh` — the fixed issue-fetch envelope (`GATHER_ISSUE`): one round-trip instead
  of three, with threshold routing.
- `scripts/gh-pr-gather.sh` — the PR-fetch envelope (`GATHER_PR`), with optional `--with-diff` /
  `--with-line-comments` (always spilled to disk).
- `scripts/gh-persist.sh` — the single write path (`create`/`edit-body`/`comment`). Its leading
  `test -s <body_path>` is the **empty-body gate**: the caller stages the verbatim body to its own
  scratch dir and passes the path, so nothing re-serializes the body across the prompt boundary.
  An empty/missing file exits 2 with `EMPTY_BODY_FILE:` and forces a `DECISION_NEEDED`. Supports
  `--dry-run` and returns a `body_sha256` so callers can verify byte-for-byte. Keep these scripts
  as the single execution path for all four caller skills — that is what makes the contract
  self-consistent. If a real op doesn't fit a script, extend the script; don't bypass it.

### Shared contracts in `skills/_shared/`

- `handoff-format.md` — the cross-session `## Handoff` schema, omission rules, Epic/Story variants,
  terminal endings, and re-route rules.
- `dod-annotations.md` — the closed set of `## Definition of done` checkbox annotation forms and
  the parser. Three skills share it: the **resolver** projects ticks as phases ship, the
  **evaluator** verifies and writes sticky-veto un-ticks, the **planner** reconciles during revise
  mode. Annotation form and checkbox state must always agree; a bullet never stacks two
  annotations.

When changing behavior that touches handoffs or DoD annotations, edit the `_shared` file (the
single source of truth) and keep the per-skill renderings consistent with it.

### Coupling to a consuming repo is convention-driven

The skills are extracted from a real project and degrade gracefully when conventions are absent,
but key behaviors are driven by markers the *consuming* repo provides — not by config:

- **Marker comment blocks** in the consuming repo's `CLAUDE.md`/`COMMANDS.md` tell the resolver and
  evaluator how to test/gate: `<!-- issue-resolver-test-target -->`,
  `<!-- issue-resolver-fast-checks -->`, `<!-- issue-resolver-canonical-suite -->`,
  `<!-- pr-evaluator-health-checks -->`, `<!-- pr-evaluator-static-checks -->`,
  `<!-- pr-evaluator-test-target -->`, `<!-- pr-evaluator-escalation-labels -->`.
- **Epic integration branches** named `epic/<N>-<slug>` — the resolver/evaluator discover and
  classify Epic vs story PRs by this pattern.
- **Durable marker comments** the skills post/read: `<!-- implementation-plan:v1 -->` (planner),
  `<!-- issue-research:v1 -->` (researcher).
- **Optional grounding docs** read if present: `docs/prd.md`, `docs/architecture.md`,
  `docs/constitution.md`, `CLAUDE.md`.

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
