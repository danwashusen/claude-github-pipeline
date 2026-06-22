---
name: github-pipeline-setup
model: opus
effort: medium
description: Configure (or re-configure) a repository so the github-pipeline skills — resolver, evaluator, planner — actually work in it, by writing the marker-delimited command blocks they read from COMMANDS.md / CLAUDE.md. Use this skill right after installing the plugin, or any time the pipeline can't find how to test/check a repo: phrases like "set up the pipeline", "configure the pipeline for this repo", "onboard this repo to github-pipeline", "the resolver doesn't know how to run my tests", "configure the fast-checks / static-checks", "set up the COMMANDS.md markers", "how do I tell the evaluator which suite to run", "migrate my health-checks block", or "re-run setup" all qualify. Trigger this even when the user doesn't name a specific marker — if they're wiring this plugin into a project, or a pipeline skill reported a missing `<!-- … -->` block, this is the skill. Detects the project's existing lint/test/build commands and proposes drafts; is safe to run repeatedly (idempotent — reconciles in place, never duplicates); offers to migrate legacy single-block declarations and to dry-run the commands it writes. Does NOT itself draft, plan, or resolve issues — it only configures the conventions the other skills depend on.
---

# GitHub Pipeline Setup

Make a repository ready for the `github-pipeline` skills. The resolver, evaluator, and
planner don't carry per-project config — they read it at use-time from **marker-delimited
blocks** the consuming repo declares in `COMMANDS.md` (preferred) or `CLAUDE.md`. A repo with
none of those blocks degrades to "ask the user / fall back to the full suite" on every run;
a repo with them gets fast, targeted, predictable behaviour. This skill writes and reconciles
those blocks.

It is deliberately the *only* blessed place to write them. The resolver and evaluator both
refuse to write the blocks silently — they say "always ask the user before modifying project
files" — precisely because that write belongs here, behind a confirmation, where the user can
see exactly what's going in.

**This is not a pipeline stage.** Unlike draft → research → plan → resolve → evaluate, setup
has no cross-session handoff and no GitHub state — it edits local Markdown. So it does not emit
a `## Handoff` block; it ends with a plain setup summary (see §7).

### Asking the user a decision

Every gate in this skill — which file to write, confirm-before-write, migrate-or-not,
dry-run-or-not — goes through `AskUserQuestion` per the shared contract in
[`../_shared/asking-the-user.md`](../_shared/asking-the-user.md): one decision per card,
`header` ≤ 12 chars, imperative `label`s with consequence-bearing `description`s, options
generated from what you actually found. That file is the single source of truth.

### The single write path: `config-block.sh`

Idempotency is the whole point of this skill — "run it again and nothing breaks". That guarantee
lives in deterministic code, not in you landing an in-place Edit byte-perfect every time. **Never
hand-roll `sed`/`Edit`/`Write` against these blocks.** Every read and every write goes through the
bundled script, the same way the other skills route all `gh` I/O through `gh-persist.sh`:

```
${CLAUDE_PLUGIN_ROOT}/scripts/config-block.sh read   <file> <marker-name>
${CLAUDE_PLUGIN_ROOT}/scripts/config-block.sh list   <file>
${CLAUDE_PLUGIN_ROOT}/scripts/config-block.sh upsert <file> <marker-name> <body-path> [--dry-run]
${CLAUDE_PLUGIN_ROOT}/scripts/config-block.sh remove <file> <marker-name>             [--dry-run]
```

