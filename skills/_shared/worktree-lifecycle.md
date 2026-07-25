# Worktree hook blocks — shared reference

The consuming repo's **`<!-- worktree-setup -->` / `<!-- worktree-teardown -->` blocks**: the
external contract ([prd.md §7](../../docs/prd.md) "Config marker blocks"). A repo declares the
commands that provision and release per-worktree resources; the plugin discovers, parses, and runs
them.

**Scope of this file.** The block format and the semantics a repo must honor when authoring one.
The *mechanics* — where workspaces live, reuse and branch-exclusivity rules, when hooks fire, how
failures are classified — belong to `scripts/workspace.py` and
[architecture.md §6](../../docs/architecture.md); this file does not restate them. `setup` authors
these blocks (see `skills/setup/references/block-authoring.md`); `workspace.py ensure` runs the
setup commands on every ensure (the `resolver`'s work workspace), and `workspace.py remove --work`
runs the teardown commands before removing a merged workspace (the `evaluator`).

## The blocks a consuming repo declares

Both blocks live in `COMMANDS.md` (preferred) or `CLAUDE.md`:

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
`pr-evaluator-static-checks`): one Markdown list item per command — a backtick-quoted command, then
` — `, then a short human description. **Order matters** — commands run in declaration order. Either
block is optional; if a phase's block is absent the phase is a clean no-op (no warning, no prompt —
most repos need neither hook). The commands run **inside the workspace**, as the consuming repo's
own opaque shell commands; the trust boundary is `setup`'s confirm-before-write gate, and nothing
re-validates them at run time.

## What the commands must guarantee

- **Setup is idempotent.** It runs on **every** workspace ensure — fresh create *and* reuse — so
  re-entering a healthy workspace must cost only the idempotency check (reuse the still-resolving
  simulator UDID on a Swift/iOS project, or the already-bound dev port / scratch database on a Rails
  project; otherwise discard the stale state and re-provision). Running on every entry is
  load-bearing: a workspace whose per-worktree state went missing for any reason silently falls back
  to whatever **global** resource the test wrapper's defaults pick, which masks the isolation the
  hook exists to provide — tests appear to run, but against a shared resource, so passes and
  failures are both untrustworthy.
- **Setup persists whatever state the rest of the workflow needs**, and the plugin never interprets
  that state. Common patterns: write a `<workspace>/.worktree-state/<key>` file the project's other
  commands read; allocate a free port and export it via a `.envrc`; provision a scratch container or
  database and record its handle. Make setup idempotent against a half-failed prior run so it can be
  re-triggered without orphaning resources.
- **Teardown is best-effort and tolerant of missing state.** It reads the same state setup wrote and
  releases it; it may run against a workspace whose setup partially failed, or which the operator
  already cleaned up by hand.
- **Teardown runs before the workspace is removed.** The teardown commands live *inside* the
  workspace (e.g. a checked-in `./scripts/worktree-teardown.sh`), so once the workspace is removed
  the commands are gone and any resources they would have released — simulators, containers, ports,
  scratch databases — leak.

Setup failure is fail-fast (the workspace exists but is not ready for tests, so proceeding would run
against a missing resource); teardown failure is logged and never blocks removal. Those policies are
fixed by `workspace.py`; the *idempotency* of the commands themselves is the consuming repo's
responsibility.

## Abandoned work

Teardown and removal happen only on the evaluator's post-merge path, so a PR abandoned or closed
without merging leaves its workspace — and any scarce resource its setup allocated (a license-limited
simulator, a bound port, a scratch DB) — until an operator reclaims it. A repo that provisions a
scarce per-worktree resource should expect to do that by hand on abandoned PRs.

Comment-only / no-code responses (questions, blocked issues, duplicates) never open a workspace at
all, so neither hook fires.
