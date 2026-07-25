# Example — every config marker block (schema definitions)

> Artifact: config marker blocks — `issue-resolver-*`, `pr-evaluator-*`,
> `drafter-open-question-markers`, `worktree-setup`/`-teardown`, `claude-code-stack-profile`
> (prd.md §7, row 11).
> Source: `skills/github-pipeline-setup/references/block-authoring.md`, the canonical form given for
> each block in its own dedicated subsection. Every block below is a **schema/template definition**,
> quoted verbatim from its fence; the two `claude-code-stack-profile` worked examples (Rails,
> Node/TS) are genuine worked instances, captured because the file itself presents them as the
> canonical stack-specific fill-ins.

## `issue-resolver-fast-checks`

Source: `references/block-authoring.md:57-61`.

```markdown
<!-- issue-resolver-fast-checks -->
- `<command>` — <description>
<!-- /issue-resolver-fast-checks -->
```

## `issue-resolver-test-target`

Source: `references/block-authoring.md:69-78`.

```markdown
<!-- issue-resolver-test-target -->
- wrapper: `<test-runner command>`
- targets:
  - `<TargetName>` (unit | UI)
    - naming: <how source files map to suite identifiers>
    - helpers-fallback: <command, or "none">
    - broad-change-fallback: <command, or "none">
<!-- /issue-resolver-test-target -->
```

## `issue-resolver-canonical-suite`

Source: `references/block-authoring.md:93-99`. Read only by the resolver's
epic-baseline/bootstrap/post-rectification flow, never at a story gate.

```markdown
<!-- issue-resolver-canonical-suite -->
- full-suite: `<one-shot canonical command>`
- build-once: `<compile-the-test-bundle-once command>`
- retry-without-rebuild: `<re-run-without-recompile command>`
<!-- /issue-resolver-canonical-suite -->
```

## `pr-evaluator-static-checks`

Source: `references/block-authoring.md:112-116`. Same command-list shape as
`issue-resolver-fast-checks`; commands are repo-root-relative.

```markdown
<!-- pr-evaluator-static-checks -->
- `<command>` — <description>
<!-- /pr-evaluator-static-checks -->
```

## `pr-evaluator-test-target`

Source: `references/block-authoring.md:123-133`. Like `issue-resolver-test-target`, plus a
`full-suite-command` line returned when escalation rules fire.

```markdown
<!-- pr-evaluator-test-target -->
- wrapper: `<test-runner command>`
- full-suite-command: `<full canonical suite command>`
- targets:
  - `<TargetName>` (unit | UI)
    - naming: <how source files map to suite identifiers>
    - helpers-fallback: <command, or "none">
    - broad-change-fallback: <command, or "none">
<!-- /pr-evaluator-test-target -->
```

## `pr-evaluator-escalation-labels`

Source: `references/block-authoring.md:145-150`. Empty or absent means "no label-based
escalation" — a valid, normal choice.

```markdown
<!-- pr-evaluator-escalation-labels -->
- `full-suite-required` — bypass targeted selection
- `pre-release` — run everything before a release cut
<!-- /pr-evaluator-escalation-labels -->
```

## `pr-evaluator-merge-policy`

Source: `references/block-authoring.md:158-163`. Keys are exactly `standard` and `story`; values
`ask`|`auto`; default (absent block, or a type omitted from a present block) is `ask`;
`epic-integration` is not a valid key.

```markdown
<!-- pr-evaluator-merge-policy -->
- standard: ask
- story: ask
<!-- /pr-evaluator-merge-policy -->
```

## `worktree-setup` / `worktree-teardown`

Source: `references/block-authoring.md:192-200`. Optional — proposed as a pair only when the
project provisions a per-worktree resource. Parser constraint: each command must be a single
backtick-quoted span on one line with no embedded backtick, or `worktree-hooks.sh` silently drops
it.

```markdown
<!-- worktree-setup -->
- `<command>` — <description>
<!-- /worktree-setup -->

<!-- worktree-teardown -->
- `<command>` — <description>
<!-- /worktree-teardown -->
```