- `<marker-name>` is the bare name — `issue-resolver-fast-checks`, **not** `<!-- … -->`.
- **`upsert`** replaces the interior of an existing block or appends a fresh one in canonical form.
  Re-running with the same body is a byte-level no-op (the file isn't even touched). It returns a
  one-line JSON envelope with `changed: true|false` — `false` means it was already in the desired
  state. `--dry-run` reports what *would* change without writing.
- **`read`** prints a block's interior (exit 3 if absent). **`list`** prints `<status> <name>` for
  every block found — `ok` / `open` (unterminated) / `dup` (declared twice) — which is how you take
  inventory and spot legacy or malformed blocks.
- **`remove`** deletes a block (and one blank line above it); used by legacy migration. Idempotent.
- Malformed input is refused, not guessed: a duplicated marker exits 4, an unterminated one exits 5.
  Surface these to the user rather than working around them — a block declared twice means the repo
  is already in a confusing state the pipeline skills would also trip on.

**How you write a block:** stage the body to a scratch file with `Write` (e.g.
`/tmp/gh-setup-<repo>/<marker>.md`), then call `config-block.sh upsert <file> <marker> <that-path>`.
Staging-then-passing-the-path (not re-inlining the body on a command line) is the same discipline
`gh-persist.sh` uses — it keeps the exact bytes intact and keeps `upsert` deterministic.

### The blocks you configure

Eight blocks across two consumer skills, plus the worktree-lifecycle pair. **Before drafting any of
them, `Read` [`references/block-authoring.md`](references/block-authoring.md)** — it is the
authoring spec (exact shape, what belongs in each, detection heuristics for inferring the contents
from the repo, and the legacy-migration mapping). It is progressively disclosed, so the forced Read
is what guarantees the per-block shapes are in context before you propose anything.

| Marker name | Read by | Shape |
|---|---|---|
| `issue-resolver-fast-checks` | resolver static gate | command list |
| `issue-resolver-test-target` | resolver test selection | prose config |
| `issue-resolver-canonical-suite` | resolver epic/baseline | 3 labelled commands |
| `pr-evaluator-static-checks` | evaluator static gate | command list |
| `pr-evaluator-test-target` | evaluator test selection | prose config |
| `pr-evaluator-escalation-labels` | evaluator escalation | label list (may be empty) |
| `worktree-setup` | resolver per-worktree provisioning | command list (optional) |
| `worktree-teardown` | evaluator per-worktree teardown | command list (optional) |

Leave the *runtime* markers the skills post themselves alone — `implementation-plan:v1`,
`issue-research:v1`, `pr-evaluator-health-cache:v1`. Those are emitted by the pipeline at use-time;
they are not configuration and this skill never touches them.

## Workflow

### 1. Preflight (report, don't fix)

Confirm the environment can run the pipeline at all, and **report gaps without trying to fix them** —
fixing auth or installing tools is the user's call, not a silent side effect of "setup".

- `git rev-parse --is-inside-work-tree` — is this a git repo? If not, say so and stop; the pipeline
  is git-centric and nothing below applies.
- `command -v jq`, `command -v git`, `command -v gh` — the scripts and skills need all three.
- `gh auth status` — the four caller skills can't do anything without an authenticated `gh`.

Print a short readiness line for each (`✓` / `✗ — <how to fix>`). Missing tooling or auth doesn't
block writing the blocks (you can still configure a repo offline), so note it and continue — just be
explicit that the pipeline won't *run* until the `✗`s are resolved.

### 2. Inventory the current configuration

Locate the target files and see what's already declared, so you reconcile rather than re-create.

- Look for `COMMANDS.md` and `CLAUDE.md` at the repo root. Run `config-block.sh list` on each.
- Classify every known marker as **present** (already `ok`), **legacy** (a
  `pr-evaluator-health-checks` block — the pre-split single block), **malformed** (`dup`/`open`), or
  **missing**.
- **Same marker in both files** is an ambiguity the pipeline skills would also hit (they scan both).
  Flag it and ask which file is canonical; plan to `remove` the duplicate from the other.
- Decide the **target file**: if blocks already live in one file, keep writing there (don't scatter
  config across two). If neither file exists, default to creating `COMMANDS.md` — it's the preferred
  home and keeps the pipeline config out of the human-facing `CLAUDE.md`. Confirm the target with the
  user before writing.

Tell the user the inventory in one compact view: what's set, what's legacy, what's missing.

### 3. Detect and draft

For each missing or to-be-updated block, infer a draft from the repo using the detection heuristics
in `references/block-authoring.md` — scan `package.json` scripts, `Makefile` targets, `scripts/*.sh`,
CI workflows (`.github/workflows/*.yml`), and project-type signals (`Package.swift`, `go.mod`,
`pyproject.toml`, etc.). Use `Explore`/`Grep`/`Glob` for this; it's local discovery, not GitHub I/O,
so there's no `github-ops` here.

- The **command-list** blocks (`*-fast-checks`, `*-static-checks`, `worktree-*`) can usually be
  drafted straight from detection — propose them filled in.
- The two **`*-test-target`** blocks are prose and project-specific (wrapper, per-target naming
  conventions, helper/broad-change fallbacks). Detection gets you the wrapper and target names;
  interview the user briefly for the naming convention and fallbacks rather than inventing them.
- If detection finds nothing for a block (e.g. no obvious static checks), don't fabricate commands —
  present the empty draft and ask, or offer to skip that block. A wrong command silently wired in is
  worse than an absent block the skill asks about at runtime.

Skip the optional `worktree-*` blocks unless the project clearly needs per-worktree resources (an
iOS simulator, a scratch DB, a bound port) — most repos don't, and the resolver no-ops silently when
they're absent.

### 4. Propose and confirm

Show each drafted block as a **diff against what's there now** (use `config-block.sh read` to get the
current interior for blocks that exist). The user is approving exact bytes that will go into their
repo — make it easy to see the change, not just the result.

