# github-pipeline

A Claude Code plugin that runs a complete GitHub issue/PR workflow through the `gh` CLI — five
session-per-stage skills that hand off to one another, plus four standalone maintenance tools,
backed by stdlib-only Python scripts that do every deterministic step (fetching, parsing, state
derivation, worktree lifecycle, and every write).

```
draft ──▶ research ──▶ plan ──▶ resolve ──▶ evaluate
 (file)    (cite)      (design)  (code+PR)   (review+merge)
```

Each stage runs in its own Claude Code session and ends with a copy-pasteable `## Handoff` block
that starts the next one, so context stays clean across the pipeline.

## The pipeline

| Skill | What it does |
|---|---|
| `/github-pipeline:drafter` | Turns informal feedback into a well-structured issue (or Epic + stories) and files it. Never silently absorbs an unresolved open question — each is matched against the `question`-issue registry, filed if untracked, and recorded on the build issue. |
| `/github-pipeline:researcher` | Web-researches version/API/migration questions and posts a dated, cited dossier on the issue — or declines outright when the issue carries no currency risk. |
| `/github-pipeline:planner` | Designs the implementation approach, grounded in repo precedent + project docs at a recorded commit SHA, and posts a reviewed `<!-- implementation-plan:v1 -->` comment. Epic plans pin cross-story contracts; story plans are authored just-in-time. |
| `/github-pipeline:resolver` | Implements one issue against its verified plan in a git worktree, opens/continues a PR, projects Definition-of-done ticks as phases ship, and loops with code review until approved. |
| `/github-pipeline:evaluator` | Evaluates a PR against its origin issue, gates on branch health (CI plus your declared checks, cached per head SHA), posts a formal approve/soft-reject review, merges per your configured policy, and cleans up the worktree. |

## The standalone tools

| Skill | What it does |
|---|---|
| `/github-pipeline:setup` | **Run this first.** Detects your project's lint/test/build commands and writes the marker blocks the resolver/evaluator read from `COMMANDS.md`/`CLAUDE.md`, plus a stack operating-profile for `CLAUDE.md`. Idempotent — safe to re-run; migrates legacy blocks. |
| `/github-pipeline:question-sweep` | Reconciles the project's open questions between its docs and the GitHub `question`-issue tracker (the registry of record): files the untracked ones, flags docs left stale by an answered question, and repairs the doc↔issue back-links. Reports first, applies on confirmation. |
| `/github-pipeline:question-resolver` | Assisted closing of one open `question` issue: evaluates it and its thread against the project docs, records your approved decision as a durable `<!-- question-decision:v1 -->` comment, offers to close the issue, and **proposes** the doc fold-back. It never decides for you and never edits docs. |
| `/github-pipeline:doc-reviewer` | Reviews one project doc against its bundled authoring guide and offers to apply the findings you accept. |

The tools are report-then-apply and end with a plain summary, not a handoff. The three that edit
tracked files (`setup`, `question-sweep`, `doc-reviewer`) stage their edits in a worktree and offer
the landing (commit + push + PR) as one final gate — decline it and nothing is committed, with the
workspace path and ready-to-run commands printed instead.

`skills/_shared/` holds the cross-skill contracts (handoff schema, Definition-of-done annotations,
the open-question contracts, the worktree hook-block format); `scripts/` holds the Python scripts
the skills invoke — the `gh`/git executors, `workspace.py`, `parse.py`, and one `prep_*.py`
state-assembly script per skill.

## Requirements

