# Block authoring reference

The authoring spec for every block `github-pipeline-setup` writes: exact shape, what belongs
in each, how to infer the contents from the repo, and how to migrate the legacy single-block
declaration. Read this before drafting anything in §3 of the skill.

The source of truth for *how each block is consumed* lives in the skills that read them —
`github-issue-resolver` §P3.1 / §P2 and `github-pr-evaluator` "Repo health-check declaration".
This file mirrors those formats for the *authoring* side; if they ever disagree, the consuming
skill wins. The one exception is `claude-code-stack-profile`, which no skill reads — it is
model-consumed via the CLAUDE.md auto-load, so it has no consuming-skill source of truth.

## Contents

- [Two shared shapes](#two-shared-shapes)
- [The blocks](#the-blocks)
  - [issue-resolver-fast-checks](#issue-resolver-fast-checks)
  - [issue-resolver-test-target](#issue-resolver-test-target)
  - [issue-resolver-canonical-suite](#issue-resolver-canonical-suite)
  - [pr-evaluator-static-checks](#pr-evaluator-static-checks)
  - [pr-evaluator-test-target](#pr-evaluator-test-target)
  - [pr-evaluator-escalation-labels](#pr-evaluator-escalation-labels)
  - [pr-evaluator-merge-policy](#pr-evaluator-merge-policy)
  - [worktree-setup / worktree-teardown](#worktree-setup--worktree-teardown)
  - [claude-code-stack-profile](#claude-code-stack-profile)
- [Detection heuristics](#detection-heuristics)
- [Legacy migration: health-checks → static-checks + test-target](#legacy-migration)
- [Two worked examples — Swift and Rails](#worked-examples)

## Two shared shapes

Every block is one of two shapes:

**Command-list** (`*-fast-checks`, `*-static-checks`, `worktree-*`) — one Markdown list entry per
command: a backtick-quoted command, then ` — `, then a short human description. **Order matters** —
commands run in declaration order, and the static lists are *fail-fast* (the first non-zero exit
stops the run), so put the cheapest/fastest commands first.

```markdown
- `<command>` — <description>
- `<command>` — <description>
```

**Prose config** (`*-test-target`) — structured Markdown the consuming skill reads as natural
language (it is *not* parsed). Don't compress it into a one-liner; the per-target indentation and
labels are what make it legible to the test-selection sub-agent.

## The blocks

### issue-resolver-fast-checks

Fail-fast **static** commands the resolver runs at its §7 baseline and before every push (§8/§10.6):
codegen, dependency resolution, lints, layer-import boundary checks. **No test invocations belong
here** — tests are the test-target block's job. Keep it to things that finish in seconds.

```markdown
<!-- issue-resolver-fast-checks -->
- `<command>` — <description>
<!-- /issue-resolver-fast-checks -->
```

### issue-resolver-test-target

Configuration for the resolver's test-selection sub-agent at the story gates (targeted selection
only). Declares the test `wrapper` and, per target, how source files map to suite identifiers and
what to fall back to when a change can't be mapped to one suite.

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

- **wrapper** — the test runner the project invokes (`./scripts/xcb.sh`, `bin/rails test`, `pytest`, `go test`, …).
- **naming** — the convention mapping a changed source file to the suite(s) that cover it. Project
  knowledge; interview the user rather than inventing it.
- **helpers-fallback** — what to run when a changed file is a shared helper that doesn't map to one
  suite (run the whole target, or `none`).
- **broad-change-fallback** — what to run when a change is too broad to scope (run the whole target,
  or `none`).

### issue-resolver-canonical-suite

The **full** suite, read only by the resolver's epic-baseline / bootstrap / post-rectification flow —
never at a story gate. Three labelled commands so re-runs don't cold-rebuild:

```markdown
<!-- issue-resolver-canonical-suite -->
- full-suite: `<one-shot canonical command>`
- build-once: `<compile-the-test-bundle-once command>`
- retry-without-rebuild: `<re-run-without-recompile command>`
<!-- /issue-resolver-canonical-suite -->
```

If the project's runner can't separate compile from run (most non-Apple stacks), set all three to the
same command and note it — the labels still satisfy the reader, you just lose the no-rebuild re-run
optimisation. Skip this block on projects that have no "epic" flow; the resolver falls back to
`pr-evaluator-test-target`'s `full-suite-command` when it's absent.

### pr-evaluator-static-checks

The evaluator's equivalent of `issue-resolver-fast-checks` — fail-fast always-run hygiene, run first
at every gate. Same command-list shape and the same "no test invocations here" rule. Commands use
repo-root-relative paths (the evaluator `cd`s into the branch worktree first).

```markdown
<!-- pr-evaluator-static-checks -->
- `<command>` — <description>
<!-- /pr-evaluator-static-checks -->
```

### pr-evaluator-test-target

Like `issue-resolver-test-target`, plus a **`full-suite-command`** — the command returned when
escalation rules fire (epic-integration PR, or an escalation label matched).

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

The resolver and evaluator test-target blocks usually share the same `wrapper`, target names, and
naming conventions — draft them together and keep them consistent. The only structural difference is
this block's `full-suite-command` line.

### pr-evaluator-escalation-labels

GitHub PR labels that force the full suite instead of targeted selection. **An empty or absent block
means "no label-based escalation"** — which is a perfectly normal choice. If the user wants no
escalation labels, write the block empty (it documents the decision) or skip it.

```markdown
<!-- pr-evaluator-escalation-labels -->
- `full-suite-required` — bypass targeted selection
- `pre-release` — run everything before a release cut
<!-- /pr-evaluator-escalation-labels -->
```

### pr-evaluator-merge-policy

Governs whether the evaluator's merge step (its §12) runs hands-free or routes through the §12.0
**operator decision gate** (a human approves/rejects the merge). One list item per PR type,
`<pr-type>: <ask | auto>` — a small key/value list, not the command-list or prose-config shape:

```markdown
<!-- pr-evaluator-merge-policy -->
- standard: ask
- story: ask
<!-- /pr-evaluator-merge-policy -->
```

- **Keys** are `standard` and `story`. **Values** are `ask` (gate before merge — the operator must
  Approve / Needs Revision / Reject) or `auto` (merge directly on a clean automated approval).
- **Default is `ask`.** The evaluator treats an absent block — or a PR type omitted from a present
  block — as `ask`, so a repo gets human-in-the-loop merges with no configuration at all. `auto` is
  strictly opt-in, per PR type.
- **`epic-integration` is not configurable** and isn't a valid key here — epic integration PRs land
  every child story's diff on `main` at once and are *always* gated. The evaluator ignores an
  `epic-integration:` line if one appears.
- **Not detected — it's a preference, not a repo fact.** There's nothing in the repo to infer this
  from; ask the user which PR types they want to approve by hand. Propose `ask` for both (the safe
  default) and let them opt specific types into `auto`.
- **Stack-independent.** Unlike every other block here, this one's content never varies by language,
  framework, or test runner — there's no per-stack variant. The one shape above *is* the whole
  schema, which is why the worked examples below don't repeat it.

### worktree-setup / worktree-teardown

**Optional**, and most repos don't need them — skip unless the project provisions a per-worktree
resource the test commands depend on (an isolated iOS Simulator on a Swift project, a free localhost
port or scratch DB on a Rails one, a branch-keyed cache). Command-list shape. Setup runs after a
worktree is created/entered and is *fail-fast*; teardown runs before a worktree is removed and is
*best-effort*. Both must be **idempotent** — setup may re-run on a reused worktree, teardown may run
on a half-provisioned or already-cleaned one. The full runtime contract (discovery, idempotency
rationale, status lines, the `worktree-hooks.sh` executor the resolver/evaluator run) lives in
[`../../_shared/worktree-lifecycle.md`](../../_shared/worktree-lifecycle.md) — this section only
covers the authoring shape.

```markdown
<!-- worktree-setup -->
- `<command>` — <description>
<!-- /worktree-setup -->

<!-- worktree-teardown -->
- `<command>` — <description>
<!-- /worktree-teardown -->
```

**Authored by research-and-propose, not detection** (setup §3): no heuristic infers per-worktree
provisioning, so setup researches the best-practice approach for the detected stack and proposes the
commands for confirmation. Propose the two blocks **as a pair** — setup that allocates a resource must
ship with the teardown that releases it — and prefer commands that are idempotent by construction
(guard-then-create / create-if-absent), per the idempotency contract above.

**Parser constraint.** The runtime executor (`worktree-hooks.sh`) extracts the *first* backtick-quoted
span of each `- ` item, so every command must be a single backtick-quoted span on one line with no
embedded backticks — a multi-line or backtick-containing command is silently dropped. Chain a compound
command with `&&` on one line, or wrap it in a checked-in script and reference that script.

### claude-code-stack-profile

**Optional but broadly useful**, and the only block here not read by a pipeline skill at a defined
step. It's general operating guidance written into the consuming repo's
**CLAUDE.md** so Claude Code auto-loads it into *every* session in that repo — the resolver, the
evaluator, and any ad-hoc session (someone running only the drafter, or just hand-coding). It
answers one question: **how do you run this stack's commands inside a Claude Code session without
drowning the context window?**

Because the value is the auto-load, this block always lives in **CLAUDE.md** (or a file CLAUDE.md
`@`-includes), regardless of where the pipeline config blocks live — the one deliberate exception
to the "config defaults to `COMMANDS.md`" rule. The interior is free prose under a human-facing
heading; `config-block.sh` copies it verbatim and reconciles it idempotently like any other block.

```markdown
<!-- claude-code-stack-profile -->
## Running this stack with Claude Code

<concise operating guidance — see scope and constraints below>
<!-- /claude-code-stack-profile -->
```

**No parser constraint.** Nothing parses this block at runtime — it's model-read via the CLAUDE.md
auto-load, not extracted by a script. So unlike `worktree-*`, the one-backtick-span-per-line rule
does **not** apply: multi-line prose, lists, and several code spans on a line are all fine.

**Scope — the operating/efficiency layer only.** What belongs:
- which commands are slow enough to run backgrounded (`run_in_background: true`) and waited on;
- when to redirect output to a log and read back the tail / `grep` the failures, vs. let a terse
  command stream inline;
- the stack's terse/machine-readable output formatter, and its fast-subset / re-run-only-failures
  invocation syntax;
- parallelism knobs and any per-worker resource (e.g. a test database per worker) a session should
  know about.

What does **not** belong: coding conventions, architecture, or style (those are the human's
CLAUDE.md), and a plain command list (that's what `/init` produces — complement it, don't
duplicate). Keeping it narrow is what keeps it concise enough to justify the always-loaded weight.

**Surface the signal, never suppress it.** Guidance is always *redirect-then-read-back* (`… | tee
<log>`, then `grep`/tail), never "hide output" — the reader still has to see pass/fail and the
failures, or it's blinded.

**Authored by research-and-propose with a default-on currency check** (setup §3): draft from stack
knowledge, run a lightweight web check that the idioms are still current — currency is this block's
whole point — and escalate to fuller research for an unfamiliar stack. Never fabricate; if the
stack is unrecognized, ask or skip.

**Two worked examples.** State the generic principle first — *name the slow/noisy commands and how
to run them cheaply; leave the fast ones alone* — then fill it in. Same shape, two stacks.

*Rails:*

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

*Node / TS:*

```markdown
<!-- claude-code-stack-profile -->
## Running this stack with Claude Code

- Unit tests are fast — run targeted: `npm test -- path/to/foo.test.ts`.
- The full suite, e2e runs, and coverage are slow/noisy — background and log: `npm run test:e2e > /tmp/e2e.log 2>&1`, then read the tail / `grep` failures. Prefer the reporter's terse mode (`--reporter=dot`) over the verbose default.
- Re-run only failures (`vitest --changed`, `jest --onlyFailures`) instead of the full run.
- One-time slow steps (`npm ci`, a cold production build) — background and wait.
<!-- /claude-code-stack-profile -->
```

## Detection heuristics

Propose drafts from what the repo already declares, then confirm. Sources, roughly in order of
signal strength:

1. **CI workflows** (`.github/workflows/*.yml`) — the commands CI runs are the strongest signal for
   what the static and test commands *should* be, because they're already the project's source of
   truth for "is this green". Map CI's lint/typecheck steps → static checks; its test step → the
   test wrapper / full-suite-command.
2. **Task runner manifests:**
   - **Node / TS** — `package.json` `scripts`: `lint`, `typecheck`/`tsc`, `build` → static checks;
     `test`, `test:unit`, `test:e2e` → test wrapper (`npm run <script>` / `pnpm <script>`). Test
     framework + dir (`jest`, `vitest`, `__tests__/`, `*.test.ts`) → target names and naming.
   - **Go** — `go vet ./...`, `golangci-lint run` → static; `go test ./...` → wrapper; packages are
     the targets; naming maps `foo.go` ↔ `foo_test.go` in the same package.
   - **Python** — `ruff check`/`flake8`, `mypy` → static; `pytest` → wrapper; `tests/` modules are
     the targets; naming maps `module.py` ↔ `tests/test_module.py`.
   - **Swift / Apple** — `swiftlint`, layer-import scripts, `scripts/xcb.sh` style wrappers → static;
     `xcodebuild test` or the project's `xcb.sh` → wrapper; `<App>Tests` (unit) / `<App>UITests` (UI)
     are the targets; canonical-suite's three labels come from the wrapper's build-vs-run flags.
   - **Ruby / Rails** — `rubocop`, `brakeman` → static; `bin/rails test` (or `bundle exec rspec`) →
     wrapper; `test/` (Minitest) or `spec/` (RSpec) modules are the targets, with system/feature
     tests (`test/system`, `spec/system`/`spec/features`) as the integration target; naming maps
     `app/<layer>/<x>.rb` ↔ `test/<layer>/<x>_test.rb` (or `spec/<layer>/<x>_spec.rb`). No separate
     compile step, so canonical-suite's three labels collapse to the one test command.
   - **Make** — `Makefile` targets: `make lint`/`make check` → static; `make test` → wrapper.
3. **Project-type signals** — `Package.swift`/`*.xcodeproj`, `go.mod`, `pyproject.toml`/`setup.cfg`,
   `Cargo.toml`, `pom.xml`/`build.gradle`, `Gemfile`/`config/application.rb` — disambiguate stack when
   the manifests above are absent.
4. **`scripts/*.sh`** — repos often wrap their real commands (`scripts/check-*.sh`, `scripts/test.sh`,
   `scripts/xcb.sh`); prefer the wrapper over the raw tool when one exists, since that's what the
   project maintains.

Rules of thumb:
- **Prefer the project's own wrapper** over a raw tool invocation — it's what's maintained and what
  CI uses.
- **Static lists exclude tests.** If detection surfaces a single "test everything" command, that's
  the test-target wrapper / full-suite-command, not a static check.
- **Never fabricate.** If a source yields nothing for a block, present it empty and ask — a wrong
  command wired in silently is worse than an absent block the pipeline skill asks about at runtime.

## Legacy migration

Older repos declare one `pr-evaluator-health-checks` block holding both static checks and the test
invocation as a flat command list. Re-running setup offers to split it:

1. `config-block.sh read <file> pr-evaluator-health-checks` — get the current commands.
2. **Static commands** (lints, codegen, dep resolution, boundary checks) → `pr-evaluator-static-checks`.
3. **The test invocation** → the basis for `pr-evaluator-test-target`: that command becomes both the
   `wrapper` and the `full-suite-command`. The per-target `naming` / fallbacks aren't recoverable from
   a flat command — interview the user (or carry over from `issue-resolver-test-target` if it already
   exists and matches).
4. Confirm the split, `upsert` both new blocks, then `remove pr-evaluator-health-checks`.

Migration is opt-in and reversible-by-eye (the user sees the diff). Don't remove the legacy block
until both replacements are written and confirmed.

## Worked examples

The same schema, filled in for two different stacks. Read them side by side: the block *shapes*
and field names are identical — only the commands, target names, and naming rules change with the
stack. That's the contract working as intended; nothing here is stack-specific by design.

### Swift / Apple (`food-journal`) — the canonical shape the evaluator documents

```markdown
<!-- pr-evaluator-static-checks -->
- `./scripts/check-layer-imports.sh` — Layer-import boundary lint (fast, <5s)
- `CI=1 ./scripts/run-swiftlint.sh` — SwiftLint in CI strict mode
<!-- /pr-evaluator-static-checks -->

<!-- pr-evaluator-test-target -->
- wrapper: `./scripts/xcb.sh`
- full-suite-command: `./scripts/xcb.sh`
- targets:
  - `FoodJournalTests` (unit)
    - naming: source `<X>.swift` ↔ `FoodJournalTests/<X>Tests.swift`; suite id `FoodJournalTests/<X>Tests`.
    - helpers-fallback: `./scripts/xcb.sh -only-testing FoodJournalTests`
    - broad-change-fallback: `./scripts/xcb.sh -only-testing FoodJournalTests`
  - `FoodJournalUITests` (UI)
    - naming: flow-oriented; map by symbol references and `@testable import`.
    - helpers-fallback: `./scripts/xcb.sh -only-testing FoodJournalUITests`
    - broad-change-fallback: none
<!-- /pr-evaluator-test-target -->

<!-- pr-evaluator-escalation-labels -->
- `full-suite-required` — bypass targeted selection
<!-- /pr-evaluator-escalation-labels -->
```

The resolver side mirrors this — same `wrapper`, target names, naming, and fallbacks — minus the
`full-suite-command` line, plus the `issue-resolver-canonical-suite` block for the epic flow. Swift
builds and runs tests in separate steps, so the canonical-suite's three labels are distinct:

```markdown
<!-- issue-resolver-canonical-suite -->
- full-suite: `./scripts/xcb.sh test`
- build-once: `./scripts/xcb.sh build-for-testing`
- retry-without-rebuild: `./scripts/xcb.sh test-without-building`
<!-- /issue-resolver-canonical-suite -->
```

### Ruby on Rails (`books-api`) — the same schema, a different stack

```markdown
<!-- pr-evaluator-static-checks -->
- `bin/rubocop` — Ruby style + lint
- `bin/brakeman --no-pager -q` — static security scan
<!-- /pr-evaluator-static-checks -->

<!-- pr-evaluator-test-target -->
- wrapper: `bin/rails test`
- full-suite-command: `bin/rails test && bin/rails test:system`
- targets:
  - `test` (unit)
    - naming: source `app/<layer>/<x>.rb` ↔ `test/<layer>/<x>_test.rb`; suite id `test/<layer>/<x>_test.rb`.
    - helpers-fallback: `bin/rails test test/<layer>`
    - broad-change-fallback: `bin/rails test`
  - `test/system` (system / integration)
    - naming: flow-oriented; map by symbol references and rendered partials/routes.
    - helpers-fallback: `bin/rails test test/system`
    - broad-change-fallback: none
<!-- /pr-evaluator-test-target -->

<!-- pr-evaluator-escalation-labels -->
- `full-suite-required` — bypass targeted selection
<!-- /pr-evaluator-escalation-labels -->
```

Rails runs tests directly — there's no separate compile step — so the canonical-suite's three
labels collapse to the single test command (the all-three-identical degenerate case the
`issue-resolver-canonical-suite` authoring notes call out for non-compile stacks):

```markdown
<!-- issue-resolver-canonical-suite -->
- full-suite: `bin/rails test && bin/rails test:system`
- build-once: `bin/rails test && bin/rails test:system`
- retry-without-rebuild: `bin/rails test && bin/rails test:system`
<!-- /issue-resolver-canonical-suite -->
```