Gate the write with `AskUserQuestion`: per-block confirm, or one "write all N as shown / let me edit
/ cancel" card when the drafts are clean. Honour edits inline before writing.

### 5. Write (and migrate legacy)

For each approved block: `Write` the body to `/tmp/gh-setup-<repo>/<marker>.md`, then
`config-block.sh upsert <target-file> <marker> <that-path>`. Read back the `changed` field — report
`changed: false` blocks as "already correct" so the user sees the idempotency working.

**Legacy migration.** When inventory found a `pr-evaluator-health-checks` block and the user opted in
(§3 / its own gate): `read` the legacy block, split its static commands into `pr-evaluator-static-checks`
and its test invocation into a `pr-evaluator-test-target` draft (mapping in
`references/block-authoring.md`), `upsert` both, then `remove pr-evaluator-health-checks`. Confirm the
split with the user before removing the original — you're restructuring their declaration, and the
test-target prose is a judgement call worth a look.

### 6. Offer to validate

After writing, offer (don't force — it executes project commands) to dry-run the fast static commands
once to catch typos and missing scripts immediately, while the user is still here. Run only the
`*-fast-checks` / `*-static-checks` lists — they're the fast, side-effect-light ones; never auto-run a
`test-target` full suite, which can be many minutes and may have side effects. Run each from the repo
root, in declared order, and report pass/fail per command. A failure here means the block references a
command that doesn't work yet — show it and let the user fix the command or the block.

### 7. Summary

Close with a compact summary (not a `## Handoff` — setup isn't a pipeline stage):

- **Target file** written, and per block: written / reconciled / already-correct / skipped.
- **Preflight ✗s** still outstanding, if any, with the one-line fix for each.
- **Next step** — a copy-pasteable suggestion to start actually using the pipeline, e.g.
  *"Configured. Run `/github-pipeline:github-issue-drafter` on your first piece of feedback, or
  `/github-pipeline:github-issue-resolver <issue#>` to resolve an existing issue."* Phrase it as a
  pointer, not a pipeline command — there's no session state to carry.

## When to ask the user

- **Target-file choice** when neither file exists, or when blocks are split across both — don't
  guess where their config should live.
- **Before every write** — this skill exists so the blocks are never written silently. Even on a
  clean greenfield, confirm the drafts.
- **Legacy migration** — splitting `pr-evaluator-health-checks` restructures the user's declaration
  and infers test-target prose; confirm before `remove`.
- **Validation** — running detected commands has side effects; make it opt-in.
- **Ambiguous detection** — when the repo offers several plausible test wrappers or no obvious
  static checks, present what you found and let the user pick, rather than wiring in a guess.

## Failure modes to avoid

- **Hand-rolling the edit.** `sed -i` / a raw `Edit` on these blocks re-opens the duplicate-block and
  drift-on-re-run problems the script exists to prevent. Route every write through `config-block.sh`.
- **Fabricating commands.** An invented `npm test` that cold-rebuilds, or a static check that doesn't
  exist, is worse than an absent block — the pipeline skill would at least *ask* about an absent one.
  Detect, then confirm; never confidently wire in something you didn't verify.
- **Touching runtime markers.** `implementation-plan:v1`, `issue-research:v1`, and the health-cache
  marker are written by the pipeline at use-time. They are not configuration; leave them be.
- **Scattering config across both files.** If the skills find the same marker in `COMMANDS.md` and
  `CLAUDE.md`, behaviour is ambiguous. Keep each marker in exactly one file.
- **Auto-fixing the environment.** Preflight reports `gh`/`jq`/auth gaps; it does not log in, install,
  or modify the user's machine. Those are the user's to resolve.
