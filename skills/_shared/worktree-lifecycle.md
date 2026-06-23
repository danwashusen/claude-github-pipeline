# Worktree lifecycle — shared reference

Two GitHub-pipeline skills work inside a `git worktree` and run the consuming repo's per-worktree
lifecycle commands: `github-issue-resolver` **creates** worktrees and runs **setup** on every entry
(it never removes them), and `github-pr-evaluator` runs **teardown** and **removes** the worktree
after a merge (it is the only place a worktree is removed automatically). This file is the single
source of truth for the worktree contract — the path convention, the reuse/nesting rules, the
idempotency guarantee, the `<!-- worktree-setup -->` / `<!-- worktree-teardown -->` block format, and
the mechanical runner. Both skills reference this file rather than restating the contract inline;
each keeps only its caller-specific glue (which branch it creates, where it triggers setup/teardown).

The mechanical loop (discover the block → parse it → `cd` into the worktree → run the commands →
report) lives in **`${CLAUDE_PLUGIN_ROOT}/scripts/worktree-hooks.sh`**, not in either skill body. A
skill invokes the script from its own main loop (never via `github-ops` — the worktree lifecycle is
cwd-stateful and stays with the caller) and acts on the script's structured result.

## Where worktrees live

`.worktrees/<branch-name>/` inside the repo. Before the first worktree is created in a repo, ensure
`.gitignore` contains a `.worktrees/` line — append it if missing (small, idempotent edit; never
remove anything else). Without that entry every worktree's files show up as untracked in the main
checkout's `git status`.

**The worktree is the working directory.** Once a worktree is created or reused, `cd
.worktrees/<branch-name>` is the cwd for every subsequent command in that skill run — baselines,
edits, `git add/commit/push`, `gh pr create`, the review loop. State the path explicitly when you
switch so the user can follow along (and run their own commands in the same place).

## Reuse rule

Before any `git worktree add`, run `git worktree list --porcelain` and check whether the target
branch is already checked out somewhere. If it is, `cd` to that path and continue — don't try to add
it again (git will error) and don't recreate it. The existing worktree is the source of truth.

## Nesting guard

If `git rev-parse --git-dir` shows a path under `.git/worktrees/`, you are already running inside a
worktree. Don't nest. Find the main working tree (the first `worktree` entry in `git worktree list
--porcelain`) and run `git worktree add` with paths relative to that main tree's root.

## Setup runs on every entry — and must be idempotent

Run setup **after every `git worktree add` and on every reuse of an existing worktree** — both arms,
every time. Setup is idempotent by contract, so re-entering a healthy worktree costs only the
idempotency check (e.g., reuse the still-resolving simulator UDID on a Swift/iOS project, or the
already-bound dev port / scratch database on a Rails project; otherwise discard the stale state and
re-provision).

Running on every entry is load-bearing, not defensive overkill. A worktree whose per-worktree state
is missing for any reason — the original create-arm run missed discovery, a sibling tool deleted it,
the user wiped the state dir, or setup never ran because an earlier invocation skipped it — will
otherwise silently fall back to whatever **global** resource the test wrapper's defaults pick. That
masks the per-worktree isolation the setup hook exists to provide: tests appear to run, but against a
shared resource, so failures and successes are both untrustworthy. Re-running idempotent setup on
entry closes that gap.

**What setup commands typically do.** Provision per-worktree resources and persist whatever state the
rest of the workflow needs — the skill does not interpret that state. Common patterns: write a
`<worktree>/.worktree-state/<key>` file the project's other commands read; allocate a free port and
export it via a `.envrc`; provision a scratch container or database and record its handle. Make setup
idempotent against a half-failed prior run so it can be re-triggered without orphaning resources.

## Teardown is best-effort and runs before removal

Teardown releases the resources setup created (read the same state, tear it down). It is idempotent
and tolerant of missing state — it may run on a worktree whose setup partially failed, or which the
user already cleaned up manually.

**Ordering is load-bearing: teardown must run BEFORE `git worktree remove`.** The teardown commands
live *inside* the worktree (e.g. a `./scripts/worktree-teardown.sh` checked into the repo), so once
the worktree is removed the commands are gone and any resources they would have released (simulators,
containers, ports, scratch databases) leak. Run teardown, then remove.

## The marker blocks the consuming repo declares

A project declares its hooks via two marker-delimited blocks in `COMMANDS.md` (preferred) or
`CLAUDE.md` — or any file either `@`-includes that is reachable from the repo root:

```markdown
<!-- worktree-setup -->
- `<command>` — <description>
- `<command>` — <description>
<!-- /worktree-setup -->