- [`gh`](https://cli.github.com), authenticated (`gh auth status`).
- `git` and `python3` (≥ 3.9) on `PATH`. The scripts are **stdlib-only** — nothing to install, no
  virtualenv, no lockfile.

## Install

```
/plugin marketplace add danwashusen/claude-github-pipeline
/plugin install github-pipeline@reactive-tools
```

Then invoke any skill by its namespaced name, e.g. `/github-pipeline:drafter`, or just describe the
task ("file an issue for…", "plan #142", "resolve #287") and Claude will pick the skill. The four
standalone tools except `setup` are explicit-invocation only.

## Conventions a consuming repo should provide

These skills are **convention-driven** rather than fully parameterised. They degrade gracefully
when a convention is absent, but work best when the repo provides:

- **A write-protected `main`.** Everything the pipeline changes lands through a PR; the project
  root checkout is treated as read-only and stays on `main`. All work happens in worktrees under
  `.worktrees/`.
- **Epic integration branches** named `epic/<N>-<slug>` (the resolver creates them; resolver and
  evaluator classify Epic and story PRs by this pattern).
- **Test / build / static-check commands** declared in `CLAUDE.md` or `COMMANDS.md` inside these
  marker blocks, which the resolver and evaluator read to learn how to test and gate your project:
  - `<!-- issue-resolver-test-target -->`, `<!-- issue-resolver-fast-checks -->`,
    `<!-- issue-resolver-canonical-suite -->`
  - `<!-- pr-evaluator-static-checks -->`, `<!-- pr-evaluator-test-target -->`,
    `<!-- pr-evaluator-escalation-labels -->`, `<!-- pr-evaluator-merge-policy -->` (per-PR-type
    `ask | auto`; default `ask`) — plus the legacy `<!-- pr-evaluator-health-checks -->`, which
    setup offers to split and migrate.

  You don't have to write these by hand — run **`/github-pipeline:setup`** and it detects your
  project's commands, proposes drafts, and writes the blocks idempotently.
- **Worktree hooks** (optional) — `<!-- worktree-setup -->` / `<!-- worktree-teardown -->` blocks
  declaring the commands that provision and release per-worktree resources (a simulator, a port, a
  scratch database). Setup runs on every worktree entry, so the commands must be idempotent.
- **An open-question marker convention** (optional) — `<!-- drafter-open-question-markers -->`
  tells the drafter and planner how this repo marks unresolved open questions; without it they fall
  back to built-in heuristic cues.
- **A stack operating-profile** (optional, setup-authored) — setup proposes a
  `<!-- claude-code-stack-profile -->` block in `CLAUDE.md`: concise guidance on running your stack
  efficiently in a Claude Code session (backgrounding slow commands, logging verbose output instead
  of flooding context), auto-loaded into every session. It's yours to edit — re-running setup
  re-ingests your edits rather than overwriting them.
- **Optional grounding docs** read if present: `docs/prd.md`, `docs/architecture.md`,
  `docs/constitution.md`, and `CLAUDE.md`. The planner and resolver use them to align designs and
  audit implementations; missing docs are simply skipped.

The skills post and read durable marker comments: `<!-- implementation-plan:v1 -->` (planner),
`<!-- issue-research:v1 -->` (researcher), `<!-- epic-delivery-log:v1 -->` (evaluator-written,
planner-read), `<!-- pr-evaluator-health-cache:v1 -->` (evaluator), `<!-- question-decision:v1 -->`
(question-resolver), and the `<!-- open-question-links:v1 -->` build-issue body section (drafter).

## Notes for maintainers

- **Path resolution.** Bundled scripts and reference files are referenced from skill bodies as
  `${CLAUDE_PLUGIN_ROOT}/…`, which Claude Code substitutes inline to the real install path before
  the model reads it. The path changes on every plugin update and is read-only — never write state
  there (session scratch goes to `/tmp/gh-<skill>-<N>/`). Where a path must reach a *raw-read*
  reference file or a dispatched sub-agent prompt (which are not substituted), the orchestrating
  skill resolves it and passes it as an explicit placeholder.
- **Plugin namespace.** Skills resolve as `/github-pipeline:<skill>`; the cross-session handoff
  commands are namespaced to match. If you rename the plugin, update those references.
- **Tests.** `python3 tests/run.py` runs the offline suite (stdlib `unittest`, a fixture-replaying
  `gh` shim, a temp-repo git sandbox — no network, no live repo). It must pass on macOS and Linux;
  see `tests/README.md`. `CLAUDE.md` documents the prompt-side validators.

## License

MIT