## `claude-code-stack-profile`

Source: `references/block-authoring.md:233-239` (the template). Free prose, no parser constraint —
model-read via the CLAUDE.md auto-load, not extracted by a script. Lives only in **CLAUDE.md** (or
a file it `@`-includes), regardless of where the pipeline config blocks live. User-owned: setup
seeds it when absent and re-ingests the existing interior as the base on re-run, proposing only
currency refinements — never wholesale-replaces user prose.

```markdown
<!-- claude-code-stack-profile -->
## Running this stack with Claude Code

<concise operating guidance — see scope and constraints below>
<!-- /claude-code-stack-profile -->
```

### Worked example — Rails

Source: `references/block-authoring.md:273-283`.

```markdown
<!-- claude-code-stack-profile -->
## Running this stack with Claude Code

- Unit/integration tests are terse — run them inline and targeted: `bin/rails test test/models/book_test.rb` (append `:LINE` for one test).
- System tests and the full suite (`bin/rails test:system`, or `bin/rails test:all` for everything) are slow and noisy (headless browser, server logs, screenshots under `tmp/screenshots/`). Background them, log the output, read only the summary: `bin/rails test:system 2>&1 | tee tmp/test.log`, then `grep -E 'runs|failures|errors|Failure|Error' tmp/test.log`.
- Re-run only what failed; keep iterating on the named test rather than the whole suite.
- Tests parallelize above ~50 examples, one test DB per worker (auto-created, suffixed by worker number) — don't assume a single shared DB; pair with `worktree-setup` when isolating per worktree.
- One-time slow setup (`bundle install`, `bin/rails db:prepare`, `assets:precompile`) — run backgrounded and wait, don't poll the output.
<!-- /claude-code-stack-profile -->
```

### Worked example — Node / TS

Source: `references/block-authoring.md:287-296`.

```markdown
<!-- claude-code-stack-profile -->
## Running this stack with Claude Code

- Unit tests are fast — run targeted: `npm test -- path/to/foo.test.ts`.
- The full suite, e2e runs, and coverage are slow/noisy — background and log: `npm run test:e2e > /tmp/e2e.log 2>&1`, then read the tail / `grep` failures. Prefer the reporter's terse mode (`--reporter=dot`) over the verbose default.
- Re-run only failures (`vitest --changed`, `jest --onlyFailures`) instead of the full run.
- One-time slow steps (`npm ci`, a cold production build) — background and wait.
<!-- /claude-code-stack-profile -->
```

## `github-pipeline-config` (file header — not machine-parsed by any pipeline skill, but
plugin-owned and reconciled to canonical)

Source: `skills/github-pipeline-setup/references/block-authoring.md:313-316`. Lives only in
`COMMANDS.md`, never atop a human-facing `CLAUDE.md`.

```markdown
<!-- github-pipeline-config -->
Pipeline configuration for the `github-pipeline` skills (resolver / evaluator / planner), read at use-time. You can edit these blocks by hand — just keep each block's `<!-- … -->` marker pair intact so the skills can find it. Re-run `github-pipeline-setup` to reconcile them (idempotent).
<!-- /github-pipeline-config -->
```

## `drafter-open-question-markers` (not authored by `setup` — read by the drafter/planner; the
canonical example lives in `_shared/open-question-detection.md`, not `block-authoring.md`)

This marker is a genuine outlier among the eleven: it is **not** one of the blocks `setup` writes
(the setup skill's own S1 spec confirms all eleven of *its* blocks above; this one is authored by
the consuming repo's operator directly, since it describes *their own* register conventions, not
something `setup` can detect or draft). It is included in this file because it is named in the same
prd.md §7 row as the ten setup-authored blocks. There is no fixed schema fence for it in the v1
source — `skills/_shared/open-question-detection.md:16-28` describes its **contents** (register
location(s), inline-marker pattern, open-status rule) as free-form prose the drafter/planner parse
heuristically, not a byte-exact template. No verbatim fenced block exists to quote for this one.