<!-- worktree-teardown -->
- `<command>` — <description>
<!-- /worktree-teardown -->
```

Format matches the other list-style command blocks (`issue-resolver-fast-checks`,
`pr-evaluator-static-checks`): one Markdown list item per command — a backtick-quoted command,
then ` — `, then a short human description. **Order matters** — commands run in declaration order.
Either block is optional; if a phase's block is absent the phase is a clean no-op (no warning, no
prompt — most repos need neither hook).

## The mechanical runner: `scripts/worktree-hooks.sh`

One self-contained script runs both phases; the skill never re-implements the discover/parse/run loop
inline. It does **not** create or remove the worktree — those cwd-stateful git ops stay in the
calling skill. It runs the project-declared commands inside an already-existing worktree and reports.

```bash
# setup — fail-fast; non-zero exit if a command fails. Pass --reused on a reused worktree
# so the status line names it. --dry-run lists the commands without running them.
${CLAUDE_PLUGIN_ROOT}/scripts/worktree-hooks.sh setup    <worktree_path> <repo_root> [--reused] [--dry-run]

# teardown — best-effort; logs each failure, continues, always exits 0.
${CLAUDE_PLUGIN_ROOT}/scripts/worktree-hooks.sh teardown <worktree_path> <repo_root>            [--dry-run]
```

- **Discovery & parsing** (scan `COMMANDS.md`/`CLAUDE.md` + their `@`-includes for the phase's block,
  extract the backtick commands, first non-empty block wins) is handled by the script.
- **Result on stdout** is a single JSON object: `op`, `phase_present`, `commands_run`, `succeeded`,
  `dry_run`, plus `reused` (setup), `first_failure {step, command, output_tail}` (setup, on failure),
  `failures [...]` (teardown), and `would_run [...]` (dry-run). Human-readable progress (the status
  lines below) streams to **stderr**.
- **Exit codes**: `0` success or no block; `1` a setup command failed (`first_failure` populated);
  `2` usage / path-not-found.

**How the skill uses it.** Setup: run the script at each create/reuse site; if it exits non-zero,
surface `first_failure.command` and `output_tail` and **stop** — the worktree exists but isn't ready
for tests, and proceeding would run against a missing resource. Teardown: run the script, then run
`git worktree remove`; a non-empty `failures` array is logged but never blocks removal.

The script is a dumb deterministic executor. The fail-fast (setup) / best-effort (teardown) policies
are fixed; the *idempotency* of the commands themselves is the consuming repo's responsibility.

## Status-line announcements (emitted by the script to stderr)

- Setup, fresh worktree: `Running worktree setup (N command(s))…` → `Worktree setup complete.`
- Setup, reused worktree (`--reused`): `Running worktree setup (N command(s))… (worktree reused;
  setup is idempotent)` → same complete/failure lines. The reuse variant fires even when setup is a
  true no-op, so users learn setup ran defensively rather than wondering whether it was skipped.
- Setup, on failure: `Worktree setup failed at step i: <command>` followed by the output tail.
- Teardown: `Running worktree teardown (N command(s))…` → `Worktree teardown complete.`, with
  `Worktree teardown step i failed: <command>` logged per failure (run continues).

No stamp file is needed — the skill ties setup to the worktree-entry event, not to a persistent
on-disk marker. If the user manually re-runs setup to recover a lost resource, that's their call.

## Ownership split (deliberate, not duplication)

- **`github-issue-resolver`** creates worktrees (off `main` for a standard issue, off the epic branch
  for a story) and runs **setup** on every create/reuse. It **never** runs `git worktree remove` — a
  worktree may hold unpushed commits or in-flight edits, so silent teardown would lose work. Its
  manual-cleanup reminder names the teardown + removal sequence for the user.
- **`github-pr-evaluator`** runs **teardown** then **removes** the worktree after a merge — the only
  place removal happens automatically.

Comment-only / no-code responses (questions, blocked issues, duplicates) skip the worktree entirely —
there is no branch to host.
