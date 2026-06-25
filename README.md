# github-pipeline

A Claude Code plugin that runs a complete GitHub issue/PR workflow through the `gh` CLI — five
session-per-step skills that hand off to one another, plus a one-shot setup skill that configures a
repo to use them, backed by a mechanical `github-ops` executor sub-agent and four bundled shell
scripts.

```
draft ──▶ research ──▶ plan ──▶ resolve ──▶ evaluate
 (file)    (cite)      (design)  (code+PR)   (review+merge)
```

Each skill runs in its own Claude Code session and ends with a copy-pasteable `## Handoff` block
that starts the next one, so context stays clean across the pipeline.

## Components

| Component | What it does |
|---|---|
| `/github-pipeline:github-pipeline-setup` | **Run this first.** Detects your project's lint/test/build commands and writes the marker blocks the resolver/evaluator read from `COMMANDS.md`/`CLAUDE.md`, plus a concise stack operating-profile for `CLAUDE.md` (how to run your stack efficiently in a Claude Code session). Idempotent — safe to re-run to re-configure; migrates legacy blocks. Not a pipeline stage. |
| `/github-pipeline:github-issue-drafter` | Turns informal feedback into a well-structured issue (or Epic + stories) and files it. |
| `/github-pipeline:github-issue-researcher` | Web-researches version/API/migration questions and posts a dated, cited dossier on the issue. |
| `/github-pipeline:github-issue-planner` | Designs the implementation approach, grounded in repo precedent + project docs, and posts a verified `<!-- implementation-plan:v1 -->` comment. |
| `/github-pipeline:github-issue-resolver` | Implements the issue end-to-end, opens/continues a PR, and loops with `review` until approved. Understands Epics and stories. |
| `/github-pipeline:github-pr-evaluator` | Evaluates a PR against its origin issue, posts a formal approval/soft-reject review, and recommends a merge strategy. |
| `github-pipeline:github-ops` (agent) | Internal executor. The skills delegate all mechanical `gh`/`git` fetch + persist I/O to it (runs on Sonnet) so the expensive model isn't spent on round-trips. Not for direct use. |

The `_shared/` skill folder holds the cross-skill handoff schema and Definition-of-Done annotation
contract; `scripts/` holds the bundled `gh-gather.sh`, `gh-pr-gather.sh`, `gh-persist.sh`, and
`config-block.sh` (the deterministic, idempotent reader/writer for the marker blocks above).

## Requirements

- The [`gh`](https://cli.github.com) CLI, authenticated (`gh auth status`).
- `jq` and `git` on `PATH`.
- The bundled scripts are POSIX `sh`; the agent invokes them by absolute path via `${CLAUDE_PLUGIN_ROOT}`.

## Install

```
/plugin marketplace add danwashusen/claude-github-pipeline
/plugin install github-pipeline@reactive-tools
```

Then invoke any skill by its namespaced name, e.g. `/github-pipeline:github-issue-drafter`, or just
describe the task ("file an issue for…", "plan #142", "resolve #287") and Claude will pick the skill.

## Conventions a consuming repo should provide

These skills were extracted from a real project and are **convention-driven** rather than fully
parameterised. They degrade gracefully when a convention is absent, but work best when the repo
provides:

- **Epic integration branches** named `epic/<N>-<slug>` (the resolver/evaluator discover and classify
  Epic and story PRs by this pattern).
- **Test / build / static-check commands** declared in `CLAUDE.md` or `COMMANDS.md` inside these
  marker blocks, which the resolver and evaluator read to learn how to test and gate your project:
  - `<!-- issue-resolver-test-target -->`, `<!-- issue-resolver-fast-checks -->`,
    `<!-- issue-resolver-canonical-suite -->`
  - `<!-- pr-evaluator-static-checks -->`, `<!-- pr-evaluator-test-target -->`,
    `<!-- pr-evaluator-escalation-labels -->` (and the legacy `<!-- pr-evaluator-health-checks -->`)

  You don't have to write these by hand — run **`/github-pipeline:github-pipeline-setup`** and it
  detects your project's commands, proposes drafts, and writes the blocks idempotently (and offers to
  migrate the legacy `health-checks` block).
- **A stack operating-profile** (optional, setup-authored) — setup also proposes a
  `<!-- claude-code-stack-profile -->` block in `CLAUDE.md`: concise guidance on running your stack
  efficiently in a Claude Code session (backgrounding slow commands, logging verbose output instead
  of flooding context), auto-loaded into every session.
- **Optional grounding docs** read if present: `docs/prd.md`, `docs/architecture.md`,
  `docs/constitution.md`, and `CLAUDE.md`. The planner and resolver use them to align designs and
  audit implementations; missing docs are simply skipped.

The skills post and read durable marker comments: `<!-- implementation-plan:v1 -->` (planner) and
`<!-- issue-research:v1 -->` (researcher).

## Notes for maintainers

- **Path resolution.** Bundled scripts and reference files are referenced from skill/agent bodies as
  `${CLAUDE_PLUGIN_ROOT}/…`, which Claude Code substitutes inline to the real install path before the
  model reads it. The path changes on every plugin update and is read-only — never write state there.
  Where a path must reach a *raw-read* reference file or a dispatched sub-agent (which are not
  substituted), the orchestrating skill resolves it and passes it as an explicit placeholder
  (e.g. `<RESOLVER_DIR>` in the resolver's review loop).
- **Plugin namespace.** Skills resolve as `/github-pipeline:<skill>` and the executor as
  `github-pipeline:github-ops`; the cross-session handoff commands are namespaced to match. If you
  rename the plugin, update those references.

## License

MIT
